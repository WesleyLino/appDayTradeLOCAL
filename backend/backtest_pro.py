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
        self.ai = kwargs.get('ai_core', AICore())
        # Tenta carregar o motor de inferência (se existir o peso SOTA)
        try:
            self.inference = InferenceEngine(model_path="backend/patchtst_weights_sota.pth")
            self.ai.inference_engine = self.inference
            logging.info("🧠 Motor de Inferência SOTA carregado.")
        except Exception as e_engine:
            self.inference = None 
            self.ai.inference_engine = None
            logging.warning(f"⚠️ Pesos SOTA não carregados ({e_engine}). Usando modo degenerado (Sentiment/OBI).")
            
        self.risk = RiskManager()
        self.collector = DataCollector(symbol)
        
        # Parâmetros Editáveis no Grid Search - [ANTIVIBE-CODING]
        # Carrega Golden Params se existirem, senão usa defaults validados em 23/02/2026
        locked_params = {}
        try:
            import json
            params_path = os.path.join(os.path.dirname(__file__), "v22_locked_params.json")
            if os.path.exists(params_path):
                with open(params_path, "r") as f:
                    config = json.load(f)
                    locked_params = config.get("strategy_params", {})
                    logging.info("🛡️ Golden Params V22 carregados com sucesso.")
        except Exception as e:
            logging.warning(f"⚠️ Falha ao carregar Golden Params ({e}). Usando defaults hardcoded.")

        self.opt_params = {
            'rsi_period': kwargs.get('rsi_period', locked_params.get('rsi_period', 9)), # [ANTIVIBE-CODING]
            'bb_dev': kwargs.get('bb_dev', locked_params.get('bb_dev', 2.0)), # [ANTIVIBE-CODING]
            'vol_spike_mult': kwargs.get('vol_spike_mult', locked_params.get('vol_spike_mult', 1.0)), # [ANTIVIBE-CODING]
            'trailing_trigger': kwargs.get('trailing_trigger', locked_params.get('trailing_trigger', 70.0)), # [ANTIVIBE-CODING]
            'trailing_lock': kwargs.get('trailing_lock', locked_params.get('trailing_lock', 50.0)), # [ANTIVIBE-CODING]
            'trailing_step': kwargs.get('trailing_step', locked_params.get('trailing_step', 20.0)), # [ANTIVIBE-CODING]
            'sl_dist': kwargs.get('sl_dist', locked_params.get('sl_dist', 150.0)), # [ANTIVIBE-CODING]
            'tp_dist': kwargs.get('tp_dist', locked_params.get('tp_dist', 400.0)), # [ANTIVIBE-CODING]
            'confidence_threshold': kwargs.get('confidence_threshold', locked_params.get('confidence_threshold', 0.85)), # [ANTIVIBE-CODING]
            'aggressive_mode': kwargs.get('aggressive_mode', True),
            'use_trailing_stop': kwargs.get('use_trailing_stop', True),
            'dynamic_lot': kwargs.get('dynamic_lot', locked_params.get('dynamic_lot', False)),
            'start_time': kwargs.get('start_time', "09:15"),
            'end_time': kwargs.get('end_time', "17:15"),
            'daily_trade_limit': kwargs.get('daily_trade_limit', 3),
            'use_flux_filter': kwargs.get('use_flux_filter', locked_params.get('use_flux_filter', True)), # [ANTIVIBE-CODING]
            'flux_imbalance_threshold': kwargs.get('flux_imbalance_threshold', locked_params.get('flux_imbalance_threshold', 1.2)), # [ANTIVIBE-CODING]
            'be_trigger': kwargs.get('be_trigger', 50.0),
            'be_lock': kwargs.get('be_lock', 0.0),
            'base_lot': kwargs.get('base_lot', locked_params.get('base_lot', 1)), # [ANTIVIBE-CODING]
            'use_ai_core': kwargs.get('use_ai_core', locked_params.get('use_ai_core', True)) # [ANTIVIBE-CODING] v27 Default
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
        # Tracking de Oportunidades (Shadow Trading)
        self.shadow_signals = {
            'total_missed': 0,
            'filtered_by_ai': 0,
            'filtered_by_flux': 0,
            'v22_candidates': 0,
            'component_fail': {
                'rsi': 0,
                'bb': 0,
                'volume': 0
            },
            'tiers': {'70-75': 0, '75-80': 0, '80-85': 0}
        }
        self.last_day = None
        self.last_trade_time = datetime(2000, 1, 1) # Cooldown control
        self.data = None # Para inspeção externa

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
        use_trailing = self.opt_params.get('use_trailing_stop', False)
        
        if side == 'buy':
            # 1. Lógica de Trailing Stop - BUY (USA PARÂMETROS PADRÃO)
            trigger_pts = self.opt_params.get('trailing_trigger', 70.0)
            lock_pts = self.opt_params.get('trailing_lock', 50.0)
            step_pts = self.opt_params.get('trailing_step', 20.0)
            
            # 1.1 Lógica de Breakeven [URGENTE]
            be_trigger = self.opt_params.get('be_trigger', 70.0)
            be_lock = self.opt_params.get('be_lock', 0.0)
            profit_pts_be = row['high'] - entry
            
            if profit_pts_be >= be_trigger and position['sl'] < entry:
                position['sl'] = entry + be_lock

            # 1.2 Lógica de Trailing Stop SOTA
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
            
            # 1.3 Take Profit Fixo (Agora coexistente com Trailing Stop)
            if row['high'] >= tp:
                return 'TP', tp
                
        else: # sell
            # 1. Lógica de Trailing Stop - SELL (USA ASSIMETRIA V26)
            trigger_pts = self.opt_params.get('trailing_trigger_sell', 200.0)
            lock_pts = self.opt_params.get('trailing_lock_sell', 100.0)
            step_pts = self.opt_params.get('trailing_step_sell', 50.0)

            # 2.1 Lógica de Breakeven [URGENTE]
            be_trigger = self.opt_params.get('be_trigger', 70.0)
            be_lock = self.opt_params.get('be_lock', 0.0)
            profit_pts_be = entry - row['low']

            if profit_pts_be >= be_trigger and position['sl'] > entry:
                position['sl'] = entry - be_lock

            # 2.2 Lógica de Trailing Stop SOTA
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
                    
            # 2.3 Take Profit Fixo (Agora coexistente com Trailing Stop)
            if row['low'] <= tp:
                return 'TP', tp
            
        # 4. Scaling Out — Saída Parcial [SOTA v26] Real Financeiramente
        if not position.get('partial_done', False):
            # Se atingiu o lucro parcial (Ex: 50pts)
            partial_pts = self.risk.partial_profit_points
            profit_now = profit_pts_be if side == 'buy' else (entry - row['low'])
            
            if profit_now >= partial_pts and position['lots'] >= 2:
                # Realiza lucro de 1 contrato (metade no caso de base_lot=2)
                symbol_mult = 0.20 if "WIN" in self.symbol else 10.0
                partial_pnl = partial_pts * 1 * symbol_mult # 1 contrato de parcial
                self.balance += partial_pnl
                self.daily_pnl += partial_pnl
                
                position['partial_done'] = True
                position['lots'] -= 1 # Mantém o restante no trade
                logging.debug(f"✂️ PARCIAL REALIZADA: +{partial_pnl} R$ (Mantém {position['lots']} lotes)")

        return None, None

    async def run(self):
        if self.data is None:
            self.data = await self.load_data()
            
        data = self.data
        if data is None: 
            logging.error("❌ Erro no BacktestPro: load_data retornou None")
            return
            
        logging.info(f"🚀 Iniciando Simulação High Fidelity com {len(data)} velas...")
        
        # ---- PRE-CALCULATIONS FOR EXTREME SPEED ----
        # 1. RSI (Usa EWM para suavizar e evitar NaNs persistentes)
        rsi_p = self.opt_params['rsi_period']
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=rsi_p, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=rsi_p, adjust=False).mean()
        rs = gain / (loss + 1e-9)
        data['rsi'] = 100 - (100 / (1 + rs))
        data['rsi'] = data['rsi'].fillna(50.0) # Estabiliza início

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

        # [MELHORIA H - V28] EMA30 e EMA90 para Filtro de Tendência Diária
        data['ema30'] = data['close'].ewm(span=30, adjust=False).mean()
        data['ema90'] = data['close'].ewm(span=90, adjust=False).mean()

        # 4. Volume SMA
        data['vol_sma'] = data['tick_volume'].rolling(window=20).mean().bfill()
        
        # [SOTA v26] VWAP Intraday & Bands Pre-calculation
        tp = (data['high'] + data['low'] + data['close']) / 3
        v = data['tick_volume']
        # [SOTA v26] VWAP Intraday & Bands Pre-calculation - Corrigido para estabilidade de Index
        data['day'] = data.index.date
        group_v = v.groupby(data['day'])
        group_tp_v = (tp * v).groupby(data['day'])
        data['vwap'] = group_tp_v.cumsum() / group_v.cumsum()
        data['vwap_std'] = tp.rolling(20).std().fillna(0) # Std local de 20p como o bot
        
        # [SOTA v25] Microstructure Pre-calculation (Vectorized)
        logging.info("🔬 Calculando Microestrutura em Vetor (CVD/OFI/Ratio)...")
        body = data['close'] - data['open']
        high_low = data['high'] - data['low'] + 1e-8
        # Simula CVD com base no fechamento do candle
        data['cvd'] = (data['tick_volume'] * body.apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)).cumsum()
        # OFI simplificado para backtest OHLCV
        data['ofi'] = body / high_low
        # Volume Ratio (Z-score like)
        data['volume_ratio'] = data['tick_volume'] / (data['vol_sma'] + 1e-8)
        
        self.data = data # Expor para debug externo

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

            # [SOTA v5] Simulação de Spread Dinâmico (1.0 a 3.5 pts)
            fixed_spread = self.opt_params.get('spread')
            if fixed_spread is not None:
                current_spread = fixed_spread
            else:
                current_spread = 1.0 + (row['high'] - row['low']) * 0.1
                current_spread = min(4.0, max(1.0, current_spread))
            
            # [SOTA v5] Sincronizar Âncora de Sentimento (Price-Based Decay)
            self.ai.update_sentiment_anchor(row['close'])

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
                
                # --- MELHORIA H (V28): Filtro de Tendência Diária ---
                # Na abertura de cada dia, deteta se EMA30 < EMA90 → mercado em baixa.
                # Nesse caso, BUY fica vetado para evitar counter-trend losses.
                current_hour = row.name.hour
                current_minute = row.name.minute
                is_opening_window = (current_hour == 9 and current_minute <= 44) or (
                    current_hour < 9)
                current_ema30 = row['ema30']
                current_ema90 = row['ema90']
                if current_date != getattr(self, '_bias_day', None):
                    # Reset do bias diário na troca de dia
                    self._bias_diario = 'neutro'
                    self._bias_day = current_date
                if is_opening_window:
                    if current_ema30 < current_ema90 * 0.9998:  # Margem de 0.02% para evitar falsos alertas
                        self._bias_diario = 'baixa'
                    elif current_ema30 > current_ema90 * 1.0002:
                        self._bias_diario = 'alta'
                    else:
                        self._bias_diario = 'neutro'
                bias_veto_buy  = (getattr(self, '_bias_diario', 'neutro') == 'baixa')
                bias_veto_sell = (getattr(self, '_bias_diario', 'neutro') == 'alta')
                # [ANTIVIBE-CODING] Filtro de tendência V28 — aprovado pelo usuário em 01/03/2026

                # Gatilhos Alpha V22 (Counter-Trend Sniper)
                # [SOTA v24] Cooldown Dinâmico por Convicção
                # [MELHORIA J - V28] VERY_HIGH=3min
                # [MELHORIA N - V28] Cooldown adaptativo por regime: Tendência=5min, Lateral=9min, Ruído=12min
                cooldown_base = self.opt_params.get('cooldown_minutes', 7)
                last_conf = self.trades[-1].get('quantile_confidence', 'NORMAL') if self.trades else 'NORMAL'
                if last_conf == 'VERY_HIGH':
                    cooldown_min = 3
                else:
                    # Regime adaptativo: 5min tendência, 9min lateral, 12min ruído
                    _regime_now = row.get('regime', row['regime'] if 'regime' in row else 0)
                    if _regime_now == 1:   # Tendência clara
                        cooldown_min = 5
                    elif _regime_now == 2: # Ruído/alta volatilidade
                        cooldown_min = 12
                    else:                  # Lateral / indefinido
                        cooldown_min = max(cooldown_base, 8)
                # [ANTIVIBE-CODING] Cooldown adaptativo V28-N — aprovado pelo usuário em 01/03/2026
                cooldown_ok = (row.name - self.last_trade_time) >= timedelta(minutes=cooldown_min)
                
                # --- ADAPTIVE REGIME CORTEX ---
                # OBI is approximated as 0.0 in OHLCV backtester
                current_regime = row['regime']
                use_ai_core = self.opt_params.get('use_ai_core', False)
                
                # Default for operational filters
                vol_spike_eff = vol_spike
                ai_stability = 0.75 # Default threshold
                
                # --- [FASE 27] BLINDED DECISION CORTEX ---
                if use_ai_core:
                    # Preparar métricas sincronizadas
                    obi = 0.0 # Sem L2 no backtest CSV
                    sentiment_score = 0.0
                    if self.sentiment_stream and row.name in self.sentiment_stream:
                        sentiment_score = self.sentiment_stream[row.name]
                        # [SOTA v5] Atualiza o score interno do AI para que o Decay atue sobre o valor real do candle
                        self.ai.latest_sentiment_score = sentiment_score
                    
                    # Predição PatchTST (Agora com normalização automática no AICore)
                    patchtst_data = 0.0
                    if self.ai.inference_engine is not None:
                        # Extrair janela para predição
                        window_data = data.iloc[i-64:i] # PatchTST usa 64 velas
                        if len(window_data) == 64:
                            patchtst_data = await self.ai.predict_with_patchtst(self.ai.inference_engine, window_data)

                    # Volatilidade Anualizada (Proxy do Bot)
                    log_returns = np.log(window['close'] / window['close'].shift(1))
                    vol_val = float(log_returns.tail(20).std() * np.sqrt(252 * 480))
                    if not np.isfinite(vol_val): vol_val = 0.0

                    # AI Decision (Passando OFI se disponível)
                    # No backtest OHLCV, simulamos OFI como 0.5 * sentiment para manter consistência
                    sim_ofi = (sentiment_score * 0.5) if sentiment_score != 0 else 0.0
                    
                    ai_decision = self.ai.calculate_decision(
                        obi=obi,
                        sentiment=self.ai.latest_sentiment_score, # Usa score com decay v5
                        patchtst_score=patchtst_data,
                        regime=current_regime,
                        atr=atr_current,
                        volatility=vol_val,
                        hour=row.name.hour,
                        minute=row.name.minute, # [SOTA v5] Sincronia de minuto
                        ofi=sim_ofi,
                        current_price=row['close'], # [SOTA v5] Sincronia de preco
                        spread=current_spread, # [SOTA v5] Sincronia de spread
                        vwap=row['vwap'],
                        vwap_std=row['vwap_std']
                    )
                    
                    direction = ai_decision['direction']
                    v22_buy = direction == "BUY"
                    v22_sell = direction == "SELL"
                    quantile_confidence = ai_decision.get('quantile_confidence', "NORMAL")
                    
                    regime_tag = f"AI_{direction}_{quantile_confidence}"
                    dyn_sl = self.opt_params['sl_dist']
                    dyn_tp = self.opt_params['tp_dist']
                    
                    # Ajustes de alvos por regime (Compatibilidade com Phase 13)
                    if current_regime == 2 or current_regime == 0: # Noise/Consol
                        dyn_tp = 100.0 if "WIN" in self.symbol else self.opt_params['tp_dist'] * 0.5
                    
                    # Log de auditoria interna
                    if v22_buy or v22_sell:
                        logging.debug(f"🤖 Decisão da IA: {ai_decision}")
                        vol_spike_eff = vol_spike # No modo IA usamos volume puro
                        ai_stability = ai_decision.get('score', 50.0) / 100.0 # [SOTA v25.4] Usa score real para o filtro de confianca do auditor
                    elif (rsi < 30 and row['close'] < lower_bb) or (rsi > 70 and row['close'] > upper_bb):
                        logging.debug(f"💤 IA NEUTRA (Candidato Filtrado por Incerteza da IA/Meta): {ai_decision.get('uncertainty', 0)*100:.1f}% de incerteza")

                # --- [LEGACY] INTELIGÊNCIA DO SUCESSO: REGIME MAESTRO & SCALPING ADAPTATION ---
                else:
                    dir_prob = row['dir_prob']
                    aggressive = self.opt_params.get('aggressive_mode', False)
                    v_mult_eff = v_mult * 0.8 if aggressive else v_mult # Reduce volume spike req by 20%
                    
                    # Sinais V22 (Estratégia de Reversão de Volatilidade - Mean Reversion)
                    cond_rsi_buy = (rsi < 30)
                    cond_bb_buy = (row['close'] < lower_bb)
                    cond_rsi_sell = (rsi > 70)
                    cond_bb_sell = (row['close'] > upper_bb)
                    
                    # [SOTA v23] FLUXO ADAPTATIVO: Se ATR > 200, reduz threshold para 1.05
                    current_flux_thresh = self.opt_params['flux_imbalance_threshold']
                    if self.opt_params.get('adaptive_flux_active', False) and atr_current > 200:
                        current_flux_thresh = 1.05
                        
                    cond_vol_buy = (row['tick_volume'] > vol_sma * current_flux_thresh)
                    cond_vol_sell = (row['tick_volume'] > vol_sma * current_flux_thresh)

                    v22_reversion_buy = cond_rsi_buy and cond_bb_buy and cond_vol_buy
                    v22_reversion_sell = cond_rsi_sell and cond_bb_sell and cond_vol_sell

                    # 1. Regime Maestro (Trend Routing)
                    v22_trend_buy = v22_trend_sell = False
                    if dir_prob >= 0.8 and current_regime == 1: # Trend Mode
                        v22_trend_buy = (row['close'] > mid_bb) and (rsi > 50) and (rsi < 70) and vol_spike_eff
                        v22_trend_sell = (row['close'] < mid_bb) and (rsi < 50) and (rsi > 30) and vol_spike_eff
                        dyn_sl = self.opt_params['sl_dist'] * 1.5
                        dyn_tp = self.opt_params['tp_dist'] * 2.0
                        regime_tag = "TREND_MAESTRO"
                    
                    # 2. Amorphous Regimes (Scalping Adaptation)
                    v22_scalp_buy = v22_scalp_sell = False
                    if current_regime == 2: # Noise Mode
                        rsi_buy_thresh = 35 if aggressive else 25 # Loosened for relaxed analysis
                        rsi_sell_thresh = 65 if aggressive else 75
                        v22_scalp_buy = (row['close'] < lower_bb) and (rsi < rsi_buy_thresh) and (lower_wick > body * 0.4) and vol_spike_eff
                        v22_scalp_sell = (row['close'] > upper_bb) and (rsi > rsi_sell_thresh) and (upper_wick > body * 0.4) and vol_spike_eff
                        dyn_sl = self.opt_params['sl_dist'] * 0.5
                        dyn_tp = 100.0 if "WIN" in self.symbol else self.opt_params['tp_dist'] * 0.5
                        regime_tag = "NOISE_SCALP"
                    
                    elif current_regime == 3 or True: # Consolidation / Default Mode
                        rsi_buy_thresh = 35 if aggressive else 25
                        rsi_sell_thresh = 65 if aggressive else 75
                        v22_scalp_buy = (row['close'] < lower_bb) and (rsi < rsi_buy_thresh) and (lower_wick > body * 0.4) and vol_spike_eff
                        v22_scalp_sell = (row['close'] > upper_bb) and (rsi > rsi_sell_thresh) and (upper_wick > body * 0.4) and vol_spike_eff
                        dyn_sl = self.opt_params['sl_dist']
                        dyn_tp = 100.0 if "WIN" in self.symbol else self.opt_params['tp_dist'] * 0.5 
                        regime_tag = "CONSOL_SCALP"

                    v22_buy = v22_reversion_buy or v22_trend_buy or v22_scalp_buy
                    v22_sell = v22_reversion_sell or v22_trend_sell or v22_scalp_sell

                    ai_stability = min(0.99, 0.70) # Placeholder para fluxo legado

                # [PHASE 2] Audit Tracking Sync: Contamos candidatos v22 independentemente do modo
                # Isso permite ver no relatório de auditoria quantos sinais a IA vetou.
                if (rsi < 30 and row['close'] < lower_bb) or (rsi > 70 and row['close'] > upper_bb):
                    self.shadow_signals['v22_candidates'] += 1

                # Filtros Operacionais
                t_start = datetime.strptime(self.opt_params['start_time'], "%H:%M").time()
                t_end = datetime.strptime(self.opt_params['end_time'], "%H:%M").time()
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
                # Se estiver usando AI Core, respeitamos a decisão e estabilidade real do modelo
                if not use_ai_core:
                    # No modo legado, simulamos a confiança da IA com base no RSI e Volume (Proxy)
                    # Isso evita que o modo legado seja "perfeito" demais sem filtros.
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
                if not use_ai_core and self.opt_params.get('use_flux_filter', False):
                    flux_ok = row['tick_volume'] > (vol_sma * self.opt_params.get('flux_imbalance_threshold', 1.2))
                
                # Tracking Detalhado de Oportunidades Perdidas
                if v22_buy or v22_sell:
                    if not time_ok: self.shadow_signals['component_fail']['time'] = self.shadow_signals['component_fail'].get('time', 0) + 1
                    if not vol_stable: self.shadow_signals['component_fail']['vol_stable'] = self.shadow_signals['component_fail'].get('vol_stable', 0) + 1
                    if not cooldown_ok: self.shadow_signals['component_fail']['cooldown'] = self.shadow_signals['component_fail'].get('cooldown', 0) + 1
                    
                    if not ai_filter_ok:
                        self.shadow_signals['total_missed'] += 1
                        self.shadow_signals['filtered_by_ai'] += 1
                        if 0.70 <= ai_stability < 0.75: self.shadow_signals['tiers']['70-75'] += 1
                        elif 0.75 <= ai_stability < 0.80: self.shadow_signals['tiers']['75-80'] += 1
                        elif 0.80 <= ai_stability < 0.85: self.shadow_signals['tiers']['80-85'] += 1
                    
                    elif not flux_ok:
                        self.shadow_signals['total_missed'] += 1
                        self.shadow_signals['filtered_by_flux'] += 1
                    
                    elif not sentiment_ok:
                        self.shadow_signals['total_missed'] += 1
                        # self.shadow_signals['filtered_by_sentiment'] = ...

                if (v22_buy or v22_sell) and not (time_ok and risk_ok and limit_ok and vol_stable and cooldown_ok and ai_filter_ok and sentiment_ok and flux_ok):
                    logging.debug(f"⚠️ Signal BLOCKED at {row.name}: time={time_ok}, risk={risk_ok}, limit={limit_ok}, vol_stable={vol_stable}, cooldown={cooldown_ok}, ai={ai_filter_ok}, flux={flux_ok}, sent={sentiment_ok}")

                if (v22_buy or v22_sell) and time_ok and risk_ok and limit_ok and vol_stable and cooldown_ok and ai_filter_ok and sentiment_ok and flux_ok:
                    side = "buy" if v22_buy else "sell"
                    
                    # [MELHORIA H - V28] Veto de direção por tendência diária
                    if side == 'buy' and bias_veto_buy:
                        self.shadow_signals['total_missed'] = self.shadow_signals.get('total_missed', 0) + 1
                        self.shadow_signals['filtered_by_bias'] = self.shadow_signals.get('filtered_by_bias', 0) + 1
                        logging.debug(f"🚫 [H] BUY vetado por tendência diária de BAIXA em {row.name}")
                        continue
                    if side == 'sell' and bias_veto_sell:
                        self.shadow_signals['total_missed'] = self.shadow_signals.get('total_missed', 0) + 1
                        self.shadow_signals['filtered_by_bias'] = self.shadow_signals.get('filtered_by_bias', 0) + 1
                        logging.debug(f"🚫 [H] SELL vetado por tendência diária de ALTA em {row.name}")
                        continue

                    # --- [DYNAMIC ATR TARGETS V3] ---
                    # Replica a lógica do RiskManager ajustada por regime
                    tp_mult = self.opt_params.get('tp_mult_regime', 1.0)
                    sl_mult = self.opt_params.get('sl_mult_regime', 1.3)

                    if current_regime == 1: # Trend
                        tp_mult = 1.6 # Aumentado para 1.6x do ATR ou Alvo
                        tp_mult *= 1.2 # +20% se Ultra Tendência
                    elif current_regime == 0: # Lateral
                        tp_mult = 0.9 # Proteção
                    
                    # ATR atual já calculado no início do loop: row['atr_current']
                    # Se não houver alvos fixos, usa ATR. Se houver, usa o fixo como base de escala.
                    tp_fixed = self.opt_params.get('tp_dist', 550.0)
                    sl_fixed = self.opt_params.get('sl_dist', 150.0)
                    
                    raw_tp = tp_fixed * tp_mult if tp_fixed > 0 else atr_current * tp_mult
                    raw_sl = sl_fixed if sl_fixed > 0 else atr_current * sl_mult

                    if "WDO" in self.symbol or "DOL" in self.symbol:
                        dyn_tp_pts = max(5.0, min(30.0, raw_tp))
                        dyn_sl_pts = max(3.0, min(15.0, raw_sl))
                    else: # Padrão WIN
                        dyn_tp_pts = max(100.0, min(400.0, raw_tp))
                        dyn_sl_pts = max(100.0, min(300.0, raw_sl))

                    # [SOTA v5] Aplicação do Multiplicador de Precisão (Spread-Adjusted)
                    tp_multiplier = ai_decision.get('tp_multiplier', 1.0) if use_ai_core else 1.0
                    if tp_multiplier != 1.0:
                        dyn_tp_pts *= tp_multiplier
                    
                    sl = row['close'] - dyn_sl_pts if side == "buy" else row['close'] + dyn_sl_pts
                    tp = row['close'] + dyn_tp_pts if side == "buy" else row['close'] - dyn_tp_pts
                    
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
                    
                    # [SOTA v5] Aplicar multiplicador de assertividade da IA
                    ai_multiplier = ai_decision.get('lot_multiplier', 1.0) if use_ai_core else 1.0
                    target_lot = max(1, round(target_lot * ai_multiplier))
                    
                    self.position = {
                        'side': side,
                        'entry_price': row['close'],
                        'sl': sl,
                        'tp': tp,
                        'lots': target_lot,
                        'index': i,
                        'time': row.name,
                        'quantile_confidence': quantile_confidence if 'quantile_confidence' in locals() else "NORMAL",
                        'execution_mode': ai_decision.get('execution_mode', 'LIMIT') if 'ai_decision' in locals() else 'LIMIT'
                    }
                    self.daily_trade_count += 1
                    logging.info(f"🎯 V22 TRIGGER [{regime_tag}]: {side} @ {row['close']} | Lots: {target_lot}")
            
            # Atualizar Drawdown
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance
            current_dd = (self.peak_balance - self.balance) / self.peak_balance if self.peak_balance > 0 else 0
            if current_dd > self.max_drawdown:
                self.max_drawdown = current_dd

            self.equity_curve.append(self.balance)
            self.timestamps.append(row.name)

        logging.info("🏁 Simulação concluída.")
        if self.position:
            # Força o fechamento da última posição para fins de relatório final no backtest
            self._close_trade(row['close'], 'END_OF_SIM', row.name)
        return self.generate_report()

    def _close_trade(self, price, reason, exit_time):
        if not self.position: return
        pos = self.position
        pnl_points = (price - pos['entry_price']) if pos['side'] == 'buy' else (pos['entry_price'] - price)
        
        # Cálculo financeiro (Simplificado: WIN=0.20/pt, WDO=10.00/pt)
        mult = 0.20 if "WIN" in self.symbol else 10.0
        pnl_fin = pnl_points * pos['lots'] * mult
        
        # Auditoria Financeira
        self.balance += pnl_fin
        self.daily_pnl += pnl_fin
        
        # Registrar Trade
        trade_data = {
            'entry_time': pos['time'],
            'exit_time': exit_time,
            'side': pos['side'],
            'entry_price': pos['entry_price'],
            'exit_price': price,
            'lots': pos['lots'],
            'pnl_pts': pnl_points,
            'pnl_fin': pnl_fin,
            'reason': reason,
            'quantile_confidence': pos.get('quantile_confidence', 'NORMAL'),
            'execution_mode': pos.get('execution_mode', 'LIMIT')
        }
        self.trades.append(trade_data)
        
        # [v27] Sincronizar Resultado com Meta-Learner / Quarter-Kelly
        self.ai.record_result(pnl_fin)
        
        # Atualiza métricas de lote dinâmico tracker
        if pnl_fin > 0:
            self.consecutive_wins += 1
        else:
            self.consecutive_wins = 0
            
        self.position = None
        self.last_trade_time = exit_time # Garante cooldown no backtest
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
