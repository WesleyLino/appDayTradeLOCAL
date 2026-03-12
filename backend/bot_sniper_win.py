import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, time, date
from backend.mt5_bridge import MT5Bridge
from backend.risk_manager import RiskManager
from backend.ai_core import AICore
from backend.persistence import PersistenceManager
import pandas as pd
import numpy as np
import os
import json

# Configuração de Logs com Rotação Diária
log_handler = TimedRotatingFileHandler("backend/bot_sniper.log", when="midnight", interval=1, backupCount=7, encoding='utf-8')
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_formatter)

logger = logging.getLogger("SniperBot")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(logging.StreamHandler())

def sanitize_log(e):
    """Protege contra UnicodeDecodeError em logs de exceções."""
    try:
        return str(e).encode('utf-8', 'replace').decode('utf-8')
    except Exception:
        return "Erro desconhecido (falha de codificação)"

class SniperBotWIN:
    def __init__(self, bridge=None, risk=None, ai=None, dry_run=True, log_callback=None):
        self.bridge = bridge or MT5Bridge()
        self.log_callback = log_callback
        # [ANTIVIBE-CODING] - Calibração para saldo de R$ 500,00
        self.risk = risk or RiskManager(max_daily_loss=100.0, daily_trade_limit=3) 
        
        # Só define dry_run se o risk for novo ou se explicitamente passado
        if risk is None:
            self.risk.dry_run = dry_run
            
        self.ai = ai or AICore()
        self.persistence = PersistenceManager()
        
        self.symbol = None
        self.trade_count = 0
        self.last_date = None
        self.running = False
        self.last_total_trades = 0 # Para detectar fechamento de trades
        
        # Parâmetros Sniper (Carregados dinamicamente de v22_locked_params.json)
        self.start_time = None
        self.end_time = None
        self.rsi_period = 14
        self.flux_threshold = 0.95 
        self.vol_spike_mult = 1.0 
        self.consecutive_wins = 0 # Alpha Scaling tracker
        self.last_trade_time = None
        
        # [PAUSA PARCIAL] Controle de Volatilidade de Abertura
        self.dia_pausado_vol = False
        self.hl_abertura_cache = None
        self.dia_abertura_cache = None
        
        # Sincronização inicial
        self.risk.load_optimized_params("WIN$", "backend/v22_locked_params.json")
        self._load_params_from_risk("WIN$")
        
        logger.info(f"🛡️ [SOTA V22.5.1] Sincronização de Setup: OBI={self.flux_threshold}, RSI={self.rsi_period}, Vol={self.vol_spike_mult}, Janela={self.start_time}-{self.end_time}")
        
        self._load_state()

    def _load_params_from_risk(self, symbol_key):
        """Helper para carregar parâmetros do risk manager."""
        strategy = self.risk.dynamic_params.get(symbol_key, {})
        if not strategy: return
        
        self.flux_threshold = float(strategy.get("flux_imbalance_threshold", 0.95))
        self.rsi_period = int(strategy.get("rsi_period", 14))
        self.vol_spike_mult = float(strategy.get("vol_spike_mult", 1.0))
        
        raw_start = strategy.get("start_time", "10:00")
        raw_end = strategy.get("end_time", "17:15")
        self.start_time = datetime.strptime(raw_start, "%H:%M").time() if isinstance(raw_start, str) else time(10,0)
        self.end_time = datetime.strptime(raw_end, "%H:%M").time() if isinstance(raw_end, str) else time(17,15)
        
        self.rsi_dynamic_buy = float(strategy.get("rsi_dynamic_buy", 30))
        self.rsi_dynamic_sell = float(strategy.get("rsi_dynamic_sell", 70))
        self.rsi_dynamic_activation_atr = float(strategy.get("rsi_dynamic_activation_atr", 100.0))

        self.ai.use_h1_trend_bias = bool(strategy.get("use_h1_trend_bias", True))
        self.ai.h1_ma_period = int(strategy.get("h1_ma_period", 20))
        self.ai.confidence_relax_factor = float(strategy.get("confidence_relax_factor", 0.80))
        self.ai.atr_confidence_relax_trigger = float(strategy.get("atr_confidence_relax_trigger", 100.0))
        
        self.ai.confidence_buy_threshold = float(strategy.get("confidence_buy_threshold", 0.55)) * 100.0
        self.ai.confidence_sell_threshold = (1.0 - float(strategy.get("confidence_sell_threshold", 0.55))) * 100.0

    def _log_to_dashboard(self, msg, log_type="info"):
        if self.log_callback:
            self.log_callback(msg, log_type)
        
    async def get_flux_pressure(self):
        book = self.bridge.get_order_book(self.symbol)
        if not book or not book['bids'] or not book['asks']:
            return 1.0
        bid_vol = sum(item['volume'] for item in book['bids'][:5])
        ask_vol = sum(item['volume'] for item in book['asks'][:5])
        if bid_vol >= ask_vol:
            return float(bid_vol / max(1, ask_vol))
        else:
            return -float(ask_vol / max(1, bid_vol))

    def _load_state(self):
        tc = self.persistence.get_state("sniper_trade_count")
        ld = self.persistence.get_state("sniper_last_date")
        if tc: self.trade_count = int(tc)
        if ld: self.last_date = datetime.strptime(ld, "%Y-%m-%d").date()
        today = date.today()
        if self.last_date != today:
            self.trade_count = 0
            self.last_date = today
            self._save_state()

    def _save_state(self):
        self.persistence.save_state("sniper_trade_count", str(self.trade_count))
        self.persistence.save_state("sniper_last_date", str(self.last_date))

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 0.000001)
        return 100 - (100 / (1 + rs))

    def calculate_adx(self, df, period=14):
        plus_dm = df['high'].diff(); minus_dm = df['low'].diff()
        plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm > 0] = 0
        tr = pd.concat([df['high'] - df['low'], abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (abs(minus_dm).rolling(period).mean() / atr)
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di).replace(0, 1e-6)) * 100
        return dx.rolling(period).mean()

    def calculate_bollinger(self, series, period=20, std=2.0):
        sma = series.rolling(window=period).mean()
        std_dev = series.rolling(window=period).std()
        return sma + (std_dev * std), sma, sma - (std_dev * std)

    async def execute_trade(self, side, ai_decision=None, quantile_confidence="NORMAL", tp_multiplier=1.0, current_atr=None, regime=None, is_scaling_in=False):
        tick = self.bridge.mt5.symbol_info_tick(self.symbol)
        if not tick: return False
        limit_price = tick.ask if side == "buy" else tick.bid
        
        perf = self.risk.get_performance_metrics()
        wr = perf.get("win_rate", 55.0); pf = perf.get("profit_factor", 1.2)
        balance = getattr(self.risk, 'initial_balance', 500.0)
        kelly_volume = self.risk.calculate_quarter_kelly(balance, wr, pf, current_atr or 150.0)
        
        scaling = min(2, self.consecutive_wins)
        if is_scaling_in: lots = 1.0
        else:
            lots = round(kelly_volume) + scaling
            if quantile_confidence == "HIGH": lots += 1
            elif quantile_confidence == "VERY_HIGH": lots += 2
        lots = min(10, lots)
        
        if self.risk.dry_run:
            self.trade_count += 1
            self._save_state()
            self._log_to_dashboard(f"🧪 [SIMULAÇÃO] Sniper {side} @ {limit_price} ({lots} l)", "info")
            return True

        params = self.risk.get_order_params(self.symbol, self.bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else self.bridge.mt5.ORDER_TYPE_SELL_LIMIT, limit_price, lots, current_atr=current_atr, regime=regime, tp_multiplier=tp_multiplier)
        result = self.bridge.place_smart_order(self.symbol, params['type'], limit_price, lots, sl=params['sl'], tp=params['tp'], score=ai_decision.get("confidence_score", 0.0), uncertainty=ai_decision.get("uncertainty", 0.0), comment="SNIPER_SOTA_EXPERT")
        
        if result and result.retcode == self.bridge.mt5.TRADE_RETCODE_DONE:
            self.trade_count += 1
            self._save_state()
            return True
        return False

    async def _check_trade_results(self):
        stats = self.bridge.get_trading_performance()
        if stats['total_trades'] > self.last_total_trades:
            deals = self.bridge.mt5.history_deals_get(datetime.combine(date.today(), time(0,0)), datetime.now())
            if deals:
                out_deals = [d for d in deals if d.entry in [self.bridge.mt5.DEAL_ENTRY_OUT, self.bridge.mt5.DEAL_ENTRY_INOUT]]
                if out_deals:
                    profit = out_deals[-1].profit + out_deals[-1].swap + out_deals[-1].commission
                    if profit > 0: self.consecutive_wins += 1
                    else: self.consecutive_wins = 0
                    self._save_state()
            self.last_total_trades = stats['total_trades']

    async def manage_trailing_stop(self):
        positions = self.bridge.mt5.positions_get(symbol=self.symbol)
        if not positions: return
        df = self.bridge.get_market_data(self.symbol, n_candles=20)
        current_atr = float((df['high'] - df['low']).rolling(14).mean().iloc[-1]) if not df.empty else 150.0
        
        for pos in positions:
            if pos.sl == 0: continue
            elapsed = datetime.utcnow().timestamp() - pos.time
            current_profit = (pos.price_current - pos.price_open) if pos.type == self.bridge.mt5.POSITION_TYPE_BUY else (pos.price_open - pos.price_current)
            
            if self.risk.check_time_stop(elapsed, current_profit, current_atr=current_atr):
                if not self.risk.dry_run: self.bridge.close_position(pos.ticket)
                continue

            should_partial, p_vol = self.risk.check_scaling_out(self.symbol, pos.ticket, current_profit, pos.volume)
            if should_partial and not self.risk.dry_run:
                self.bridge.close_partial_position(pos.ticket, p_vol)
                continue

            if current_profit >= self.risk.be_trigger:
                new_sl = self.risk._quantize_price(self.symbol, pos.price_open + (self.risk.be_lock if pos.type == self.bridge.mt5.POSITION_TYPE_BUY else -self.risk.be_lock))
                if (pos.type == self.bridge.mt5.POSITION_TYPE_BUY and new_sl > pos.sl) or (pos.type == self.bridge.mt5.POSITION_TYPE_SELL and new_sl < pos.sl):
                    if not self.risk.dry_run: self.bridge.update_sltp(pos.ticket, new_sl, pos.tp)

            t_trigger, t_lock, t_step = self.risk.get_dynamic_trailing_params(current_atr)
            if current_profit >= t_trigger:
                potential_sl = self.risk._quantize_price(self.symbol, pos.price_current + (-(t_trigger-t_lock) if pos.type == self.bridge.mt5.POSITION_TYPE_BUY else (t_trigger-t_lock)))
                if (pos.type == self.bridge.mt5.POSITION_TYPE_BUY and potential_sl > pos.sl + t_step) or (pos.type == self.bridge.mt5.POSITION_TYPE_SELL and potential_sl < pos.sl - t_step):
                    if not self.risk.dry_run: self.bridge.update_sltp(pos.ticket, potential_sl, pos.tp)

    async def run(self):
        logger.info("🚀 Sniper Bot WIN v2.0 Live")
        if not self.bridge.connected and not self.bridge.connect(): return
        self.symbol = self.bridge.get_current_symbol("WIN")
        self.risk.load_optimized_params(self.symbol, "backend/v22_locked_params.json")
        self._load_params_from_risk(self.bridge._normalize_symbol(self.symbol))
        
        self.running = True
        while self.running:
            try:
                await self.manage_trailing_stop()
                await self._check_trade_results()
                self.bridge.cancel_stale_orders(symbol=self.symbol, timeout_seconds=60)
                
                now = datetime.now()
                if not self.bridge.check_connection(): await asyncio.sleep(5); continue

                acc = self.bridge.get_account_health()
                total_pnl = self.bridge.get_daily_realized_profit() + acc.get('profit', 0)
                if not self.risk.check_daily_loss(total_pnl)[0] or not self.risk.check_equity_kill_switch(acc.get('equity', 0), acc.get('balance', 0))[0]:
                    self.stop(); break

                if not (self.start_time <= now.time() <= self.end_time) or not self.risk.is_time_allowed():
                    await asyncio.sleep(1); continue

                if self.last_trade_time:
                    limit = 300 if self.persistence.get_state("last_quantile_confidence") == "VERY_HIGH" else 600
                    if (now - self.last_trade_time).total_seconds() < limit: await asyncio.sleep(1); continue

                df = self.bridge.get_market_data(self.symbol, n_candles=50)
                if df.empty or len(df) < 30: await asyncio.sleep(1); continue
                
                book = self.bridge.get_order_book(self.symbol)
                ticks_df = self.bridge.get_time_and_sales(self.symbol, n_ticks=100)
                
                try:
                    h1_data = self.bridge.get_market_data(self.symbol, n_candles=50, timeframe="H1")
                    if h1_data is not None: self.ai.update_h1_trend(h1_data)
                except: pass

                self.ai.micro_analyzer.analyze(book, ticks_df)
                weighted_ofi = self.ai.micro_analyzer.calculate_wen_ofi(book)
                
                df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)
                df['vol_sma'] = df['tick_volume'].rolling(20).mean()
                df['adx'] = self.calculate_adx(df, 14)
                df['bb_up'], df['bb_mid'], df['bb_down'] = self.calculate_bollinger(df['close'], 20, 2.0)
                
                last = df.iloc[-1]
                atr = float((df['high'] - df['low']).rolling(14).mean().iloc[-1])
                adx_val = float(last['adx']) if not np.isnan(last['adx']) else 0.0
                pressure = await self.get_flux_pressure()
                
                # Pausa Volatilidade
                if self.dia_abertura_cache != now.date():
                    self.dia_pausado_vol = False; self.hl_abertura_cache = None; self.dia_abertura_cache = now.date()
                if self.hl_abertura_cache is None:
                    inicio = datetime(now.year, now.month, now.day, 9, 0, 0)
                    r = self.bridge.mt5.copy_rates_range(self.symbol, self.bridge.mt5.TIMEFRAME_M1, inicio, now)
                    if r is not None and len(r) >= 10:
                        hl = pd.DataFrame(r)['high'].iloc[:10] - pd.DataFrame(r)['low'].iloc[:10]
                        self.hl_abertura_cache = float(hl.mean())
                        if self.hl_abertura_cache > 250.0: self.dia_pausado_vol = True
                
                rsi_buy = self.rsi_dynamic_buy if atr >= self.rsi_dynamic_activation_atr else 30.0
                rsi_sell = self.rsi_dynamic_sell if atr >= self.rsi_dynamic_activation_atr else 70.0
                if self.ai.use_h1_trend_bias and self.ai.h1_trend == -1: rsi_buy = 0.0

                flux_mult = self.vol_spike_mult if atr < 200 else 1.05
                c_buy = last['rsi'] < rsi_buy and last['tick_volume'] > (last['vol_sma'] * flux_mult)
                c_sell = last['rsi'] > rsi_sell and last['tick_volume'] > (last['vol_sma'] * flux_mult)
                
                if c_buy or c_sell:
                    side = "buy" if c_buy else "sell"
                    if (side == "buy" and pressure > self.flux_threshold) or (side == "sell" and pressure < -self.flux_threshold):
                        patchtst_score = await self.ai.predict_with_patchtst(self.ai.inference_engine, df)
                        sentiment = await self.ai.update_sentiment() if getattr(self.risk, 'enable_news_filter', True) else 0.0
                        regime = self.ai.identify_market_regime(df, self.ai.h1_trend, atr, adx_val, last['bb_up'], last['bb_down'], last['bb_mid'])
                        m_ctx = self._load_market_context()
                        bc_score = m_ctx.get("synthetic_index", 0.0)
                        
                        decision = self.ai.calculate_decision(obi=pressure, sentiment=sentiment, patchtst_score=patchtst_score, regime=regime, atr=atr, volatility=0.1, hour=now.hour, minute=now.minute, ofi=weighted_ofi, current_price=last['close'], spread=self.bridge.get_latency_and_spread(self.symbol)[1], sma_20=last['bb_mid'], bluechip_score=bc_score)
                        
                        if not self.risk.is_macro_allowed("BUY" if side == "buy" else "SELL", bc_score): decision["direction"] = "WAIT"
                        if self.dia_pausado_vol: decision["direction"] = "WAIT"

                        if decision["direction"] in ["COMPRA", "VENDA"]:
                            positions = self.bridge.mt5.positions_get(symbol=self.symbol)
                            can_trade = True
                            if positions:
                                p = positions[0]; prof = (p.price_current - p.price_open) if p.type == 0 else (p.price_open - p.price_current)
                                if not self.risk.allow_pyramiding(prof, pressure, sum(pos.volume for pos in positions), symbol=self.symbol): can_trade = False
                            
                            if can_trade:
                                if await self.execute_trade(side, ai_decision=decision, quantile_confidence=decision["quantile_confidence"], tp_multiplier=decision.get("tp_multiplier", 1.0), current_atr=atr, is_scaling_in=len(positions)>0):
                                    self.persistence.save_state("last_quantile_confidence", decision["quantile_confidence"])
                                    self.last_trade_time = now
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Erro Sniper: {sanitize_log(e)}"); await asyncio.sleep(2)

    def _load_market_context(self):
        ctx_path = os.path.join("data", "market_context.json")
        try:
            if os.path.exists(ctx_path):
                with open(ctx_path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
        return {}

    def stop(self):
        self.running = False; self.bridge.disconnect()

if __name__ == "__main__":
    bot = SniperBotWIN(dry_run=True); asyncio.run(bot.run())
