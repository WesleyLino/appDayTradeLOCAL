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

    async def execute_trade(self, side):
        """Coordena o envio de ORDEM LIMITADA (Passive Entry) com Cancelamento Tático."""
        tick = self.bridge.mt5.symbol_info_tick(self.symbol)
        if not tick: return False
        
        # Preço Sniper: Ask para Compra, Bid para Venda (Garante execução no topo do book)
        # O usuário sugeriu Ask ou Ask - 0.5. No WIN, subtraímos 5 pontos (1 tick).
        limit_price = tick.ask if side == "buy" else tick.bid
        
        # [R$ 3000] Lote Fixo Proporcional (1 contrato por R$ 1000)
        lots = 3.0
        
        if self.risk.dry_run:
            logger.info(f"🧪 [DRY RUN] LIMIT {side.upper()} Sniper disparado @ {limit_price}")
            self.trade_count += 1
            self._save_state()
            return True

        # Enviar Ordem Limitada
        order_type = self.bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else self.bridge.mt5.ORDER_TYPE_SELL_LIMIT
        result = self.bridge.place_limit_order(self.symbol, order_type, limit_price, lots, comment="SNIPER_SOTA_LIMIT")
        
        if result and result.retcode == self.bridge.mt5.TRADE_RETCODE_DONE:
            order_ticket = result.order
            logger.info(f"⏳ Ordem LIMIT {order_ticket} aberta @ {limit_price}. Aguardando 3s (Tactical TTL)...")
            
            # --- CANCELAMENTO TÁTICO (3 segundos) ---
            for _ in range(6): # 6 x 0.5s = 3s
                await asyncio.sleep(0.5)
                status = self.bridge.check_order_status(order_ticket)
                if status == "FILLED":
                    self.trade_count += 1
                    self._save_state()
                    logger.info(f"🎯 [SNIPER FILL] {side.upper()} @ {limit_price} | Trade {self.trade_count}/{self.risk.daily_trade_limit}")
                    return True
                elif status == "CANCELED":
                    logger.warning(f"Ordem {order_ticket} cancelada externamente.")
                    return False
            
            # Se não executar em 3s, cancela
            logger.info(f"⏱️ TTL Expirou. Cancelando ordem {order_ticket}...")
            if self.bridge.cancel_order(order_ticket):
                logger.info(f"🛡️ Ordem {order_ticket} cancelada (Momento passou).")
            else:
                # Race Condition Check
                final_status = self.bridge.check_order_status(order_ticket)
                if final_status == "FILLED":
                    logger.info(f"🏁 Race Condition WIN: {order_ticket} preenchida no limite!")
                    self.trade_count += 1
                    self._save_state()
                    return True
            return False
            
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
                        logger.info(f"✨ VITÓRIA detectada! Consecutive Wins: {self.consecutive_wins} | Lote Próximo: {min(1 + self.consecutive_wins, 5)}")
                    else:
                        self.consecutive_wins = 0
                        logger.info(f"📉 LOSS ou BE detectado. Resetando Alpha Scaling. Consecutive Wins: 0")
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

            # Cálculo de Lucro em Pontos
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

                # 2. Trailing Stop SOTA
                if current_profit >= self.risk.trailing_trigger:
                    potential_sl = pos.price_current + (self.risk.trailing_trigger - self.risk.trailing_lock)
                    potential_sl = self.risk._quantize_price(self.symbol, potential_sl)
                    
                    if potential_sl < pos.sl - self.risk.trailing_step:
                        if self.risk.dry_run:
                            logger.info(f"🛡️ [DRY RUN] Trailing Stop SELL ajustado: {pos.sl} -> {potential_sl}")
                        else:
                            self.bridge.update_sltp(pos.ticket, potential_sl, pos.tp)
                            logger.info(f"⚡ [SOTA TRAILING] SL SELL Movido: {potential_sl} | Flutuante: {current_profit:.1f} pts")

    async def run(self):
        logger.info("🚀 Inicializando Sniper Bot WIN (Foco: R$ 3000 Capital)...")
        if not self.bridge.connected:
            if not self.bridge.connect():
                logger.error("Falha ao conectar MT5. Encerrando.")
                return

        self.symbol = self.bridge.get_current_symbol("WIN")
        logger.info(f"Símbolo alvo: {self.symbol} | MODO: {'DRY RUN' if self.risk.dry_run else 'LIVE'}")
        
        self.running = True
        while self.running:
            try:
                # 0. Gestão de Posição (Trailing Stop SOTA)
                await self.manage_trailing_stop()
                
                # 0.1 Monitorar resultados para Alpha Scaling
                await self._check_trade_results()

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

                # 2. Janela de Operação Sniper
                if not (self.start_time <= now_time <= self.end_time):
                    # Fora da janela, apenas aguarda (ou fecha se necessário)
                    await asyncio.sleep(60)
                    continue

                # 2.1 Cooldown Check (Não bloqueante)
                if self.last_trade_time:
                    elapsed = (datetime.now() - self.last_trade_time).total_seconds()
                    if elapsed < 120: # 2 min de cooldown
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
                
                # 6. Lógica Sniper (Aggressive Bollinger Style)
                buy_cond = rsi < 30 and curr_vol > (avg_vol * self.vol_spike_mult)
                sell_cond = rsi > 70 and curr_vol > (avg_vol * self.vol_spike_mult)
                
                # 7. FILTRO DE FLUXO (L2 PRESSURE) + AI VETO
                if buy_cond or sell_cond:
                    pressure = await self.get_flux_pressure() # Agora retorna -1 a 1
                    side = "buy" if buy_cond else "sell"
                    
                    # Filtro de Fluxo SOTA
                    flux_ok = (side == "buy" and pressure > 0.3) or \
                              (side == "sell" and pressure < -0.3)
                    
                    if flux_ok:
                        # [HFT 2.1] AI VETO: Verifica se a IA concorda com a direção técnica
                        # Para WIN 1000 BRL, o veto é a última linha de defesa
                        ai_pred = self.ai.predict_regime(df)
                        ai_ok = (side == "buy" and ai_pred['direction'] == 1) or \
                                (side == "sell" and ai_pred['direction'] == -1)
                        
                        if ai_ok:
                            if await self.execute_trade(side):
                                logger.info(f"🚀 Sniper disparado com sucesso! Iniciando cooldown.")
                                self.last_trade_time = datetime.now()
                        else:
                            logger.info(f"🛡️ AI VETO: Sinal técnico ignorado por desalinhamento da IA ({ai_pred['direction']})")
                    else:
                        logger.debug(f"Fluxo não alinhado: {side.upper()} | Pressure: {pressure:.2f}")

                await asyncio.sleep(0.1) # Loop de alta frequência (100ms) para Sniper
                
            except Exception as e:
                logger.error(f"Erro no loop do Sniper: {e}")
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
