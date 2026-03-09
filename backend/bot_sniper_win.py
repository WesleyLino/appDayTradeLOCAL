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
        
        # Parâmetros Sniper (Otimizados em Backtest)
        self.start_time = time(10, 0)
        self.end_time = time(15, 0) # Expandido para janela da tarde
        self.consecutive_wins = 0 # Alpha Scaling tracker
        self.rsi_period = 14
        self.flux_threshold = 1.2 # Sniper Pro: 1.2x (Validated)
        self.vol_spike_mult = 1.2 # Sniper Pro: 1.2x (Validated)
        self.last_trade_time = None
        # [PAUSA PARCIAL] Controle de Volatilidade de Abertura (H-L Extremo)
        self.dia_pausado_vol = False
        self.hl_abertura_cache = None
        self.dia_abertura_cache = None
        
        # [FASE 28] Sincronização de Parâmetros Calibrados (Grid Search)
        self.risk.load_optimized_params("WIN", "best_params_WIN.json")
        self.risk.load_optimized_params("WINJ26", "best_params_WIN.json") # Fallback para símbolo específico
        
        self._load_state()

    def _log_to_dashboard(self, msg, log_type="info"):
        """Envia mensagem para o Dashboard se o callback estiver configurado."""
        if self.log_callback:
            self.log_callback(msg, log_type)
        
    async def get_flux_pressure(self):
        """Calcula a pressão de compra/venda baseada no Book L2."""
        book = self.bridge.get_order_book(self.symbol)
        if not book or not book['bids'] or not book['asks']:
            return 1.0
        
        # Filtro de Volume Bruto Top 5
        bid_vol = sum(item['volume'] for item in book['bids'][:5])
        ask_vol = sum(item['volume'] for item in book['asks'][:5])
        
        # Formula Institucional (Ratio): Bid/Ask para compatibilidade com gatilhos > 1.0
        if bid_vol >= ask_vol:
            return float(bid_vol / max(1, ask_vol))
        else:
            return -float(ask_vol / max(1, bid_vol))

    def _load_state(self):
        """Carrega estado persistido do bot."""
        tc = self.persistence.get_state("sniper_trade_count")
        ld = self.persistence.get_state("sniper_last_date")
        cw = self.persistence.get_state("sniper_consecutive_wins")
        
        if tc: self.trade_count = int(tc)
        if ld: self.last_date = datetime.strptime(ld, "%Y-%m-%d").date()
        if cw: self.consecutive_wins = int(cw)
        
        # Reset diário
        today = date.today()
        if self.last_date != today:
            logger.info(f"📅 Novo dia detectado. Resetando trades: {self.last_date} -> {today}")
            self.trade_count = 0
            self.last_date = today
            self._save_state()

    def _save_state(self):
        """Salva estado atual do bot."""
        self.persistence.save_state("sniper_trade_count", str(self.trade_count))
        self.persistence.save_state("sniper_last_date", str(self.last_date))
        self.persistence.save_state("sniper_consecutive_wins", str(self.consecutive_wins))

    def calculate_rsi(self, series, period=14):
        """Cálculo robusto de RSI para evitar divisão por zero."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # Proteção contra divisão por zero
        rs = gain / loss.replace(0, 0.000001)
        return 100 - (100 / (1 + rs))

    async def execute_trade(self, side, ai_decision=None, quantile_confidence="NORMAL", tp_multiplier=1.0, current_atr=None, regime=None, is_scaling_in=False):
        """Coordena o envio de ORDEM LIMITADA com dimensionamento de IA."""
        tick = self.bridge.mt5.symbol_info_tick(self.symbol)
        if not tick: return False
        
        limit_price = tick.ask if side == "buy" else tick.bid
        
        # [HFT ELITE] Quarter-Kelly Scaling (Fase 2)
        # Puxa métricas reais de performance para dimensionar o lote
        perf = self.risk.get_performance_metrics()
        wr = perf.get("win_rate", 55.0) 
        pf = perf.get("profit_factor", 1.2)
        
        # Saldo base para Kelly - [ANTIVIBE-CODING]
        balance = getattr(self.risk, 'initial_balance', 500.0)
        kelly_volume = self.risk.calculate_quarter_kelly(balance, wr, pf, current_atr or 150.0)
        
        # Escalonamento Alpha (Vitórias consecutivas)
        scaling = min(2, self.consecutive_wins)
        
        # Volume Base (Kelly) + Scaling
        if is_scaling_in:
            lots = 1.0 # [INSTITUCIONAL] Lote reduzido para piramidação (mão pequena)
            logger.info(f"💎 [PIRAMIDAÇÃO] Executando Scaling In: +{lots} lote.")
        else:
            lots = round(kelly_volume) + scaling
            
            # Boost por Confiança da IA (Fase 22)
            if quantile_confidence == "HIGH": lots += 1
            elif quantile_confidence == "VERY_HIGH": lots += 2
        
        # Limite Master (Capped)
        lots = min(10, lots)
        
        if not is_scaling_in:
            logger.info(f"[QUARTER-KELLY] WR={wr}% PF={pf} -> VolKelly={kelly_volume:.2f} | Alpha={scaling} Confiança={quantile_confidence} -> Total={lots}")
        
        if self.risk.dry_run:
            msg = f"🧪 [SIMULAÇÃO] Sniper {side.upper()} (LIMIT) disparado @ {limit_price} com {lots} lotes"
            logger.info(msg)
            self._log_to_dashboard(msg, "info")
            self.trade_count += 1
            self._save_state()
            return True

        params = self.risk.get_order_params(
            self.symbol, 
            self.bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else self.bridge.mt5.ORDER_TYPE_SELL_LIMIT,
            limit_price, 
            lots, 
            current_atr=current_atr,
            regime=regime,
            tp_multiplier=tp_multiplier
        )

        # [v30 - SMART ROUTING]
        # Decide entre LIMIT ou MARKET com base no Score da IA e Incerteza
        score = ai_decision.get("confidence_score", 0.0) if ai_decision else 0.0
        uncertainty = ai_decision.get("uncertainty", 0.0) if ai_decision else 0.0

        result = self.bridge.place_smart_order(
            self.symbol, params['type'], limit_price, lots, 
            sl=params['sl'], tp=params['tp'],
            score=score, uncertainty=uncertainty,
            comment="SNIPER_SOTA_PYRAMID" if is_scaling_in else "SNIPER_SOTA_SMART"
        )
        
        if result and result.retcode == self.bridge.mt5.TRADE_RETCODE_DONE:
            order_ticket = result.order
            timeout_sec = self.risk.alpha_fade_timeout
            iterations = int(timeout_sec / 0.5)
            
            logger.info(f"⏳ [ORDEM ABERTA] {order_ticket} @ {limit_price}. Lotes: {lots}. TTL: {timeout_sec}s...")
            
            for _ in range(iterations):
                await asyncio.sleep(0.5)
                status = self.bridge.check_order_status(order_ticket)
                if status == "FILLED":
                    self.trade_count += 1
                    self._save_state()
                    msg = f"🎯 [EXECUÇÃO] {side.upper()} {lots} @ {limit_price}"
                    logger.info(msg)
                    self._log_to_dashboard(msg, "success")
                    return True
                elif status == "CANCELED":
                    return False
            
            if self.bridge.cancel_order(order_ticket):
                logger.info(f"🛡️ [CANCELADA/TTL] Ordem {order_ticket} (Momento passou).")
            else:
                if self.bridge.check_order_status(order_ticket) == "FILLED":
                    self.trade_count += 1
                    self._save_state()
                    return True
            return False
        else:
            msg = result.comment if result else "Nenhum"
            logger.error(f"❌ [REJEITADA] Falha: {msg}")
            return False

    async def _check_trade_results(self):
        """Monitora o histórico para atualizar vitórias consecutivas (Alpha Scaling)."""
        stats = self.bridge.get_trading_performance()
        if stats['total_trades'] > self.last_total_trades:
            deals = self.bridge.mt5.history_deals_get(datetime.combine(date.today(), time(0,0)), datetime.now())
            if deals:
                out_deals = [d for d in deals if d.entry in [self.bridge.mt5.DEAL_ENTRY_OUT, self.bridge.mt5.DEAL_ENTRY_INOUT]]
                if out_deals:
                    last_deal = out_deals[-1]
                    profit = last_deal.profit + last_deal.swap + last_deal.commission
                    if profit > 0:
                        self.consecutive_wins += 1
                        logger.info(f"✨ [LUCRO] Vitória! +{profit:.2f} | Alpha: {self.consecutive_wins}")
                    else:
                        self.consecutive_wins = 0
                        logger.info("📉 [PREJUÍZO] Resetando Alpha Scaling.")
                    self._save_state()
            self.last_total_trades = stats['total_trades']

    async def manage_trailing_stop(self):
        """Monitora posições e aplica Trailing Stop, Breakeven e Time-Stop (HFT Master)."""
        positions = self.bridge.mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        # Busca ATR atual para cálculos dinâmicos
        df = self.bridge.get_market_data(self.symbol, n_candles=20)
        current_atr = float((df['high'] - df['low']).rolling(14).mean().iloc[-1]) if not df.empty else 150.0

        for pos in positions:
            if pos.sl == 0: continue

            now_ts = datetime.utcnow().timestamp()
            elapsed = now_ts - pos.time
            
            if pos.type == self.bridge.mt5.POSITION_TYPE_BUY:
                current_profit = pos.price_current - pos.price_open
            else:
                current_profit = pos.price_open - pos.price_current
            
            # 0. Velocity Limit (Drawdown Acelerado)
            v_ok, v_msg = self.risk.check_velocity_limit(current_profit, elapsed)
            if v_ok:
                logger.warning(f"🛡️ [VELOCITY] {v_msg}: {pos.ticket}")
                if not self.risk.dry_run: self.bridge.close_position(pos.ticket)
                continue

            # 0.1 [v50 - MASTER] Time-Based Stop Elástico (3-5 min)
            if self.risk.check_time_stop(elapsed, current_profit, current_atr=current_atr):
                logger.warning(f"⏰ [TIME-STOP MASTER] Posição {pos.ticket} estagnada ({elapsed/60:.1f} min).")
                if not self.risk.dry_run: self.bridge.close_position(pos.ticket)
                continue

            # 0.2 [v30 - INSTITUCIONAL] Scaling Out (Parcial)
            should_partial, p_vol = self.risk.check_scaling_out(self.symbol, pos.ticket, current_profit, pos.volume)
            if should_partial:
                if not self.risk.dry_run:
                    self.bridge.close_partial_position(pos.ticket, p_vol)
                else:
                    logger.info(f"🧪 [SIMULAÇÃO] Executando PARCIAL de {p_vol} lotes no ticket {pos.ticket}")
                continue

            # 1. Breakeven
            if pos.type == self.bridge.mt5.POSITION_TYPE_BUY:
                if current_profit >= self.risk.be_trigger and pos.sl < pos.price_open:
                    new_sl = self.risk._quantize_price(self.symbol, pos.price_open + self.risk.be_lock)
                    if not self.risk.dry_run:
                        self.bridge.update_sltp(pos.ticket, new_sl, pos.tp)
                        logger.info(f"⚡ [BREAKEVEN] COMPRA protegida: {new_sl}")
                
                # 2. Trailing Stop Dinâmico (Master ATR-Based)
                t_trigger, t_lock, t_step = self.risk.get_dynamic_trailing_params(current_atr)
                if current_profit >= t_trigger:
                    potential_sl = self.risk._quantize_price(self.symbol, pos.price_current - (t_trigger - t_lock))
                    if potential_sl > pos.sl + t_step:
                        if not self.risk.dry_run:
                            self.bridge.update_sltp(pos.ticket, potential_sl, pos.tp)
                            logger.info(f"⚡ [TRAILING MASTER] COMPRA movida: {potential_sl} (ATR: {current_atr:.1f})")

            elif pos.type == self.bridge.mt5.POSITION_TYPE_SELL:
                if current_profit >= self.risk.be_trigger and pos.sl > pos.price_open:
                    new_sl = self.risk._quantize_price(self.symbol, pos.price_open - self.risk.be_lock)
                    if not self.risk.dry_run:
                        self.bridge.update_sltp(pos.ticket, new_sl, pos.tp)
                        logger.info(f"⚡ [BREAKEVEN] VENDA protegida: {new_sl}")

                # 2. Trailing Stop Dinâmico (Master ATR-Based)
                t_trigger, t_lock, t_step = self.risk.get_dynamic_trailing_params(current_atr)
                if current_profit >= t_trigger:
                    potential_sl = self.risk._quantize_price(self.symbol, pos.price_current + (t_trigger - t_lock))
                    if potential_sl < pos.sl - t_step:
                        if not self.risk.dry_run:
                            self.bridge.update_sltp(pos.ticket, potential_sl, pos.tp)
                            logger.info(f"⚡ [TRAILING MASTER] VENDA movida: {potential_sl} (ATR: {current_atr:.1f})")

    async def run(self):
        msg_init = "🚀 Sniper Bot WIN v2.0 (Quarter-Kelly & Time-Stops)"
        logger.info(msg_init)
        self._log_to_dashboard(msg_init, "info")
        if not self.bridge.connected and not self.bridge.connect():
            return

        self.symbol = self.bridge.get_current_symbol("WIN")
        
        # Carregar Params SOTA
        if self.symbol in self.risk.dynamic_params:
            d = self.risk.dynamic_params[self.symbol]
            if d.get("rsi_period"): self.rsi_period = int(d["rsi_period"])
            if d.get("vol_spike_mult"): self.vol_spike_mult = float(d["vol_spike_mult"])
        
        self.running = True
        while self.running:
            try:
                await self.manage_trailing_stop()
                await self._check_trade_results()
                self.bridge.cancel_stale_orders(symbol=self.symbol, timeout_seconds=self.risk.alpha_fade_timeout)

                now = datetime.now()
                if self.last_date != now.date():
                    self.trade_count = 0
                    self.last_date = now.date()
                    self._save_state()

                if not self.bridge.check_connection():
                    await asyncio.sleep(5)
                    continue

                # Risco Ambiental
                ping, spread = self.bridge.get_latency_and_spread(self.symbol)
                env_ok, env_msg = self.risk.validate_environmental_risk(ping, spread)
                if not env_ok:
                    await asyncio.sleep(1)
                    continue
                
                # Kill Switch Equity & Daily Profit
                acc = self.bridge.get_account_health()
                
                # [ANTIVIBE-CODING] - Calcula PnL Diário Realizado + Flutuante
                daily_realized = self.bridge.get_daily_realized_profit()
                total_pnl = daily_realized + acc.get('profit', 0)
                
                # 1. Trava de Perda Diária (Acumulada)
                pnl_ok, pnl_msg = self.risk.check_daily_loss(total_pnl)
                if not pnl_ok:
                    logger.warning(pnl_msg)
                    self.stop()
                    break
                
                # 2. Kill Switch (Pânico por Drawdown Flutuante Extremo)
                # Usa o Saldo (Balance) real como referência dinâmica
                starting_balance = acc.get('balance', 0)
                eq_ok, eq_msg = self.risk.check_equity_kill_switch(acc.get('equity', 0), starting_balance)
                if not eq_ok:
                    logger.warning(eq_msg)
                    self.stop()
                    break

                if not (self.start_time <= now.time() <= self.end_time) or not self.risk.is_time_allowed():
                    await asyncio.sleep(30)
                    continue

                # Cooldown
                if self.last_trade_time:
                    elapsed = (now - self.last_trade_time).total_seconds()
                    limit = 300 if self.persistence.get_state("last_quantile_confidence") == "VERY_HIGH" else 600
                    if elapsed < limit:
                        await asyncio.sleep(1)
                        continue

                # Sinais
                df = self.bridge.get_market_data(self.symbol, n_candles=50)
                if df.empty or len(df) < 30:
                    await asyncio.sleep(1)
                    continue
                
                # [HFT ELITE - V40] Microestrutura & Fluxo Sincronizado
                book = self.bridge.get_order_book(self.symbol)
                ticks_df = self.bridge.get_time_and_sales(self.symbol, n_ticks=100)
                
                # Sincroniza o analisador para habilitar o Veto de Divergência de CVD
                self.ai.micro_analyzer.analyze(book, ticks_df)
                weighted_ofi = self.ai.micro_analyzer.calculate_wen_ofi(book)
                
                df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)
                df['vol_sma'] = df['tick_volume'].rolling(20).mean()
                last = df.iloc[-1]
                
                atr = float((df['high'] - df['low']).rolling(14).mean().iloc[-1])
                pressure = await self.get_flux_pressure() # Agora retorna Ratio escala > 1.0
                
                # [PAUSA PARCIAL - 03/03/2026] VERIFICA VOLATILIDADE M1 NA ABERTURA (Live)
                hoje = now.date()
                if self.dia_abertura_cache != hoje:
                    self.dia_pausado_vol = False
                    self.hl_abertura_cache = None
                    self.dia_abertura_cache = hoje

                if self.hl_abertura_cache is None:
                    inicio_dia = datetime(now.year, now.month, now.day, 9, 0, 0)
                    try:
                        rates_hoje = self.bridge.mt5.copy_rates_range(self.symbol, self.bridge.mt5.TIMEFRAME_M1, inicio_dia, now)
                        if rates_hoje is not None and len(rates_hoje) >= 10:
                            df_hoje = pd.DataFrame(rates_hoje)
                            if 'high' in df_hoje.columns and 'low' in df_hoje.columns:
                                hl_10 = df_hoje['high'].iloc[:10] - df_hoje['low'].iloc[:10]
                                self.hl_abertura_cache = float(hl_10.mean())
                                if self.hl_abertura_cache > 250.0:
                                    self.dia_pausado_vol = True
                                    msg_vol = f"⚠️ [PAUSA VOLATILIDADE] H-L abertura={self.hl_abertura_cache:.1f}pts (limiar=250.0). Operações PAUSADAS."
                                    logger.warning(msg_vol)
                                    self._log_to_dashboard(msg_vol, "warning")
                            else:
                                logger.debug("Início do dia aguardando colunas OHLC consistentes.")
                    except Exception as e:
                        logger.error(f"Erro ao calcular H-L abertura (Live): {e}")

                if self.dia_pausado_vol and 0 < atr < 80.0:
                    self.dia_pausado_vol = False
                    logger.info(f"✅ [PAUSA VOLATILIDADE] ATR={atr:.1f}pts normalizou. Retomando operações.")
                
                # [SOTA] Filtro de Fluxo Adaptativo
                flux_mult = self.vol_spike_mult if atr < 200 else 1.05
                comprar_cond = last['rsi'] < 30 and last['tick_volume'] > (last['vol_sma'] * flux_mult)
                vender_cond = last['rsi'] > 70 and last['tick_volume'] > (last['vol_sma'] * flux_mult)
                
                # [ANTIVIBE-CODING] Carregamento de Contexto Macro para Veto
                market_ctx = self._load_market_context()
                synthetic_idx = market_ctx.get("synthetic_index", 0.0)
                
                if comprar_cond or vender_cond:
                    side = "buy" if comprar_cond else "sell"
                    if (side == "buy" and pressure > 1.2) or (side == "sell" and pressure < -1.2):
                        patchtst_score = await self.ai.predict_with_patchtst(self.ai.inference_engine, df)
                        # [ANTIVIBE-CODING] Override de Controle Manual de Notícias
                        effective_sentiment = await self.ai.update_sentiment() if (getattr(self.risk, 'enable_news_filter', True)) else 0.0

                        ai_decision = self.ai.calculate_decision(
                            obi=pressure, 
                            sentiment=effective_sentiment, 
                            patchtst_score=patchtst_score, 
                            regime=self.ai.detect_regime(0.1, pressure),
                            atr=atr, 
                            volatility=0.1, 
                            hour=now.hour, 
                            minute=now.minute,
                            ofi=weighted_ofi, # Passando OFI real para o Veto de VWAP
                            current_price=last['close']
                        )
                        
                        # [ANTIVIBE-CODING] Veto Macro Sincronizado
                        direction = "BUY" if side == "buy" else "SELL"
                        if not self.risk.is_macro_allowed(direction, synthetic_idx):
                            ai_decision["direction"] = "WAIT"
                            ai_decision["reason"] = f"VETO_MACRO: Blue Chips {synthetic_idx:.2f}%"
                        
                        if self.dia_pausado_vol:
                            ai_decision["direction"] = "WAIT"
                            ai_decision["reason"] = "ATR_DIA_PAUSADO"

                        if (side == "buy" and ai_decision["direction"] == "COMPRA") or (side == "sell" and ai_decision["direction"] == "VENDA"):
                            # [v40 - PIRAMIDAÇÃO]
                            positions = self.bridge.mt5.positions_get(symbol=self.symbol)
                            can_trade = True
                            if positions:
                                pos = positions[0]
                                profit_pts = pos.price_current - pos.price_open if pos.type == self.bridge.mt5.POSITION_TYPE_BUY else pos.price_open - pos.price_current
                                total_vol = sum(p.volume for p in positions)
                                if not self.risk.allow_pyramiding(profit_pts, pressure, total_vol, symbol=self.symbol):
                                    can_trade = False
                                    logger.info(f"⏳ [BLOQUEIO] Piramidação não permitida: Lucro {profit_pts:.1f} pts / Vol Total {total_vol}")

                            if can_trade:
                                is_scaling_in = len(positions) > 0
                                if await self.execute_trade(side, ai_decision=ai_decision, quantile_confidence=ai_decision["quantile_confidence"], tp_multiplier=ai_decision.get("tp_multiplier", 1.0), current_atr=atr, is_scaling_in=is_scaling_in):
                                    self.persistence.save_state("last_quantile_confidence", ai_decision["quantile_confidence"])
                                    self.last_trade_time = now

                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Erro Sniper: {sanitize_log(e)}")
                await asyncio.sleep(2)

    def _load_market_context(self):
        """[ANTIVIBE-CODING] Método auxiliar para carregar contexto global."""
        ctx_path = os.path.join("data", "market_context.json")
        if os.path.exists(ctx_path):
            try:
                with open(ctx_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    def stop(self):
        self.running = False
        self.bridge.disconnect()

if __name__ == "__main__":
    bot = SniperBotWIN(dry_run=True)
    asyncio.run(bot.run())
