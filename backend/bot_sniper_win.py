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
    except:
        return "Unknown error (encoding failure)"

class SniperBotWIN:
    def __init__(self, bridge=None, risk=None, ai=None, dry_run=True):
        self.bridge = bridge or MT5Bridge()
        self.risk = risk or RiskManager(max_daily_loss=600.0, daily_trade_limit=3) # Calibrado para WIN 3000 BRL
        
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
        
        # [FASE 28] Sincronização de Parâmetros Calibrados (Grid Search)
        self.risk.load_optimized_params("WIN", "best_params_WIN.json")
        self.risk.load_optimized_params("WINJ26", "best_params_WIN.json") # Fallback para símbolo específico
        
        self._load_state()
        
    async def get_flux_pressure(self):
        """Calcula a pressão de compra/venda baseada no Book L2."""
        book = self.bridge.get_order_book(self.symbol)
        if not book or not book['bids'] or not book['asks']:
            return 1.0
        
        # Filtro de Volume Bruto Top 5
        bid_vol = sum(item['volume'] for item in book['bids'][:5])
        ask_vol = sum(item['volume'] for item in book['asks'][:5])
        
        # Formula SOTA: (Bid - Ask) / (Bid + Ask + 1)
        return float((bid_vol - ask_vol) / (bid_vol + ask_vol + 1))

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
        
        # Proteção contra divisão por zero (mercados sem variação negativa)
        rs = gain / loss.replace(0, 0.000001)
        return 100 - (100 / (1 + rs))

    async def execute_trade(self, side, quantile_confidence="NORMAL", tp_multiplier=1.0, current_atr=None, regime=None):
        """Coordena o envio de ORDEM LIMITADA (Passive Entry) com Cancelamento Tático.
        Args:
            side: 'buy' ou 'sell'
            quantile_confidence: 'NORMAL' | 'HIGH' | 'VERY_HIGH' — calibra o tamanho do lote.
            tp_multiplier: Fator de ajuste de TP por spread (SOTA v5).
            current_atr: Volatilidade atual para alvos adaptativos.
            regime: Regime de mercado detectado (0=Lateral, 1=Tendência, 2=Ruído).
        """
        tick = self.bridge.mt5.symbol_info_tick(self.symbol)
        if not tick: return False
        
        # Preço Sniper: Ask para Compra, Bid para Venda (Garante execução no topo do book)
        limit_price = tick.ask if side == "buy" else tick.bid
        
        # [FASE 22 — QUANTILE CONFIDENCE SCALING]
        # Calibra o número de contratos pela convicção do PatchTST Q10/Q90
        # NORMAL   : 1 contrato (sinal padrão, threshold 85%)
        # HIGH     : 2 contratos (banda Q10/Q90 assimétrica > 5pts)
        # VERY_HIGH: 3 contratos (banda assimétrica > 20% — alta convicção direcional)
        lot_map = {"NORMAL": 1.0, "HIGH": 2.0, "VERY_HIGH": 3.0}
        base_lots = lot_map.get(quantile_confidence, 1.0)
        
        # [ALPHA FORCE] Escalonamento por vitórias consecutivas
        # Sugerido: Alpha +1. Limitamos a +2 para segurança do capital de R$ 3000.
        scaling = min(2, self.consecutive_wins)
        lots = base_lots + scaling
        
        logger.info(f"[FORÇA ALPHA] confiança={quantile_confidence} base={base_lots} escalonamento=+{scaling} -> total_lotes={lots}")
        
        if self.risk.dry_run:
            logger.info(f"🧪 [SIMULAÇÃO] LIMIT {side.upper()} Sniper disparado @ {limit_price}")
            self.trade_count += 1
            self._save_state()
            return True

        # [FASE 28] Obter Parâmetros de Risco OCO
        # SOTA v5: Injetamos o TP Multiplier calculado pela IA
        params = self.risk.get_order_params(
            self.symbol, 
            self.bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else self.bridge.mt5.ORDER_TYPE_SELL_LIMIT,
            limit_price, 
            lots, 
            current_atr=current_atr,
            regime=regime,
            tp_multiplier=tp_multiplier
        )

        # Enviar Ordem Limitada
        order_type = params['type']
        result = self.bridge.place_limit_order(
            self.symbol, order_type, limit_price, lots, 
            sl=params['sl'], tp=params['tp'],
            comment="SNIPER_SOTA_LIMIT"
        )
        
        if result and result.retcode == self.bridge.mt5.TRADE_RETCODE_DONE:
            order_ticket = result.order
            # --- CANCELAMENTO TÁTICO (Alpha Fade Dinâmico - Melhoria E) ---
            timeout_sec = self.risk.get_alpha_fade_timeout()
            iterations = int(timeout_sec / 0.5)
            
            logger.info(f"⏳ [INICIADA] Ordem LIMIT {order_ticket} aberta @ {limit_price}. TTL: {timeout_sec}s...")
            
            for _ in range(iterations):
                await asyncio.sleep(0.5)
                status = self.bridge.check_order_status(order_ticket)
                if status == "FILLED":
                    self.trade_count += 1
                    self._save_state()
                    logger.info(f"🎯 [EXECUÇÃO] {side.upper()} @ {limit_price} | Trade {self.trade_count}/{self.risk.daily_trade_limit}")
                    return True
                elif status == "CANCELED":
                    logger.warning(f"🚫 [REJEITADA/CANCELADA] Ordem {order_ticket} cancelada externamente.")
                    return False
            
            # Se não executar em 3s, cancela
            logger.info(f"⏱️ TTL Expirou. Cancelando ordem {order_ticket}...")
            if self.bridge.cancel_order(order_ticket):
                logger.info(f"🛡️ [CANCELADA/TTL] Ordem {order_ticket} cancelada (Momento passou).")
            else:
                # Verificação de Condição de Corrida (Race Condition)
                final_status = self.bridge.check_order_status(order_ticket)
                if final_status == "FILLED":
                    logger.info(f"🏁 [LUCRO/CORRIDA] Vitória em Condição de Corrida: {order_ticket} preenchida no limite!")
                    self.trade_count += 1
                    self._save_state()
                    return True
            return False
        else:
            msg = result.comment if result else "None"
            logger.error(f"❌ [REJEITADA] Falha ao enviar ordem: {msg}")
            return False

    async def _check_trade_results(self):
        """Monitora o histórico para atualizar vitórias consecutivas (Alpha Scaling)."""
        stats = self.bridge.get_trading_performance()
        if stats['total_trades'] > self.last_total_trades:
            # Novo trade fechado detectado
            deals = self.bridge.mt5.history_deals_get(datetime.combine(date.today(), time(0,0)), datetime.now())
            if deals:
                out_deals = [d for d in deals if d.entry in [self.bridge.mt5.DEAL_ENTRY_OUT, self.bridge.mt5.DEAL_ENTRY_INOUT]]
                if out_deals:
                    last_deal = out_deals[-1]
                    profit = last_deal.profit + last_deal.swap + last_deal.commission
                    if profit > 0:
                        self.consecutive_wins += 1
                        logger.info(f"✨ [LUCRO] Vitória detectada! Lucro: {profit:.2f} | Vitórias Consecutivas: {self.consecutive_wins}")
                    else:
                        self.consecutive_wins = 0
                        logger.info(f"📉 [PREJUÍZO/STOP] Loss ou BE detectado. Lucro: {profit:.2f}. Resetando Alpha Scaling.")
                    self._save_state()
            self.last_total_trades = stats['total_trades']

    async def manage_trailing_stop(self):
        """Monitora posições abertas e aplica o Trailing Stop SOTA."""
        positions = self.bridge.mt5.positions_get(symbol=self.symbol)
        if not positions:
            return

        for pos in positions:
            # Pular se não houver SL (não deveria acontecer no Sniper)
            if pos.sl == 0: continue

            # 0. Lógica de VELOCITY LIMIT (Drawdown-Acelerado-no-Tempo)
            # pos.time é Unix Epoch do servidor
            now_ts = datetime.utcnow().timestamp()
            elapsed = now_ts - pos.time
            
            # Cálculo de Lucro em Pontos
            if pos.type == self.bridge.mt5.POSITION_TYPE_BUY:
                current_profit = pos.price_current - pos.price_open
            else:
                current_profit = pos.price_open - pos.price_current
            
            # Verificar Velocity Limit no RiskManager
            v_ok, v_msg = self.risk.check_velocity_limit(current_profit, elapsed)
            if v_ok:
                logger.warning(f"🛡️ [LIMITE VELOCIDADE] {v_msg}: Fechando posição {pos.ticket} precocemente.")
                if self.risk.dry_run:
                    logger.info(f"🧪 [SIMULAÇÃO] Fechamento {pos.ticket} por Limite de Velocidade")
                else:
                    self.bridge.close_position(pos.ticket)
                continue

            # 1. Lógica de Breakeven [URGENTE]
            if pos.type == self.bridge.mt5.POSITION_TYPE_BUY:
                current_profit = pos.price_current - pos.price_open
                
                # 1. Lógica de Breakeven [URGENTE]
                if current_profit >= self.risk.be_trigger and pos.sl < pos.price_open:
                    new_sl = self.risk._quantize_price(self.symbol, pos.price_open + self.risk.be_lock)
                    if self.risk.dry_run:
                        logger.info(f"🛡️ [DRY RUN] Breakeven BUY: SL {pos.sl} -> {new_sl}")
                    else:
                        self.bridge.update_sltp(pos.ticket, new_sl, pos.tp)
                        logger.info(f"⚡ [BREAKEVEN] SL BUY Protegido: {new_sl} (Lucro: {current_profit:.1f} pts)")
                
                # 2. Trailing Stop SOTA
                if current_profit >= self.risk.trailing_trigger:
                    potential_sl = pos.price_current - (self.risk.trailing_trigger - self.risk.trailing_lock)
                    potential_sl = self.risk._quantize_price(self.symbol, potential_sl)
                    
                    if potential_sl > pos.sl + self.risk.trailing_step:
                        if self.risk.dry_run:
                            logger.info(f"🛡️ [DRY RUN] Trailing Stop BUY ajustado: {pos.sl} -> {potential_sl}")
                        else:
                            self.bridge.update_sltp(pos.ticket, potential_sl, pos.tp)
                            logger.info(f"⚡ [SOTA TRAILING] SL BUY Movido: {potential_sl} | Flutuante: {current_profit:.1f} pts")

            elif pos.type == self.bridge.mt5.POSITION_TYPE_SELL:
                current_profit = pos.price_open - pos.price_current
                
                # 1. Lógica de Breakeven [URGENTE]
                if current_profit >= self.risk.be_trigger and pos.sl > pos.price_open:
                    new_sl = self.risk._quantize_price(self.symbol, pos.price_open - self.risk.be_lock)
                    if self.risk.dry_run:
                        logger.info(f"🛡️ [DRY RUN] Breakeven SELL: SL {pos.sl} -> {new_sl}")
                    else:
                        self.bridge.update_sltp(pos.ticket, new_sl, pos.tp)
                        logger.info(f"⚡ [BREAKEVEN] SL SELL Protegido: {new_sl} (Lucro: {current_profit:.1f} pts)")

                # [MELHORIA] Scaling Out — Saída Parcial SELL
                # Se chegou no gatilho de parcial e ainda tem volume > 1 contrato, realiza saída parcial
                if (current_profit >= self.risk.partial_profit_points
                        and pos.volume > self.risk.partial_volume
                        and not self.persistence.get_state(f"partial_done_{pos.ticket}")):
                    partial_lots = self.risk.partial_volume
                    if self.risk.dry_run:
                        logger.info(f"💰 [DRY RUN] Parcial SELL: Fechando {partial_lots} lote(s) @ +{current_profit:.1f} pts (ticket={pos.ticket})")
                    else:
                        self.bridge.close_partial(pos.ticket, partial_lots)
                        logger.info(f"💰 [PARCIAL SELL] {partial_lots} lote(s) realizados @ +{current_profit:.1f} pts. Restante: trailing livre.")
                    # Marcar para não repetir nesta posição
                    self.persistence.save_state(f"partial_done_{pos.ticket}", "1")

                # 2. [MELHORIA] Trailing Stop Assimétrico SELL
                # Ativa mais cedo (40pts) e com passo menor (15pts): mercados caem rápido.
                if current_profit >= self.risk.trailing_trigger_sell:
                    potential_sl = pos.price_current + (self.risk.trailing_trigger_sell - self.risk.trailing_lock_sell)
                    potential_sl = self.risk._quantize_price(self.symbol, potential_sl)
                    
                    if potential_sl < pos.sl - self.risk.trailing_step_sell:
                        if self.risk.dry_run:
                            logger.info(f"🛡️ [DRY RUN] Trailing Assimétrico SELL ajustado: {pos.sl} -> {potential_sl}")
                        else:
                            self.bridge.update_sltp(pos.ticket, potential_sl, pos.tp)
                            logger.info(f"⚡ [TRAILING ASSIMÉTRICO] SL SELL Movido: {potential_sl} | Flutuante: {current_profit:.1f} pts")

    async def run(self):
        logger.info("🚀 Inicializando Sniper Bot WIN (Foco: R$ 3000 Capital)...")
        if not self.bridge.connected:
            if not self.bridge.connect():
                logger.error("Falha ao conectar MT5. Encerrando.")
                return

        self.symbol = self.bridge.get_current_symbol("WIN")
        logger.info(f"Símbolo alvo: {self.symbol} | MODO: {'SIMULAÇÃO' if self.risk.dry_run else 'REAL'}")
        
        # [FASE 28] APLICAR PARÂMETROS DINÂMICOS SE CARREGADOS
        if self.symbol in self.risk.dynamic_params:
            d_params = self.risk.dynamic_params[self.symbol]
            if d_params.get("rsi_period"):
                self.rsi_period = int(d_params["rsi_period"])
            if d_params.get("vol_spike_mult"):
                self.vol_spike_mult = float(d_params["vol_spike_mult"])
            if d_params.get("start_time"):
                try:
                    self.start_time = datetime.strptime(d_params["start_time"], "%H:%M").time()
                except: pass
            if d_params.get("end_time"):
                try:
                    self.end_time = datetime.strptime(d_params["end_time"], "%H:%M").time()
                except: pass
            logger.info(f"🎯 SniperBot: Parâmetros SOTA aplicados: RSI={self.rsi_period}, VolSpike={self.vol_spike_mult}, Janela={self.start_time}-{self.end_time}")
        
        self.running = True
        while self.running:
            try:
                # 0. Gestão de Posição (Trailing Stop SOTA)
                await self.manage_trailing_stop()
                
                # 0.1 Monitorar resultados para Alpha Scaling
                await self._check_trade_results()

                # 0.2 Alpha Fade Global: Cancela qualquer ordem pendente (Melhoria E)
                self.bridge.cancel_stale_orders(symbol=self.symbol, timeout_seconds=self.risk.get_alpha_fade_timeout())

                # 1. Reset Diário (Mudança de dia com bot ligado)
                today = date.today()
                if self.last_date != today:
                    self.trade_count = 0
                    self.last_date = today
                    self._save_state()
                    logger.info(f"📅 Reset diário realizado: {today}")

                # 1. Verificações de Segurança
                now = datetime.now()
                now_time = now.time()
                
                if not self.bridge.check_connection():
                    await asyncio.sleep(5)
                    continue

                # 1.1 Coleta da Saúde de Execução e Ambiental (NOVO HFT DEFENSE)
                ping_ms, spread_points = self.bridge.get_latency_and_spread(self.symbol)
                env_ok, env_msg = self.risk.validate_environmental_risk(ping_ms, spread_points, max_ping=150.0, max_spread=15.0)
                
                if not env_ok:
                    logger.warning(f"🛡️ [BLOQUEIO AMBIENTAL] {env_msg}")
                    await asyncio.sleep(2) # Pausa leve pra esperar a B3/Rede normalizar
                    continue
                
                # 1.2 Kill Switch Financeiro Global
                acc_health = self.bridge.get_account_health()
                current_equity = acc_health.get('equity', 0.0)
                # O saldo base ideal pode vir da persistence, mas usando current_balance provisório
                starting_balance = 3000.0  
                
                eq_ok, eq_msg = self.risk.check_equity_kill_switch(current_equity, starting_balance)
                if not eq_ok:
                    logger.error(f"💀 [FALHA CRÍTICA] {eq_msg}")
                    # Encerra o loop completamente
                    self.stop()
                    break

                # 2. Janela de Operação Sniper
                if not (self.start_time <= now_time <= self.end_time):
                    # Fora da janela, apenas aguarda (ou fecha se necessário)
                    await asyncio.sleep(60)
                    continue

                # 2.1 Cooldown Check (Não bloqueante)
                if self.last_trade_time:
                    elapsed = (datetime.now() - self.last_trade_time).total_seconds()
                    # [SOTA v24] Cooldown Dinâmico por Convicção
                    # VERY_HIGH: 5 min (300s), NORMAL/HIGH: 10 min (600s)
                    is_very_high = self.persistence.get_state("last_quantile_confidence") == "VERY_HIGH"
                    cooldown_limit = 300 if is_very_high else 600
                    if elapsed < cooldown_limit:
                        await asyncio.sleep(1)
                        continue

                # 3. Limite de Risco Agressivo (60% do Saldo)
                # Assumindo capital fixo de R$ 1000 para a verificação de limite
                current_balance = 3000.0 # Capital Atualizado para R$ 3000
                limit_ok, msg = self.risk.check_aggressive_risk(self.persistence.get_state("daily_pnl") or 0.0, current_balance)
                if not limit_ok:
                    logger.info(f"🏁 Limite de perda agressivo (60%) atingido: {msg}")
                    await asyncio.sleep(300)
                    continue

                # 4. Captura de Dados M1
                df = self.bridge.get_market_data(self.symbol, n_candles=50)
                if df.empty or len(df) < 20:
                    await asyncio.sleep(1)
                    continue
                
                # 5. Indicadores
                df['rsi'] = self.calculate_rsi(df['close'], self.rsi_period)
                df['vol_sma'] = df['tick_volume'].rolling(20).mean()
                
                last_row = df.iloc[-1]
                rsi = last_row['rsi']
                avg_vol = last_row['vol_sma']
                curr_vol = last_row['tick_volume']
                
                # [Fase 27] Métricas de Contexto para Meta-Learner
                # Cálculo de ATR (14 períodos)
                low_high_range = df['high'] - df['low']
                close_prev_close = abs(df['close'] - df['close'].shift(1))
                true_range = pd.concat([low_high_range, close_prev_close], axis=1).max(axis=1)
                atr = float(true_range.rolling(14).mean().iloc[-1])
                
                # Volatilidade de Curto Prazo (Log returns de 20 períodos, anualizado)
                log_returns = np.log(df['close'] / df['close'].shift(1))
                volatility = float(log_returns.tail(20).std() * np.sqrt(252 * 480)) # Multiplicador para 1min
                if not np.isfinite(volatility): volatility = 0.0

                # Pressão de Fluxo Atual (Usada para Regime e Decision)
                pressure = await self.get_flux_pressure()

                # Detectar Regime (Contínuo para manter histórico)
                regime = self.ai.detect_regime(volatility, pressure)

                # Busca Tática: Preço de Ajuste (Settlement)
                settlement_price = self.bridge.get_settlement_price(self.symbol)

                # Atualizar Sentimento (Lê do JSON do Worker)
                sentiment_score = await self.ai.update_sentiment()
                # [SOTA v5] Sincronizar Âncora de Sentimento para o Bot Snipers
                self.ai.update_sentiment_anchor(last_row['close'])
                
                # 6. Lógica Sniper (Aggressive Bollinger Style)
                # [SOTA v23] FLUXO ADAPTATIVO: Se ATR > 200, reduz threshold para 1.05
                current_flux_mult = self.vol_spike_mult
                if atr > 200:
                    current_flux_mult = 1.05
                    logger.info(f"🔥 ALTA TENDÊNCIA (ATR {atr:.1f}): Filtro de Fluxo reduzido para {current_flux_mult}")
                
                buy_cond = rsi < 30 and curr_vol > (avg_vol * current_flux_mult)
                sell_cond = rsi > 70 and curr_vol > (avg_vol * current_flux_mult)
                
                # Regra Adicional HFT: Se preço atual estiver muito perto do Ajuste (Settlement), evita ir contra o ímã
                current_price = last_row['close']
                dist_to_settlement = abs(current_price - settlement_price) if settlement_price > 0 else 999.0
                
                # Se estiver colado no ajuste (ex: menos de 50 pontos), reforçar cautela
                if dist_to_settlement < 50.0 and settlement_price > 0:
                     # Se vou comprar acima do ajuste, é perigoso (ajuste vai puxar pra baixo)
                     if buy_cond and current_price > settlement_price:
                          logger.info("🛡️ [HFT TÁTICO] Compra barrada: Preço testando Ajuste por cima (Puxada).")
                          buy_cond = False
                     # Se vou vender abaixo do ajuste, é perigoso (ajuste empurra pra cima)
                     if sell_cond and current_price < settlement_price:
                          logger.info("🛡️ [HFT TÁTICO] Venda barrada: Preço testando Ajuste por baixo (Suporte).")
                          sell_cond = False

                # 7. FILTRO DE FLUXO (L2 PRESSURE) + AI VETO
                if buy_cond or sell_cond:
                    side = "buy" if buy_cond else "sell"
                    
                    # Filtro de Fluxo SOTA
                    flux_ok = (side == "buy" and pressure > 0.3) or \
                              (side == "sell" and pressure < -0.3)
                    
                    if flux_ok:
                        # [FASE 27] DECISÃO COMPLETA DA IA (Sincronizada)
                        # Busca predição profunda do PatchTST
                        patchtst_data = await self.ai.predict_with_patchtst(self.ai.inference_engine, df)

                        # [SOTA v5] Cálculo de Spread Normalizado
                        tick = self.bridge.mt5.symbol_info_tick(self.symbol)
                        live_spread = (tick.ask - tick.bid) / 5.0 if tick else 1.0

                        ai_decision = self.ai.calculate_decision(
                            obi=pressure,
                            sentiment=sentiment_score,
                            patchtst_score=patchtst_data,
                            regime=regime,
                            atr=atr,
                            volatility=volatility,
                            hour=now.hour,
                            minute=now.minute,
                            current_price=last_row['close'],
                            spread=live_spread,
                            sma_20=last_row['sma_20']
                        )
                        
                        ai_direction = ai_decision.get("direction", "NEUTRAL")
                        quantile_confidence = ai_decision.get("quantile_confidence", "NORMAL")
                        ai_score = ai_decision.get("score", 50.0)

                        ai_ok = (side == "buy"  and ai_direction == "BUY") or \
                                (side == "sell" and ai_direction == "SELL")

                        logger.info(
                            f"[IA] direção={ai_direction} score={ai_score:.1f} "
                            f"conf={quantile_confidence} fluxo={pressure:.2f} reg={regime} sent={sentiment_score:.2f}"
                        )

                        if ai_ok:
                            # [SOTA v25] FILTRO DE RUÍDO CENTRALIZADO NO AI CORE (macro_bull_lock / macro_bear_lock)
                            # O veto já foi processado dentro do calculate_decision e refletido no ai_ok.

                            # [SOTA v24] ALVO ADAPTATIVO: +20% TP se alinhado com Ultra Tendência
                            final_tp_mult = ai_decision.get("tp_multiplier", 1.0)
                            if regime == 1 and ((side == "buy" and ai_direction == "BUY") or (side == "sell" and ai_direction == "SELL")):
                                final_tp_mult *= 1.2
                                logger.info(f"📈 [ULTRA TENDÊNCIA] Alvo expandido: Multiplicador TP -> {final_tp_mult:.2f}")

                            if await self.execute_trade(
                                side, 
                                quantile_confidence=quantile_confidence, 
                                tp_multiplier=final_tp_mult,
                                current_atr=atr,
                                regime=regime
                            ):
                                # Salvar confiança para próximo cooldown
                                self.persistence.save_state("last_quantile_confidence", quantile_confidence)
                                logger.info(f"[SNIPER] Disparado! Lotes: {quantile_confidence} | P-Score: {ai_score:.1f}. Cooldown.")
                                self.last_trade_time = datetime.now()
                        else:
                            logger.info(f"[AI VETO] Sinal ignorado. AI: {ai_direction} | Score: {ai_score:.1f}")

                    else:
                        logger.debug(f"Fluxo não alinhado: {side.upper()} | Pressure: {pressure:.2f}")

                await asyncio.sleep(0.1) # Loop de alta frequência (100ms) para Sniper
                
            except Exception as e:
                logger.error(f"Erro no loop do Sniper: {sanitize_log(e)}")
                await asyncio.sleep(5)

    def stop(self):
        self.running = False
        self.bridge.disconnect()

if __name__ == "__main__":
    bot = SniperBotWIN(dry_run=True) # Começa em Dry Run por segurança
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Sniper Bot parado manualmente.")
