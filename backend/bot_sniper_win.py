import asyncio
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, time as dtime, date
from backend.mt5_bridge import MT5Bridge
from backend.risk_manager import RiskManager
from backend.ai_core import AICore
from backend.persistence import PersistenceManager
import pandas as pd
import numpy as np
import os
import json

# Configuração de Logs com Rotação Diária
log_handler = TimedRotatingFileHandler(
    "backend/bot_sniper.log",
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
)
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
log_handler.setFormatter(log_formatter)

logger = logging.getLogger("SniperBot")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(logging.StreamHandler())


def sanitize_log(e):
    """Protege contra UnicodeDecodeError em logs de exceções."""
    try:
        return str(e).encode("utf-8", "replace").decode("utf-8")
    except Exception:
        return "Erro desconhecido (falha de codificação)"


class SniperBotWIN:
    def __init__(
        self, bridge=None, risk=None, ai=None, dry_run=True, log_callback=None
    ):
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
        self.logger = logger
        self.last_total_trades = 0  # Para detectar fechamento de trades

        # Parâmetros Sniper (Carregados dinamicamente de v22_locked_params.json)
        self.start_time = None
        self.end_time = None
        self.rsi_period = 14
        self.flux_threshold = 0.95
        self.vol_spike_mult = 1.0
        self.consecutive_wins = 0  # Alpha Scaling tracker
        self.last_trade_time = None
        self._last_close_time = 0.0   # [FIX] Timestamp do último fechamento pelo sniper
        self._last_closed_ticket = None  # [FIX] Ticket fechado mais recente pelo sniper
        self._order_lock_until = 0.0  # [FIX #DUAL-BOT-LOCK] Lock local do Sniper
        self.SNIPER_ORDER_LOCK_SEC = 12.0  # Igual ao GLOBAL_ORDER_LOCK_SEC do main.py
        self.MIN_ELAPSED_BEFORE_TRAILING = 30.0  # [FIX #NEW-POS-GUARD] Aguarda 30s antes de gerenciar posição nova

        self.consecutive_buy_losses = 0
        self.consecutive_sell_losses = 0
        self.buy_cooldown_until = 0.0
        self.sell_cooldown_until = 0.0

        # [PAUSA PARCIAL] Controle de Volatilidade de Abertura
        self.dia_pausado_vol = False
        self.hl_abertura_cache = None
        self.dia_abertura_cache = None
        self.current_regime = 0  # [v23.1] Cache de regime para monitoramento de posição

        # Sincronização inicial v24
        self.risk.load_optimized_params("WIN$", "backend/v24_locked_params.json")
        self._load_params_from_risk("WIN$")

        logger.info(
            f"🛡️ [SOTA v24.0] Sniper v24 Ativado: OBI={self.flux_threshold}, RSI={self.rsi_period}, Vol={self.vol_spike_mult}, Janela={self.start_time}-{self.end_time}"
        )

        self._load_state()

    def _load_params_from_risk(self, symbol_key):
        """Helper para carregar parâmetros do risk manager."""
        strategy = self.risk.dynamic_params.get(symbol_key, {})
        if not strategy:
            return

        self.flux_threshold = float(strategy.get("flux_imbalance_threshold") or 0.95)
        self.rsi_period = int(strategy.get("rsi_period") or 14)
        self.vol_spike_mult = float(strategy.get("vol_spike_mult") or 1.0)

        raw_start = strategy.get("start_time", "10:00")
        raw_end = strategy.get("end_time", "17:15")
        self.start_time = (
            datetime.strptime(raw_start, "%H:%M").time()
            if isinstance(raw_start, str)
            else dtime(10, 0)
        )
        self.end_time = (
            datetime.strptime(raw_end, "%H:%M").time()
            if isinstance(raw_end, str)
            else dtime(17, 15)
        )

        self.rsi_dynamic_buy = float(strategy.get("rsi_dynamic_buy") or 30)
        self.rsi_dynamic_sell = float(strategy.get("rsi_dynamic_sell") or 70)
        self.rsi_dynamic_activation_atr = float(
            strategy.get("rsi_dynamic_activation_atr") or 100.0
        )

        self.ai.use_h1_trend_bias = bool(strategy.get("use_h1_trend_bias", True))
        self.ai.h1_ma_period = int(strategy.get("h1_ma_period", 20))
        self.ai.confidence_relax_factor = float(
            strategy.get("confidence_relax_factor", 0.80)
        )
        self.ai.atr_confidence_relax_trigger = float(
            strategy.get("atr_confidence_relax_trigger", 100.0)
        )

        c_buy = float(strategy.get("confidence_buy_threshold") or 56.5)
        self.ai.confidence_buy_threshold = c_buy * 100.0 if c_buy <= 1.0 else c_buy
        
        c_sell = float(strategy.get("confidence_sell_threshold") or 43.5)
        self.ai.confidence_sell_threshold = c_sell * 100.0 if c_sell <= 1.0 else c_sell
        self.ai.uncertainty_threshold = float(
            strategy.get("uncertainty_threshold") or 0.4
        )
        # [v24.5] Sincronização Dinâmica de Momentum e Filtro BlueChip
        # [v24.6-FIX] Fallback alinhado ao JSON (72.0). Usa .get(key, default) para não
        # substituir indevidamente caso o valor seja 0.0 (improvável mas seguro).
        self.ai.momentum_bypass_threshold = float(
            strategy.get("momentum_bypass_threshold", 72.0) or 72.0
        )
        self.ai.bluechip_bias_threshold = float(
            strategy.get("bluechip_bias_threshold") or 0.25
        )
        # [v24.6-DYNAMIC] Vinculado ao v24_locked_params.json — recarregado a cada ciclo via load_optimized_params
        _use_bc = strategy.get("use_bluechip_bias", False)
        self.ai.use_bluechip_bias = bool(_use_bc)
        logging.debug(
            f"[CFG-SYNC] use_bluechip_bias={self.ai.use_bluechip_bias} "
            f"(fonte: v24_locked_params.json → dynamic_params)"
        )
        # [v24.6-FIX] Sincroniza obi_absorption_threshold do JSON para o ai_core (Fix #4)
        # Antes: hardcoded 1.8 no ai_core → JSON ignorado. Agora: lido e aplicado a cada ciclo.
        self.ai.obi_absorption_threshold = float(
            strategy.get("obi_absorption_threshold") or 1.8
        )
        logging.info(
            f"[CFG-SYNC] momentum_bypass={self.ai.momentum_bypass_threshold:.1f} | "
            f"obi_absorption={self.ai.obi_absorption_threshold:.1f} | "
            f"use_bluechip={self.ai.use_bluechip_bias} "
            f"(fonte: v24_locked_params.json)"
        )

    def _log_to_dashboard(self, msg, log_type="info"):
        if self.log_callback:
            self.log_callback(msg, log_type)

    async def get_flux_pressure(self):
        book = self.bridge.get_order_book(self.symbol)
        if not book or not book["bids"] or not book["asks"]:
            return 1.0
        bid_vol = sum(item["volume"] for item in book["bids"][:5])
        ask_vol = sum(item["volume"] for item in book["asks"][:5])
        if bid_vol >= ask_vol:
            return float(bid_vol / max(1, ask_vol))
        else:
            return -float(ask_vol / max(1, bid_vol))

    def _load_state(self):
        tc = self.persistence.get_state("sniper_trade_count")
        ld = self.persistence.get_state("sniper_last_date")
        if tc:
            self.trade_count = int(tc)
        if ld:
            self.last_date = datetime.strptime(ld, "%Y-%m-%d").date()
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
        plus_dm = df["high"].diff()
        minus_dm = df["low"].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        tr = pd.concat(
            [
                df["high"] - df["low"],
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1)),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (abs(minus_dm).rolling(period).mean() / atr)
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di).replace(0, 1e-6)) * 100
        return dx.rolling(period).mean()

    def calculate_bollinger(self, series, period=20, std=2.0):
        sma = series.rolling(window=period).mean()
        std_dev = series.rolling(window=period).std()
        return sma + (std_dev * std), sma, sma - (std_dev * std)

    async def execute_trade(
        self,
        side,
        ai_decision=None,
        quantile_confidence="NORMAL",
        tp_multiplier=1.0,
        current_atr=None,
        regime=None,
        is_scaling_in=False,
    ):
        # [FIX #DUAL-BOT-LOCK] Verificar lock global do main.py antes de qualquer execução
        try:
            import backend.main as _main_module
            _global_lock = getattr(_main_module, '_global_order_lock_until', 0.0)
            if time.time() < _global_lock:
                _rem = _global_lock - time.time()
                logger.warning(f"🔒 [DUAL-BOT-LOCK] Sniper bloqueado pelo lock global do main.py por {_rem:.1f}s. Abortando execute_trade.")
                return False
        except Exception as _lk_err:
            logger.debug(f"[DUAL-BOT-LOCK] Não foi possível verificar lock global: {_lk_err}")

        # [FIX #DUAL-BOT-LOCK] Verificar lock local do Sniper também
        if time.time() < self._order_lock_until:
            _rem = self._order_lock_until - time.time()
            logger.warning(f"🔒 [SNIPER-LOCK] Sniper bloqueado pelo lock local por {_rem:.1f}s. Abortando execute_trade.")
            return False

        tick = self.bridge.mt5.symbol_info_tick(self.symbol)
        if not tick:
            return False
        limit_price = tick.ask if side == "buy" else tick.bid

        perf = self.risk.get_performance_metrics()
        wr = perf.get("win_rate", 55.0)
        pf = perf.get("profit_factor", 1.2)
        balance = getattr(self.risk, "initial_balance", 500.0)
        kelly_volume = self.risk.calculate_quarter_kelly(
            balance, wr, pf, current_atr or 150.0
        )

        scaling = min(2, self.consecutive_wins)
        # [v24] Lote Fixo de 2 contratos para conta de 3k (ou conforme v24_locked_params)
        force_lots = getattr(self.risk, "force_lots", None)
        if force_lots is not None:
            lots = int(force_lots)
        else:
            lots = round(kelly_volume) + scaling
            if quantile_confidence == "HIGH":
                lots += 1
            elif quantile_confidence == "VERY_HIGH":
                lots += 2

            # [v23] Aplicar multiplicador do Regime (SOTA v23)
            r_params = self.risk.get_regime_specific_params(regime)
            lot_mult = r_params.get("lot_multiplier", 1.0)
            lots *= lot_mult

            # [v23] Redução de lote se a abertura foi excessivamente volátil
            if getattr(self, "dia_pausado_vol", False):
                lots *= 0.5
                logger.info(
                    "⚠️ [VOL REDUC] Lote reduzido em 50% devido à volatilidade da abertura."
                )

            if lot_mult != 1.0:
                logger.info(
                    f"🧬 [REGIME MULT] Lote ajustado em {lot_mult}x pelo regime {r_params.get('label')}"
                )

            lots = max(1, round(lots))
        lots = min(10, lots)

        if self.risk.dry_run:
            self.trade_count += 1
            self._save_state()
            # [REGISTRO] Salva a operação de simulação no histórico do banco de dados
            try:
                self.persistence.save_trade(self.symbol, side, limit_price, lots, status="SIMULAÇÃO_SNIPER")
                self.logger.info(f"🧪 [SIMULAÇÃO] Operação registrada no histórico: {side} {lots}l @ {limit_price}")
            except Exception as e:
                self.logger.error(f"Erro ao salvar trade de simulação: {e}")
            
            self._log_to_dashboard(
                f"🧪 [SIMULAÇÃO] Sniper {side} @ {limit_price} ({lots} l)", "info"
            )
            return True

        # [v23.1] Captura de Extremos para SL Dinâmico
        prev_cand = self.bridge.get_previous_candle_extremes(self.symbol)

        params = self.risk.get_order_params(
            self.symbol,
            self.bridge.mt5.ORDER_TYPE_BUY_LIMIT
            if side == "buy"
            else self.bridge.mt5.ORDER_TYPE_SELL_LIMIT,
            limit_price,
            lots,
            current_atr=current_atr,
            regime=regime,
            tp_multiplier=tp_multiplier,
            sl_multiplier=ai_decision.get(
                "sl_multiplier", 1.0
            ),  # [v24.2] Sincronizado para momentum
            prev_extremes=prev_cand,
            current_time=datetime.now().time(),  # [v24] Essencial para Janela de Ouro
            comment="MOMENTUM_BYPASS"
            if (ai_decision and ai_decision.get("is_momentum_bypass"))
            else "SNIPER_SOTA",
        )
        buy_dist = self.ai.confidence_buy_threshold - 50.0
        buy_threshold = min(95.0, 50.0 + (buy_dist * 1.5)) if getattr(self.ai, "h1_trend", 0) < 0 else self.ai.confidence_buy_threshold
        
        sell_dist = 50.0 - self.ai.confidence_sell_threshold
        sell_threshold = max(5.0, 50.0 - (sell_dist * 1.5)) if getattr(self.ai, "h1_trend", 0) > 0 else self.ai.confidence_sell_threshold

        result = self.bridge.place_smart_order(
            self.symbol,
            params["type"],
            limit_price,
            params["volume"],
            sl=params["sl"],
            tp=params["tp"],
            score=ai_decision.get("score", 0.0),
            uncertainty=ai_decision.get("uncertainty", 0.0),
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
            comment=params.get("comment", "SNIPER_SOTA_EXPERT"),
        )

        if result and result.retcode == self.bridge.mt5.TRADE_RETCODE_DONE:
            self.trade_count += 1
            self._save_state()
            # [FIX #DUAL-BOT-LOCK] Ativar lock local E global após ordem bem-sucedida
            self._order_lock_until = time.time() + self.SNIPER_ORDER_LOCK_SEC
            try:
                import backend.main as _main_module
                _main_module._global_order_lock_until = time.time() + self.SNIPER_ORDER_LOCK_SEC
                logger.info(f"🔒 [DUAL-BOT-LOCK] Lock global propagado para main.py por {self.SNIPER_ORDER_LOCK_SEC:.0f}s.")
            except Exception:
                pass
            return True
        return False

    async def _check_trade_results(self):
        stats = self.bridge.get_trading_performance()
        if stats["total_trades"] > self.last_total_trades:
            deals = self.bridge.mt5.history_deals_get(
                datetime.combine(date.today(), dtime(0, 0)), datetime.now()
            )
            if deals:
                out_deals = [
                    d
                    for d in deals
                    if d.entry
                    in [
                        self.bridge.mt5.DEAL_ENTRY_OUT,
                        self.bridge.mt5.DEAL_ENTRY_INOUT,
                    ]
                ]
                if out_deals:
                    last_deal = out_deals[-1]
                    profit = (
                        last_deal.profit
                        + last_deal.swap
                        + last_deal.commission
                    )
                    # DEAL_TYPE_SELL na saída significa que a posição original era BUY
                    is_buy_exit = (last_deal.type == self.bridge.mt5.DEAL_TYPE_SELL)
                    is_sell_exit = (last_deal.type == self.bridge.mt5.DEAL_TYPE_BUY)

                    if profit > 0:
                        self.consecutive_wins += 1
                        if is_buy_exit:
                            self.consecutive_buy_losses = 0
                        elif is_sell_exit:
                            self.consecutive_sell_losses = 0
                    else:
                        self.consecutive_wins = 0
                        if is_buy_exit:
                            self.consecutive_buy_losses += 1
                            if self.consecutive_buy_losses >= 2:
                                self.buy_cooldown_until = time.time() + 600
                                logger.warning("🚫 [TRAVA DE INSISTÊNCIA] 2 Loss seguidos na COMPRA. Compras suspensas por 10 min.")
                        elif is_sell_exit:
                            self.consecutive_sell_losses += 1
                            if self.consecutive_sell_losses >= 2:
                                self.sell_cooldown_until = time.time() + 600
                                logger.warning("🚫 [TRAVA DE INSISTÊNCIA] 2 Loss seguidos na VENDA. Vendas suspensas por 10 min.")
                    self._save_state()
            self.last_total_trades = stats["total_trades"]

    async def manage_trailing_stop(self):
        positions = self.bridge.mt5.positions_get(symbol=self.symbol)
        if not positions:
            return
        df = self.bridge.get_market_data(self.symbol, n_candles=20)
        current_atr = (
            float((df["high"] - df["low"]).rolling(14).mean().iloc[-1])
            if not df.empty
            else 150.0
        )

        for pos in positions:
            if pos.sl == 0:
                continue
            
            # [FIX #TIMEZONE-BUG] 
            current_tick = self.bridge.mt5.symbol_info_tick(pos.symbol)
            current_mt5_time = current_tick.time if current_tick else int(time.time() - 10800)
            elapsed = current_mt5_time - pos.time

            # 🛡️ [FIX CRÍTICO GERAL] Escudo Mestre Anti-Whipsaw (3 segundos)
            # NENHUMA lógica de saída pode tocar na ordem antes de 3 segundos
            # para não confundir o spread inicial com stop/exaustão.
            if elapsed < 3.0:
                continue

            current_profit = (
                (pos.price_current - pos.price_open)
                if pos.type == self.bridge.mt5.POSITION_TYPE_BUY
                else (pos.price_open - pos.price_current)
            )

            # [FIX #NEW-POS-GUARD] Impede apenas o trailing stop nos primeiros 30s.
            # O código continua para avaliar saídas parciais ou breakeven se lucrar rápido.
            is_trailing_allowed = elapsed >= self.MIN_ELAPSED_BEFORE_TRAILING

            if self.risk.check_time_stop(
                elapsed, current_profit, current_atr=current_atr
            ):
                if not self.risk.dry_run:
                    self.bridge.close_position(pos.ticket)
                    self._last_close_time = time.time()  
                    self._last_closed_ticket = pos.ticket
                    self._order_lock_until = time.time() + self.SNIPER_ORDER_LOCK_SEC
                    try:
                        import backend.main as _main_module
                        _main_module._global_order_lock_until = time.time() + self.SNIPER_ORDER_LOCK_SEC
                        logger.info(f"🔒 [DUAL-BOT-LOCK] TIME-STOP: Lock global propagado ao main.py por {self.SNIPER_ORDER_LOCK_SEC:.0f}s (ticket #{pos.ticket}).")
                    except Exception:
                        pass
                    logger.info(f"🔒 [SNIPER TIME-STOP] Ticket #{pos.ticket} fechado. main.py será notificado via FLIP-5.")
                continue

            should_partial, p_vol = self.risk.check_scaling_out(
                self.symbol,
                pos.ticket,
                current_profit,
                pos.volume,
                regime=getattr(self, "current_regime", 0),
                comment=pos.comment,
            )
            if should_partial and not self.risk.dry_run:
                self.bridge.close_partial_position(pos.ticket, p_vol)
                self._last_close_time = time.time()  
                logger.info(f"🎯 [SNIPER PARCIAL] Ticket #{pos.ticket} parcialmente fechado ({p_vol} lotes).")
                continue

            should_be, new_sl = self.risk.check_breakeven(
                current_profit,
                pos.price_open,
                side="buy" if pos.type == self.bridge.mt5.POSITION_TYPE_BUY else "sell",
            )
            if should_be and new_sl:
                new_sl = self.risk._quantize_price(self.symbol, new_sl)
                if (
                    pos.type == self.bridge.mt5.POSITION_TYPE_BUY and new_sl > pos.sl
                ) or (
                    pos.type == self.bridge.mt5.POSITION_TYPE_SELL and new_sl < pos.sl
                ):
                    if not self.risk.dry_run:
                        self.bridge.update_sltp(pos.ticket, new_sl, pos.tp)

            # [FIX NEW-POS-GUARD] Só avança para Trailing Dinâmico se tiver passado 30s
            if not is_trailing_allowed:
                continue

            pos_side = (
                "buy" if pos.type == self.bridge.mt5.POSITION_TYPE_BUY else "sell"
            )
            t_trigger, t_lock, t_step = self.risk.get_dynamic_trailing_params(
                current_atr, side=pos_side
            )
            if current_profit >= t_trigger:
                potential_sl = self.risk._quantize_price(
                    self.symbol,
                    pos.price_current
                    + (
                        -(t_trigger - t_lock)
                        if pos.type == self.bridge.mt5.POSITION_TYPE_BUY
                        else (t_trigger - t_lock)
                    ),
                )
                if (
                    pos.type == self.bridge.mt5.POSITION_TYPE_BUY
                    and potential_sl > pos.sl + t_step
                ) or (
                    pos.type == self.bridge.mt5.POSITION_TYPE_SELL
                    and potential_sl < pos.sl - t_step
                ):
                    if not self.risk.dry_run:
                        self.bridge.update_sltp(pos.ticket, potential_sl, pos.tp)

    async def run(self):
        logger.info("🚀 Sniper Bot WIN v2.0 Live")
        if not self.bridge.connected and not self.bridge.connect():
            return
        self.symbol = self.bridge.get_current_symbol("WIN")
        self.risk.load_optimized_params(self.symbol, "backend/v24_locked_params.json")
        self._load_params_from_risk(self.bridge._normalize_symbol(self.symbol))
        # [v24.6-HOTRELOAD] Contador para recarga periódica de parâmetros dentro do loop
        self._param_reload_counter = 0

        self.last_heartbeat = time.time()
        self.running = True
        while self.running:
            try:
                # [v24.6-HOTRELOAD] Recarrega parâmetros do JSON a cada 30 ciclos (~30s)
                # Garante que momentum_bypass_threshold e obi_absorption_threshold
                # do v24_locked_params.json sejam aplicados ao ai_core em tempo real.
                self._param_reload_counter += 1
                if self._param_reload_counter >= 30:
                    self._param_reload_counter = 0
                    self.risk.load_optimized_params(self.symbol, "backend/v24_locked_params.json")
                    self._load_params_from_risk(self.bridge._normalize_symbol(self.symbol))
                    logger.info(
                        f"[v24.6-HOTRELOAD] Parâmetros sincronizados do JSON: "
                        f"momentum_bypass={self.ai.momentum_bypass_threshold:.1f} | "
                        f"obi_absorption={self.ai.obi_absorption_threshold:.1f} | "
                        f"use_bluechip={self.ai.use_bluechip_bias}"
                    )

                # [HEARTBEAT] Logar status do Sniper a cada 60 segundos
                now_ts = time.time()
                if now_ts - self.last_heartbeat > 60:
                    self.logger.info(f"🧬 [HEARTBEAT-SNIPER] Operando: {self.symbol} | Trades Hoje: {self.trade_count}")
                    self.last_heartbeat = now_ts
                await self.manage_trailing_stop()
                await self._check_trade_results()
                self.bridge.cancel_stale_orders(symbol=self.symbol, timeout_seconds=300)

                now = datetime.now()
                if not self.bridge.check_connection():
                    await asyncio.sleep(5)
                    continue

                acc = self.bridge.get_account_health()
                # [FIX #33] get_account_health() não retorna "profit".
                # O P&L flutuante é equity - balance (posições abertas).
                floating_pnl = acc.get("equity", 0) - acc.get("balance", 0)
                total_pnl = self.bridge.get_daily_realized_profit() + floating_pnl
                if (
                    not self.risk.check_daily_loss(total_pnl)[0]
                    or not self.risk.check_equity_kill_switch(
                        acc.get("equity", 0), acc.get("balance", 0)
                    )[0]
                ):
                    self.stop()
                    break

                if (
                    not (self.start_time <= now.time() <= self.end_time)
                    or not self.risk.is_time_allowed()
                ):
                    await asyncio.sleep(1)
                    continue

                if self.last_trade_time:
                    limit = (
                        300
                        if self.persistence.get_state("last_quantile_confidence")
                        == "VERY_HIGH"
                        else 600
                    )
                    remaining = limit - (now - self.last_trade_time).total_seconds()
                    if remaining > 0:
                        # [DIAGNÓSTICO] Loga uma vez por minuto para visibilidade no monitor
                        if int(remaining) % 60 < 1:
                            logger.info(
                                f"⏳ [COOLDOWN-GLOBAL] Aguardando próxima janela de entrada: "
                                f"{remaining:.0f}s restantes | Último trade: {self.last_trade_time.strftime('%H:%M:%S')}"
                            )
                        await asyncio.sleep(1)
                        continue

                df = self.bridge.get_market_data(self.symbol, n_candles=150)
                if df.empty or len(df) < 60:
                    await asyncio.sleep(1)
                    continue

                book = self.bridge.get_order_book(self.symbol)
                ticks_df = self.bridge.get_time_and_sales(self.symbol, n_ticks=100)

                try:
                    h1_data = self.bridge.get_market_data(
                        self.symbol, n_candles=150, timeframe="H1"
                    )
                    if h1_data is not None:
                        self.ai.update_h1_trend(h1_data)
                except:
                    pass

                try:
                    self.ai.analyze(book, ticks_df)
                    weighted_ofi = self.ai.calculate_wen_ofi(book)
                except Exception as e:
                    logging.debug(f"Aviso Microestrutura (Ignorado): {repr(e)}")
                    weighted_ofi = 0.0

                df["rsi"] = self.calculate_rsi(df["close"], self.rsi_period)
                df["vol_sma"] = df["tick_volume"].rolling(20).mean()
                df["adx"] = self.calculate_adx(df, 14)
                df["bb_up"], df["bb_mid"], df["bb_down"] = self.calculate_bollinger(
                    df["close"], 20, 2.0
                )

                last = df.iloc[-1]
                atr = float((df["high"] - df["low"]).rolling(14).mean().iloc[-1])
                adx_val = float(last["adx"]) if not np.isnan(last["adx"]) else 0.0
                pressure = await self.get_flux_pressure()

                # Pausa Volatilidade
                if self.dia_abertura_cache != now.date():
                    self.dia_pausado_vol = False
                    self.hl_abertura_cache = None
                    self.dia_abertura_cache = now.date()
                if self.hl_abertura_cache is None:
                    inicio = datetime(now.year, now.month, now.day, 9, 0, 0)
                    r = self.bridge.mt5.copy_rates_range(
                        self.symbol, self.bridge.mt5.TIMEFRAME_M1, inicio, now
                    )
                    if r is not None and len(r) >= 10:
                        hl = (
                            pd.DataFrame(r)["high"].iloc[:10]
                            - pd.DataFrame(r)["low"].iloc[:10]
                        )
                        self.hl_abertura_cache = float(hl.mean())
                        if self.hl_abertura_cache > 250.0:
                            self.dia_pausado_vol = True

                # [v23] CÁLCULO DE IA - ANTECIPADO (Prioridade de Autoridade)
                patchtst_score = await self.ai.predict_with_patchtst(
                    self.ai.inference_engine, df
                )
                sentiment = (
                    await self.ai.update_sentiment()
                    if getattr(self.risk, "enable_news_filter", True)
                    else 0.0
                )
                self.current_regime = self.ai.identify_market_regime(
                    df,
                    self.ai.h1_trend,
                    atr,
                    adx_val,
                    last["bb_up"],
                    last["bb_down"],
                    last["bb_mid"],
                )
                regime = self.current_regime
                m_ctx = self._load_market_context()
                bc_score = m_ctx.get("synthetic_index", 0.0)

                decision = self.ai.calculate_decision(
                    obi=pressure,
                    sentiment=sentiment,
                    patchtst_score=patchtst_score,
                    regime=regime,
                    atr=atr,
                    volatility=0.1,
                    hour=now.hour,
                    minute=now.minute,
                    ofi=weighted_ofi,
                    cvd_accel=getattr(self.ai.micro_analyzer, "last_cvd_accel", 0.0) if hasattr(self.ai, "micro_analyzer") else 0.0,  # [v24.5] Aceleração
                    current_price=last["close"],
                    spread=self.bridge.get_latency_and_spread(self.symbol)[1],
                    sma_20=last["bb_mid"],
                    bluechip_score=bc_score,
                    # [v24] Injeção de Volume para Score Elasticidade
                    current_vol=last["tick_volume"],
                    avg_vol_20=last["vol_sma"],
                )

                # [v23] Lógica de Gatilhos: Sniper (Indicadores) vs Momentum (Bypass IA)
                rsi_buy = (
                    self.rsi_dynamic_buy
                    if atr >= self.rsi_dynamic_activation_atr
                    else 30.0
                )
                rsi_sell = (
                    self.rsi_dynamic_sell
                    if atr >= self.rsi_dynamic_activation_atr
                    else 70.0
                )

                # Ajuste RSI Assimétrico para Tendência (Regime 1)
                if regime == 1:
                    rsi_buy = 45.0 if self.ai.h1_trend >= 0 else 25.0
                    rsi_sell = 55.0 if self.ai.h1_trend <= 0 else 75.0

                flux_mult = self.vol_spike_mult if atr < 200 else 1.05
                c_buy_sniper = last["rsi"] < rsi_buy and last["tick_volume"] > (
                    last["vol_sma"] * flux_mult
                )
                c_sell_sniper = last["rsi"] > rsi_sell and last["tick_volume"] > (
                    last["vol_sma"] * flux_mult
                )

                is_trade_allowed = False
                side = "NEUTRAL"

                if decision["is_momentum_bypass"]:
                    # [v23.1] BYPASS INSTITUCIONAL: IA tem autoridade total
                    if decision["direction"] == "BUY" and pressure > 1.1:
                        is_trade_allowed = True
                        side = "buy"
                        logger.info(
                            f"🚀 [MOMENTUM BYPASS] IA Score {decision['score']:.1f}% (Bypass Ativado) | Fluxo: {pressure:.2f}"
                        )
                    elif decision["direction"] == "SELL" and pressure < -1.1:
                        is_trade_allowed = True
                        side = "sell"
                        logger.info(
                            f"🚀 [MOMENTUM BYPASS] IA Score {decision['score']:.1f}% (Bypass Ativado) | Fluxo: {pressure:.2f}"
                        )
                else:
                    # SNIPER TRADICIONAL: Depende dos indicadores (RSI/Volume) + IA Neutra/Sniper
                    if (
                        c_buy_sniper
                        and decision["direction"] == "BUY"
                        and pressure > self.flux_threshold
                    ):
                        is_trade_allowed = True
                        side = "buy"
                    elif (
                        c_sell_sniper
                        and decision["direction"] == "SELL"
                        and pressure < -self.flux_threshold
                    ):
                        is_trade_allowed = True
                        side = "sell"

                # [v23] Removido Veto Hard de Volatilidade Sniper.
                # Agora a redução é aplicada no lote dentro do execute_trade.
                if self.dia_pausado_vol and not decision["is_momentum_bypass"]:
                    if side != "NEUTRAL":
                        logger.info(
                            "ℹ️ [INFO VOL] Sniper operando com lote reduzido (Abertura > 250)"
                        )

                # Veto de Macro/Segurança (Mantemos mesmo no Momentum)
                if is_trade_allowed and not self.risk.is_macro_allowed(
                    "BUY" if side == "buy" else "SELL", bc_score
                ):
                    logger.warning(
                        f"🛑 [VETO-MACRO] Bypass autorizado mas VETADO pelo filtro macro. "
                        f"Direção={side.upper()} | bc_score={bc_score:.2f} | Score={decision.get('score', 0):.1f}%"
                    )
                    is_trade_allowed = False

                # Veto da Trava de Insistência
                if is_trade_allowed:
                    if side == "buy" and time.time() < self.buy_cooldown_until:
                        rem = self.buy_cooldown_until - time.time()
                        logger.warning(
                            f"🔒 [VETO-COOLDOWN] Compra bloqueada pela trava de insistência. "
                            f"Aguardar {rem:.0f}s | Score={decision.get('score', 0):.1f}%"
                        )
                        is_trade_allowed = False
                    elif side == "sell" and time.time() < self.sell_cooldown_until:
                        rem = self.sell_cooldown_until - time.time()
                        logger.warning(
                            f"🔒 [VETO-COOLDOWN] Venda bloqueada pela trava de insistência. "
                            f"Aguardar {rem:.0f}s | Score={decision.get('score', 0):.1f}%"
                        )

                if is_trade_allowed:
                    positions = self.bridge.mt5.positions_get(symbol=self.symbol)
                    can_trade = True
                    if positions:
                        p = positions[0]
                        prof = (
                            (p.price_current - p.price_open)
                            if p.type == 0
                            else (p.price_open - p.price_current)
                        )
                        if not self.risk.allow_pyramiding(
                            prof,
                            pressure,
                            sum(pos.volume for pos in positions),
                            symbol=self.symbol,
                        ):
                            logger.warning(
                                f"⚠️ [VETO-PYRAMIDING] Ordem bloqueada: posição aberta não permite pirâmide. "
                                f"Lucro flutuante={prof:.0f}pts | Fluxo={pressure:.2f} | Score={decision.get('score', 0):.1f}%"
                            )
                            can_trade = False

                    if can_trade:
                        if await self.execute_trade(
                            side,
                            ai_decision=decision,
                            quantile_confidence=decision["quantile_confidence"],
                            tp_multiplier=decision.get("tp_multiplier", 1.0),
                            current_atr=atr,
                            regime=regime,
                            is_scaling_in=len(positions) > 0,
                        ):
                            self.persistence.save_state(
                                "last_quantile_confidence",
                                decision["quantile_confidence"],
                            )
                            self.last_trade_time = now
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Erro Sniper: {sanitize_log(e)}")
                await asyncio.sleep(2)

    def _load_market_context(self):
        ctx_path = os.path.join("data", "market_context.json")
        try:
            if os.path.exists(ctx_path):
                with open(ctx_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {}

    def stop(self):
        self.running = False
        self.bridge.disconnect()


if __name__ == "__main__":
    # [ANTIVIBE-CODING] - Ativação de CONTA REAL para saldo de 3000 BRL
    bot = SniperBotWIN(dry_run=False)
    asyncio.run(bot.run())
