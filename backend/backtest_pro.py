import pandas as pd
import numpy as np
import logging
import asyncio
import sys
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, time

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.ai_core import AICore, InferenceEngine
from backend.risk_manager import RiskManager
from backend.data_collector import DataCollector
from backend.mt5_bridge import MT5Bridge

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BacktestPro:
    def __init__(self, symbol="WIN$", n_candles=5000, timeframe="M1", data_file=None, **kwargs):
        self.symbol = symbol
        self.n_candles = n_candles
        self.timeframe = timeframe
        self.data_file = data_file
        self.bridge = MT5Bridge()
        self.ai = AICore()
        # Tenta carregar o motor de inferência (se existir o peso SOTA)
        try:
            self.inference = InferenceEngine(model_path="backend/patchtst_weights_sota.pth")
            self.ai.inference_engine = self.inference
            logging.info("🧠 Motor de Inferência SOTA carregado.")
        except:
            self.inference = True 
            self.ai.inference_engine = True
            logging.warning("⚠️ Pesos SOTA não encontrados. Mockando IA para backtest.")
            
        self.risk = RiskManager()
        self.collector = DataCollector(symbol)
        
        # Parâmetros Editáveis no Grid Search
        self.opt_params = {
            'rsi_period': kwargs.get('rsi_period', 9),
            'bb_dev': kwargs.get('bb_dev', 2.0),
            'vol_spike_mult': kwargs.get('vol_spike_mult', 1.2),
            'trailing_trigger': kwargs.get('trailing_trigger', 70.0),
            'trailing_lock': kwargs.get('trailing_lock', 50.0),
            'trailing_step': kwargs.get('trailing_step', 20.0),
            'sl_dist': kwargs.get('sl_dist', 150.0),
            'tp_dist': kwargs.get('tp_dist', 400.0),
            'confidence_threshold': kwargs.get('confidence_threshold', 0.85), # [SOTA] Filtro de Confiança IA
            'aggressive_mode': kwargs.get('aggressive_mode', True),
            'use_trailing_stop': kwargs.get('use_trailing_stop', True),
            'dynamic_lot': kwargs.get('dynamic_lot', False),
            'start_time': kwargs.get('start_time', "09:15"),
            'end_time': kwargs.get('end_time', "17:15"),
            'daily_trade_limit': kwargs.get('daily_trade_limit', 3),
            'use_flux_filter': kwargs.get('use_flux_filter', True),
            'flux_imbalance_threshold': kwargs.get('flux_imbalance_threshold', 1.2),
            'be_trigger': kwargs.get('be_trigger', 50.0),
            'be_lock': kwargs.get('be_lock', 0.0),
            'base_lot': kwargs.get('base_lot', 1) # Novo parâmetro para escala dinâmica
        }

        # Estado do Backtest
        self.initial_balance = kwargs.get('initial_balance', 10000.0)
        self.balance = self.initial_balance
        self.equity_curve = [self.initial_balance]
        self.sentiment_stream = kwargs.get('sentiment_stream', None) # {timestamp: score}
        self.timestamps = []
        self.trades = []
        self.position = None # {'side': 'buy/sell', 'entry_price': float, 'sl': float, 'tp': float, 'lots': int}
        self.consecutive_wins = 0 # Anti-Martingale tracker
        
        # Gestão de Performance
        self.max_drawdown = 0.0
        self.peak_balance = self.initial_balance
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        self.missed_signals = 0
        self.shadow_signals = {
            'total_missed': 0,
            'filtered_by_ai': 0,
            'filtered_by_flux': 0,
            'filtered_by_vol': 0,
            'tiers': {
                '70-75': 0,
                '75-80': 0,
                '80-85': 0
            }
        }
        self.last_day = None
        self.last_trade_time = datetime.datetime.min # Cooldown control

    async def load_data(self):
        if self.data_file is not None and os.path.exists(self.data_file):
            logging.info(f"📥 Lendo DataFrame Estático em O(1) do filepath: {self.data_file} (Amostra: {self.n_candles} velas)")
            df = pd.read_csv(self.data_file, nrows=self.n_candles)
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            return df

        logging.info(f"📥 Coletando {self.n_candles} candles de {self.symbol}...")
        if not self.bridge.connect():
            logging.error("❌ Falha ao conectar no MetaTrader 5.")
            return None
            
        # Pega o timeframe do MT5 (ex: mt5.TIMEFRAME_M1)
        import MetaTrader5 as mt5
        tf = mt5.TIMEFRAME_M1 # Hardcoded for backtest simplicity
        
        rates = await asyncio.to_thread(mt5.copy_rates_from_pos, self.symbol, tf, 0, self.n_candles)
        if rates is None or len(rates) == 0:
            logging.error(f"❌ Falha na coleta de candles para {self.symbol}. Verifique o Market Watch.")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        logging.info(f"✅ {len(df)} candles carregados.")
        return df

    def simulate_oco(self, row, position):
        """
        Simula execução OCO e Trailing Stop SOTA (Alpha V22 Pro).
        """
        side = position['side']
        sl = position['sl']
        tp = position['tp']
        entry = position['entry_price']
        
        trigger_pts = self.opt_params['trailing_trigger']
        lock_pts = self.opt_params['trailing_lock']
        step_pts = self.opt_params['trailing_step']
        use_trailing = self.opt_params.get('use_trailing_stop', False)
        
        if side == 'buy':
            # 1. Lógica de Breakeven [URGENTE]
            be_trigger = self.opt_params.get('be_trigger', 70.0)
            be_lock = self.opt_params.get('be_lock', 0.0)
            profit_pts_be = row['high'] - entry
            
            if profit_pts_be >= be_trigger and position['sl'] < entry:
                position['sl'] = entry + be_lock

            # 2. Lógica de Trailing Stop SOTA
            if row['low'] <= sl:
                return 'SL', sl

            if use_trailing:
                profit_pts = row['high'] - entry
                if profit_pts >= trigger_pts:
                    initial_lock = entry + lock_pts
                    if position['sl'] < initial_lock:
                        position['sl'] = initial_lock
                    new_sl = row['high'] - (trigger_pts - lock_pts)
                    if new_sl > position['sl'] + step_pts:
                        position['sl'] = new_sl
            
            # 3. Take Profit Fixo (se Trailing Stop estiver OFF)
            if not use_trailing:
                if row['high'] >= tp:
                    return 'TP', tp
                
        else: # sell
            # 1. Lógica de Breakeven [URGENTE]
            be_trigger = self.opt_params.get('be_trigger', 70.0)
            be_lock = self.opt_params.get('be_lock', 0.0)
            profit_pts_be = entry - row['low']

            if profit_pts_be >= be_trigger and position['sl'] > entry:
                position['sl'] = entry - be_lock

            # 2. Lógica de Trailing Stop SOTA
            if row['high'] >= sl:
                return 'SL', sl
                
            if use_trailing:
                profit_pts = entry - row['low']
                if profit_pts >= trigger_pts:
                    initial_lock = entry - lock_pts
                    if position['sl'] == 0 or position['sl'] > initial_lock:
                        position['sl'] = initial_lock
                    new_sl = row['low'] + (trigger_pts - lock_pts)
                    if new_sl < position['sl'] - step_pts:
                        position['sl'] = new_sl
                    
            if not use_trailing:
                if row['low'] <= tp:
                    return 'TP', tp
            
        return None, None

    async def run(self):
        data = await self.load_data()
        if data is None: return

        logging.info("🚀 Iniciando Simulação High Fidelity...")
        
        # ---- PRE-CALCULATIONS FOR EXTREME SPEED ----
        # 1. RSI
        rsi_p = self.opt_params['rsi_period']
        delta = data['close'].diff().fillna(0)
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_p).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_p).mean()
        rs = gain / (loss + 1e-6)
        data['rsi'] = 100 - (100 / (1 + rs))

        # 2. Bollinger Bands
        bb_d = self.opt_params['bb_dev']
        data['sma_20'] = data['close'].rolling(window=20).mean()
        data['std_20'] = data['close'].rolling(window=20).std()
        data['upper_bb'] = data['sma_20'] + bb_d * data['std_20']
        data['lower_bb'] = data['sma_20'] - bb_d * data['std_20']

        # 3. ATR 14
        tr = pd.concat([data['high'] - data['low'], 
                       (data['high'] - data['close'].shift()).abs(), 
                       (data['low'] - data['close'].shift()).abs()], axis=1).max(axis=1)
        data['atr_current'] = tr.rolling(window=14).mean()

        # 4. Volume SMA
        data['vol_sma'] = data['tick_volume'].rolling(window=20).mean()

        # 5. Regime Detection (Vectorized)
        try:
            obi_dummy = np.zeros(len(data))
            states = np.column_stack((data['atr_current'].fillna(0).values, obi_dummy))
            raw_labels = self.ai.regime_model.predict(states)
            centers = self.ai.regime_model.cluster_centers_
            sorted_indices = np.argsort(centers[:, 0])
            mapped_labels = np.array([np.where(sorted_indices == rl)[0][0] for rl in raw_labels])
            data['regime'] = mapped_labels
        except:
            data['regime'] = 0

        # 6. Directional Probability (Vectorized)
        prices = data['close'].values
        returns = np.diff(prices) / prices[:-1]
        returns_pad = np.insert(returns, 0, 0)
        
        ret_series = pd.Series(returns_pad, index=data.index)
        all_pos = (ret_series > 0).rolling(window=4).sum() == 4
        all_neg = (ret_series < 0).rolling(window=4).sum() == 4
        roll_sum = ret_series.rolling(window=4).sum()
        
        base_probs = np.where(all_pos | all_neg, 0.85, np.abs(roll_sum) * 100)
        data['dir_prob'] = np.clip(base_probs, 0.0, 0.99)
        data['dir_prob'] = data['dir_prob'].fillna(0.5)

        # Janela para indicadores (ex: 60 períodos)
        lookback = 60
        for i in range(lookback, len(data)):
            row = data.iloc[i]
            window = data.iloc[i-lookback:i]
            
            # 0. Reset de Perda Diária (Mudança de Dia)
            current_date = row.name.date()
            if self.last_day and current_date != self.last_day:
                logging.info(f"📅 Mudança de dia detectada ({self.last_day} -> {current_date}). Resetando métricas diárias.")
                self.daily_pnl = 0.0
                self.daily_trade_count = 0
            self.last_day = current_date

            # 1. Verificar saída de posição aberta (Simulação OCO)
            if self.position:
                exit_type, exit_price = self.simulate_oco(row, self.position)
                if exit_type:
                    self._close_trade(exit_price, exit_type, row.name)
                    self.last_trade_time = row.name # Inicia cooldown após fechar
                elif i - self.position['index'] > 25: # Time Exit (25 candles)
                    self._close_trade(row['close'], 'TIME', row.name)
                    self.last_trade_time = row.name

            # 2. Lógica de Entrada (Se estiver zerado)
            if not self.position:
                # --- INDICADORES ALPHA V21 (Pré-calculados) ---
                rsi = row['rsi']
                upper_bb = row['upper_bb']
                lower_bb = row['lower_bb']
                mid_bb = row['sma_20']
                atr_current = row['atr_current']
                vol_sma = row['vol_sma']

                # 4. Price Action: Rejeição (Pavio)
                body = abs(row['open'] - row['close'])
                upper_wick = row['high'] - max(row['open'], row['close'])
                lower_wick = min(row['open'], row['close']) - row['low']
                
                # 5. Volume Analysis (Alpha V22)
                v_mult = self.opt_params['vol_spike_mult']
                vol_spike = row['tick_volume'] > (vol_sma * v_mult)
                
                # 2.2 Filtros de Tendência
                # Gatilhos Alpha V22 (Counter-Trend Sniper)
                cooldown_ok = (row.name - self.last_trade_time) >= datetime.timedelta(minutes=15)
                
                # --- ADAPTIVE REGIME CORTEX ---
                # OBI is approximated as 0.0 in OHLCV backtester
                current_regime = row['regime']
                
                # --- INTELIGÊNCIA DO SUCESSO: REGIME MAESTRO & SCALPING ADAPTATION ---
                dir_prob = row['dir_prob']
                aggressive = self.opt_params.get('aggressive_mode', False)
                v_mult_eff = v_mult * 0.8 if aggressive else v_mult # Reduce volume spike req by 20%
                vol_spike_eff = row['tick_volume'] > (vol_sma * v_mult_eff)

                # 1. Regime Maestro (Trend Routing)
                # Verifica se a IA detectou 80%+ de chance de continuação
                if dir_prob >= 0.8 and current_regime == 1: # Trend Mode
                    v22_buy = (row['close'] > mid_bb) and (rsi > 50) and (rsi < 70) and vol_spike_eff
                    v22_sell = (row['close'] < mid_bb) and (rsi < 50) and (rsi > 30) and vol_spike_eff
                    dyn_sl = self.opt_params['sl_dist'] * 1.5
                    dyn_tp = self.opt_params['tp_dist'] * 2.0
                    regime_tag = "TREND_MAESTRO"
                
                # 2. Amorphous Regimes (Scalping Adaptation)
                elif current_regime == 2: # Noise Mode
                    rsi_buy_thresh = 30 if aggressive else 20
                    rsi_sell_thresh = 70 if aggressive else 80
                    v22_buy = (row['close'] < lower_bb) and (rsi < rsi_buy_thresh) and (lower_wick > body * 0.7) and vol_spike_eff
                    v22_sell = (row['close'] > upper_bb) and (rsi > rsi_sell_thresh) and (upper_wick > body * 0.7) and vol_spike_eff
                    # Fix TP to strict Scalping (100 points for WIN) 
                    dyn_sl = self.opt_params['sl_dist'] * 0.5 # Tighter SL
                    dyn_tp = 100.0 if "WIN" in self.symbol else self.opt_params['tp_dist'] * 0.5
                    regime_tag = "NOISE_SCALP"
                
                else: # Consolidation / Default Mode
                    rsi_buy_thresh = 35 if aggressive else 25
                    rsi_sell_thresh = 65 if aggressive else 75
                    v22_buy = (row['close'] < lower_bb) and (rsi < rsi_buy_thresh) and (lower_wick > body * 0.5) and vol_spike_eff
                    v22_sell = (row['close'] > upper_bb) and (rsi > rsi_sell_thresh) and (upper_wick > body * 0.5) and vol_spike_eff
                    # Fix TP to strict Scalping (100 points for WIN)
                    dyn_sl = self.opt_params['sl_dist']
                    dyn_tp = 100.0 if "WIN" in self.symbol else self.opt_params['tp_dist'] * 0.5 
                    regime_tag = "CONSOL_SCALP"

                # Filtros Operacionais
                t_start = datetime.datetime.strptime(self.opt_params['start_time'], "%H:%M").time()
                t_end = datetime.datetime.strptime(self.opt_params['end_time'], "%H:%M").time()
                time_ok = t_start <= row.name.time() <= t_end
                
                # [AGRESSIVO] Limite de 60% de perda diária
                limit_loss = self.initial_balance * 0.60
                risk_ok = self.daily_pnl > -limit_loss
                
                # Ignora limite numérico de trades no modo agressivo
                limit_ok = True 
                vol_min = 20 if "WIN" in self.symbol else 1.5
                vol_max = 400 if "WIN" in self.symbol else 30.0
                vol_stable = vol_min < atr_current < vol_max

                # AI Filter (SOTA Stability)
                # No backtest, simulamos a confiança da IA com base no RSI e Volume (Proxy)
                # Em um cenário real, isso viria do PatchTST. Aqui usamos uma heurística de 'Confluência'.
                test_side = "buy" if v22_buy else ("sell" if v22_sell else None)
                base_confidence = 0.70
                if vol_spike_eff: base_confidence += 0.15
                if (test_side == "buy" and rsi < 25) or (test_side == "sell" and rsi > 75): base_confidence += 0.10
                
                ai_stability = min(0.99, base_confidence)
                ai_filter_ok = ai_stability >= self.opt_params['confidence_threshold']
                
                # Sentiment Filter (V2.5)
                sentiment_ok = True
                if self.sentiment_stream and row.name in self.sentiment_stream:
                    score = self.sentiment_stream[row.name]
                    if (v22_buy and score < -0.5) or (v22_sell and score > 0.5):
                        sentiment_ok = False

                # Flux Filter (Proxy para Backtest CSV)
                flux_ok = True
                if self.opt_params.get('use_flux_filter', False):
                    flux_ok = row['tick_volume'] > (vol_sma * self.opt_params.get('flux_imbalance_threshold', 1.2))
                
                # Tracking Detalhado de Oportunidades Perdidas
                if (v22_buy or v22_sell) and not ai_filter_ok:
                    self.shadow_signals['total_missed'] += 1
                    self.shadow_signals['filtered_by_ai'] += 1
                    if 0.70 <= ai_stability < 0.75: self.shadow_signals['tiers']['70-75'] += 1
                    elif 0.75 <= ai_stability < 0.80: self.shadow_signals['tiers']['75-80'] += 1
                    elif 0.80 <= ai_stability < 0.85: self.shadow_signals['tiers']['80-85'] += 1
                
                if (v22_buy or v22_sell) and ai_filter_ok and not flux_ok:
                    self.shadow_signals['total_missed'] += 1
                    self.shadow_signals['filtered_by_flux'] += 1

                if (v22_buy or v22_sell) and time_ok and risk_ok and limit_ok and vol_stable and cooldown_ok and ai_filter_ok and sentiment_ok and flux_ok:
                    side = "buy" if v22_buy else "sell"
                    
                    # Risco Dinamizado por Regime
                    sl_dist = dyn_sl
                    tp_dist = dyn_tp
                    
                    sl = row['close'] - sl_dist if side == "buy" else row['close'] + sl_dist
                    tp = row['close'] + tp_dist if side == "buy" else row['close'] - tp_dist
                    
                    # Lote Dinâmico (Anti-Martingale)
                    # Lote Dinâmico / Fixo
                    if self.opt_params.get('force_lots'):
                        target_lot = self.opt_params['force_lots']
                    elif self.opt_params.get('dynamic_lot', False):
                        # Escala a partir do base_lot
                        base = self.opt_params.get('base_lot', 1)
                        target_lot = min(10, base + self.consecutive_wins)
                    else:
                        target_lot = self.opt_params.get('base_lot', 1)
                    
                    self.position = {
                        'side': side,
                        'entry_price': row['close'],
                        'sl': sl,
                        'tp': tp,
                        'lots': target_lot,
                        'index': i,
                        'time': row.name
                    }
                    self.daily_trade_count += 1
                    logging.info(f"🎯 V22 TRIGGER [{regime_tag}]: {side} @ {row['close']} | Vol Spike: {row['tick_volume']/vol_sma:.1f}x | RSI: {rsi:.1f}")
            
            # Atualizar Drawdown
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance
            current_dd = (self.peak_balance - self.balance) / self.peak_balance if self.peak_balance > 0 else 0
            if current_dd > self.max_drawdown:
                self.max_drawdown = current_dd

            self.equity_curve.append(self.balance)
            self.timestamps.append(row.name)

        logging.info("🏁 Simulação concluída.")
        return self.generate_report()

    def _close_trade(self, price, reason, exit_time):
        pos = self.position
        pnl_points = (price - pos['entry_price']) if pos['side'] == 'buy' else (pos['entry_price'] - price)
        
        # Cálculo financeiro (Simplificado: WIN=0.20/pt, WDO=10.00/pt)
        mult = 0.20 if "WIN" in self.symbol else 10.0
        pnl_fin = pnl_points * pos['lots'] * mult
        
        # Atualiza métricas de lote dinâmico
        if pnl_fin > 0:
            self.consecutive_wins += 1
        else:
            self.consecutive_wins = 0

        self.balance += pnl_fin
        self.daily_pnl += pnl_fin
        self.trades.append({
            'entry_time': pos['time'],
            'exit_time': exit_time,
            'side': pos['side'],
            'entry': pos['entry_price'],
            'exit': price,
            'lots': pos['lots'],
            'pnl_points': pnl_points,
            'pnl_fin': pnl_fin,
            'reason': reason
        })
        self.position = None

    def generate_report(self):
        df_trades = pd.DataFrame(self.trades)
        if df_trades.empty:
            logging.warning("Nenhum trade realizado no período.")
            return

        # Métricas
        win_rate = (len(df_trades[df_trades['pnl_fin'] > 0]) / len(df_trades)) * 100
        total_pnl = df_trades['pnl_fin'].sum()
        profit_factor = abs(df_trades[df_trades['pnl_fin'] > 0]['pnl_fin'].sum() / df_trades[df_trades['pnl_fin'] < 0]['pnl_fin'].sum()) if any(df_trades['pnl_fin'] < 0) else float('inf')
        
        # Gráficos com Plotly
        fig = make_subplots(rows=2, cols=1, subplot_titles=("Curva de Equity", "Distribuição de PnL por Trade"))
        
        # Equity
        fig.add_trace(go.Scatter(x=self.timestamps, y=self.equity_curve[1:], name="Capital"), row=1, col=1)
        
        # PnL Hist
        fig.add_trace(go.Bar(x=df_trades.index, y=df_trades['pnl_fin'], name="PnL por Trade"), row=2, col=1)
        
        fig.update_layout(height=800, title_text=f"Relatório Backtest AlphaX - {self.symbol}")
        
        report_path = "backend/backtest_report.html"
        fig.write_html(report_path)
        
        print("\n" + "="*50)
        print(f"RELATORIO DO PASSADO ({self.symbol})")
        print("="*50)
        print(f"Saldo Inicial: R$ {self.initial_balance:.2f}")
        print(f"Saldo Final:   R$ {self.balance:.2f}")
        print(f"Lucro Líquido: R$ {total_pnl:.2f}")
        print(f"Total Trades:  {len(df_trades)}")
        print(f"Win Rate:      {win_rate:.1f}%")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Max Drawdown:  {self.max_drawdown*100:.2f}%")
        print(f"\nRelatório Visual salvo em: {report_path}")
        print("="*50)
        
        return {
            'final_balance': self.balance,
            'total_pnl': total_pnl,
            'trades': df_trades.to_dict('records'),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': self.max_drawdown * 100,
            'shadow_signals': self.shadow_signals # Exporta oportunidades perdidas
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, default="WIN$")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--rsi_period", type=int, default=9)
    parser.add_argument("--bb_dev", type=float, default=2.0)
    parser.add_argument("--vol_spike_mult", type=float, default=1.5)
    parser.add_argument("--sl_dist", type=float, default=130.0)
    parser.add_argument("--tp_dist", type=float, default=260.0)
    
    args = parser.parse_args()

    # Filtra apenas os argumentos que pertencem aos opt_params ou ao init
    backtester = BacktestPro(
        symbol=args.symbol, 
        n_candles=args.n,
        rsi_period=args.rsi_period,
        bb_dev=args.bb_dev,
        vol_spike_mult=args.vol_spike_mult,
        sl_dist=args.sl_dist,
        tp_dist=args.tp_dist
    )
    asyncio.run(backtester.run())
