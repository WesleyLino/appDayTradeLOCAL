import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import logging
import time

# Configuração de Logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend/trading_bridge.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class MT5Bridge:
    def __init__(self):
        self.mt5 = mt5 # Expor módulo para acesso externo (HFT)
        self.connected = False
        self._macro_symbol_cache = None # [HFT v2.1] Cache para evitar busca repetitiva
        
        # self.connect() # Moved to explicit call

    def connect(self):
        """Estabelece conexão com o MetaTrader 5 local."""
        if not self.mt5.initialize():
            logging.error(f"Falha ao inicializar MT5: {self.mt5.last_error()}")
            return False

        # Verificar se está conectado à corretora correta
        account_info = self.mt5.account_info()
        if account_info is None:
            logging.error("Não foi possível obter informações da conta.")
            self.disconnect()
            return False
            
        logging.info("Conectado com sucesso!")
        logging.info(f"Servidor: {account_info.server}")
        logging.info(f"Corretora: {account_info.company}")
        logging.info(f"Conta: {account_info.login}")
        logging.info(f"Saldo: R$ {account_info.balance:.2f}")
        
        # Validação Estrita de Servidor (Genial)
        allowed_servers = ["GenialInvestimentos-PRD", "GenialInvestimentos-DEMO"]
        if account_info.server not in allowed_servers:
            logging.warning(f"[AVISO CRITICO] Servidor conectado ({account_info.server}) nao e Genial PRD/DEMO. Verifique sua conexao.")
        else:
            logging.info(f"[OK] Servidor Genial Verificado: {account_info.server}")

        # Validação de AlgoTrading
        terminal_info = self.mt5.terminal_info()
        if not terminal_info.trade_allowed:
            logging.error("[ERRO CRITICO] AlgoTrading DESATIVADO. Ative o botao 'AlgoTrading' no MT5 para operar.")
            self.disconnect()
            return False
        else:
            logging.info("[OK] AlgoTrading: ATIVADO (Negociacao Permitida)")

        self.connected = True
        return True

    def disconnect(self):
        """Encerra a conexão com o MT5."""
        mt5.shutdown()
        self.connected = False
        logging.info("Conexão MT5 encerrada.")

    def check_connection(self):
        """Verifica se o terminal está ativo e conectado à corretora."""
        if not self.connected: 
            return False
            
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            self.connected = False
            return False
            
        # Verifica se está conectado à rede (trade_allowed)
        if not terminal_info.connected:
            return False
            
        return True

    def place_resilient_order(self, params, max_retries=3):
        """
        Envia ordem com lógica de retentativa para Requotes (10004) e Price Change (10006).
        Específico para B3 HFT.
        """
        if not self.connected: return None
        
        attempt = 0
        last_result = None
        
        while attempt < max_retries:
            start_time = time.time()
            result = mt5.order_send(params)
            latency = (time.time() - start_time) * 1000
            
            if result is None:
                logging.error("MT5 order_send retornou None inesperadamente.")
                break

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logging.info(f"ORDEM EXECUTADA: {result.retcode} (Latência: {latency:.1f}ms)")
                return result
            
            # 10004: REQUOTE, 10006: PRICE_CHANGED
            if result.retcode in [10004, 10006]:
                attempt += 1
                logging.warning(f"REQUOTE/PRICE_OFF ({result.retcode}): Tentativa {attempt}/{max_retries}. Ajustando preço...")
                
                # Obter preço atualizado instantaneamente
                tick = mt5.symbol_info_tick(params['symbol'])
                if tick:
                    # Ajustar preço mantendo a direção
                    new_price = tick.ask if params['type'] in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT] else tick.bid
                    
                    # Se for LIMIT, talvez queiramos ser um pouco mais agressivos na retentativa
                    # mas para este escopo, apenas atualizamos para o novo preço de mercado
                    params['price'] = new_price
                    # Recalcular SL/TP se necessário (geralmente mantemos o offset original se for relativo)
                    # No RiskManager, SL/TP são absolutos, então precisamos deslocar junto com o preço
                    diff = new_price - result.request.price
                    if params['sl'] > 0: params['sl'] += diff
                    if params['tp'] > 0: params['tp'] += diff
                
                continue # Próxima tentativa no loop
            
            # Se for outro erro (ex: Limites Rejeitados 10014, Saldo Insuficiente 10019...)
            logging.error(f"Erro Crítico MT5 ({result.retcode}): {result.comment}")
            return result
            
        return result

    def place_limit_order(self, symbol, order_type, price, volume, sl=0.0, tp=0.0, comment="HFT Limit"):
        """
        Envia uma Ordem Limitada (Pending Order) para o book.
        Retorna o result object do MT5.
        """
        if not self.connected: return None

        # Normalização de Preço (Tick Size)
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logging.error(f"Símbolo {symbol} não encontrado para normalização.")
            return None
            
        tick_size = symbol_info.trade_tick_size
        if tick_size > 0:
            price = round(price / tick_size) * tick_size
            if sl > 0: sl = round(sl / tick_size) * tick_size
            if tp > 0: tp = round(tp / tick_size) * tick_size

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "sl": float(sl),
            "tp": float(tp),
            "type_time": mt5.ORDER_TIME_DAY, # Expira no final do dia se não cancelada antes
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "comment": comment,
            "magic": 123456,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Falha ao enviar Limit Order: {result.comment} ({result.retcode})")
        else:
            logging.info(f"LIMIT ORDER ENVIADA: {symbol} {volume} @ {price} (Ticket: {result.order})")
        
        return result

    def cancel_order(self, ticket):
        """Cancela uma ordem pendente pelo ticket."""
        if not self.connected: return False

        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": int(ticket),
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.warning(f"Falha ao cancelar ordem {ticket}: {result.comment}")
            return False
            
        logging.info(f"ORDEM CANCELADA: {ticket}")
        return True

    def check_order_status(self, ticket):
        """
        Verifica o estado de uma ordem.
        Retorna: 'FILLED', 'PENDING', 'CANCELED', 'UNKNOWN'
        """
        if not self.connected: return "UNKNOWN"
        
        # 1. Checar se está PENDENTE (Active)
        orders = mt5.orders_get(ticket=ticket)
        if orders and len(orders) > 0:
            return "PENDING"
            
        # 2. Checar se foi FINALIZADA (History)
        from_date = datetime.now() - timedelta(days=1)
        hist_orders = mt5.history_orders_get(from_date, datetime.now(), ticket=ticket)
        
        if hist_orders and len(hist_orders) > 0:
            state = hist_orders[0].state
            if state == mt5.ORDER_STATE_FILLED:
                return "FILLED"
            elif state == mt5.ORDER_STATE_CANCELED:
                return "CANCELED"
            elif state == mt5.ORDER_STATE_PARTIAL:
                return "PARTIAL"
            else:
                return f"STATE_{state}"
                
        return "UNKNOWN"

    def close_position(self, ticket):
        """Fecha uma posição aberta pelo ticket (B3 Netting)."""
        if not self.connected: return False
        
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logging.warning(f"Posição {ticket} não encontrada para fechamento.")
            return False
            
        pos = positions[0]
        symbol = pos.symbol
        lots = pos.volume
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick: return False
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": order_type,
            "position": int(ticket),
            "price": float(price),
            "deviation": 20,
            "magic": 123456,
            "comment": "CLOSE AUTO",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC if "WIN" in symbol or "WDO" in symbol else mt5.ORDER_FILLING_RETURN,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Erro ao fechar posição {ticket}: {result.comment}")
            return False
            
        logging.info(f"POSIÇÃO FECHADA: {ticket} {symbol} {lots} lotes")
        return True

    def update_sltp(self, ticket, sl, tp):
        """Atualiza o Stop Loss e Take Profit de uma posição."""
        if not self.connected: return False
        
        positions = mt5.positions_get(ticket=ticket)
        if not positions: return False
        pos = positions[0]
        
        symbol_info = mt5.symbol_info(pos.symbol)
        if symbol_info:
            tick_size = symbol_info.trade_tick_size
            if tick_size > 0:
                sl = round(sl / tick_size) * tick_size
                tp = round(tp / tick_size) * tick_size

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": int(ticket),
            "sl": float(sl),
            "tp": float(tp),
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Erro ao atualizar SL/TP {ticket}: {result.comment}")
            return False
            
        return True

    def close_all_positions(self, symbol=None):
        """Fecha todas as posições abertas. Se symbol for fornecido, apenas desse símbolo."""
        if not self.connected: return False
        
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions:
            for pos in positions:
                self.close_position(pos.ticket)
        return True

    def get_current_symbol(self, base="WIN"):
        """
        Retorna o símbolo ATUAL do WIN com base na regra B3 de liquidez.
        Regra de Série: G(Fev), J(Abr), M(Jun), Q(Ago), V(Out), Z(Dez).
        Vencimento Oficial: 4ª feira mais próxima do dia 15.
        Rollover HFT: Troca se Vol(Prox) > Vol(Atual) + 20%.
        """
        if base not in ["WIN", "WDO"]:
             return f"{base}$"

        try:
            now = datetime.now()
            year_short = str(now.year)[2:]
            expiry_map = { 2: 'G', 4: 'J', 6: 'M', 8: 'Q', 10: 'V', 12: 'Z' }
            
            # --- 1. Calcular Vencimento Oficial do Mês Corrente/Próximo ---
            def get_expiry_date(y, m):
                # Regra B3: Quarta-feira mais próxima do dia 15
                base = datetime(y, m, 15)
                wd = base.weekday() # 0=Seg, 2=Qua, 6=Dom
                
                # Se for Domingo (6), a próxima 4ª (dist 3) é mais perto que a anterior (dist 4)
                if wd == 6:
                    return base + timedelta(days=3)
                
                # Para Seg(0), Ter(1): Avança para Qua(2)
                elif wd < 2:
                    return base + timedelta(days=(2 - wd))
                
                # Para Qui(3), Sex(4), Sab(5): Recua para Qua(2)
                elif wd > 2:
                    return base - timedelta(days=(wd - 2))
                    
                return base

            # Determinar mês par de referência
            candidate_month = now.month
            if candidate_month % 2 != 0:
                candidate_month += 1
            
            # Ajuste de ano para Dezembro
            year_calc = now.year
            if now.month == 12 and candidate_month == 2:
                year_short = str(year_calc + 1)[2:]
                year_calc += 1
            elif candidate_month > 12:
                candidate_month = 2
                year_short = str(year_calc + 1)[2:]
                year_calc += 1

            expiry_date = get_expiry_date(year_calc, candidate_month)

            # --- 2. Verificar se já venceu (com margem de segurança pós-pregão 18h) ---
            # Se hoje > vencimento, pegar o PRÓXIMO
            if now > expiry_date + timedelta(hours=18):
                candidate_month += 2
                if candidate_month > 12:
                    candidate_month = 2
                    year_short = str(int(year_short) + 1)[-2:]
                
            current_letter = expiry_map[candidate_month]
            current_symbol = f"{base}{current_letter}{year_short}"
            
            # --- 3. Checagem de Liquidez (HFT Rollover) ---
            # Verificar contrato SEGUINTE para ver se a liquidez já migrou
            next_month = candidate_month + 2
            next_year_s = year_short
            if next_month > 12:
                next_month = 2
                next_year_s = str(int(year_short) + 1)[-2:]
            
            next_letter = expiry_map[next_month]
            next_symbol = f"{base}{next_letter}{next_year_s}"
            
            # Só verifica volume se estivermos na semana do vencimento (7 dias antes)
            days_to_expiry = (expiry_date - now).days
            if -2 <= days_to_expiry <= 7:
                if self.connected:
                    vol_curr = self.get_daily_volume(current_symbol)
                    vol_next = self.get_daily_volume(next_symbol)
                    
                    if vol_next > (vol_curr * 1.2): # 20% mais volume no novo
                        logging.warning(f"ROLLOVER DETECTADO: Migrando {current_symbol} -> {next_symbol} (Vol: {vol_next} vs {vol_curr})")
                        return next_symbol
            
            return current_symbol

        except Exception as e:
            logging.error(f"Erro ao calcular simbolo WIN: {e}")
            return f"{base}$" # Fallback genérico

    def get_market_data(self, symbol, timeframe=mt5.TIMEFRAME_M1, n_candles=100):
        """Coleta candles históricos e retorna como DataFrame."""
        if not self.connected: return pd.DataFrame()
        
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_candles)
        if rates is None or len(rates) == 0:
            logging.error(f"Erro ao obter rates para {symbol}: {mt5.last_error()}")
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        # Localização para Brasília (GMT-3)
        df['time'] = df['time'] - timedelta(hours=3)
        return df

    def get_synchronized_multi_asset_data(self, symbols, n_candles=60):
        """
        Coleta e sincroniza dados de múltiplos ativos para inferência multi-variável.
        Retorna um DataFrame com as colunas sincronizadas pelo timestamp.
        """
        if not self.connected: return None
        
        dfs = {}
        for sym in symbols:
            df = self.get_market_data(sym, n_candles=n_candles + 10) # Pegar um pouco a mais para garantir o merge
            if not df.empty:
                df = df.drop_duplicates(subset='time').set_index('time')
                # Normalização de Nomes para o Modelo SOTA (Mantém consistência WIN$ e WDO$)
                clean_name = sym
                if "WIN" in sym.upper(): clean_name = "WIN$"
                elif "WDO" in sym.upper(): clean_name = "WDO$"
                
                dfs[clean_name] = df[['close']].rename(columns={'close': f'close_{clean_name}'})
        
        if not dfs: return pd.DataFrame()
        
        # Merge sincronizado (Inner Join)
        master_df = pd.concat(dfs.values(), axis=1, join='inner')
        master_df = master_df.sort_index().tail(n_candles)
        
        # Normalização Z-Score Local (para o pacote de inferência)
        master_df = (master_df - master_df.mean()) / (master_df.std() + 1e-8)
        
        return master_df

    def get_time_and_sales(self, symbol, n_ticks=100):
        """Coleta os últimos negócios realizados (Time & Sales) como DataFrame."""
        if not self.connected: return pd.DataFrame()
        
        ticks = mt5.copy_ticks_from(symbol, datetime.utcnow(), n_ticks, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0: return pd.DataFrame()
        
        df = pd.DataFrame(ticks)
        # Sincronização Brasília (GMT-3)
        df['time_dt'] = pd.to_datetime(df['time'], unit='s') - timedelta(hours=3)
        df['time_str'] = df['time_dt'].dt.strftime('%H:%M:%S')
        return df

    def get_order_book(self, symbol):
        """Retorna o book de ofertas atualizado (Snapshot L2)."""
        if not self.connected: return {"bids": [], "asks": []}
        
        # Inscreve para receber atualizações do book se necessário
        mt5.market_book_add(symbol)
        book = mt5.market_book_get(symbol)
        if book is None:
            return {"bids": [], "asks": []}
            
        bids = []
        asks = []
        
        for item in book:
            order_data = {"price": item.price, "volume": item.volume}
            if item.type == mt5.BOOK_TYPE_SELL:
                asks.append(order_data)
            elif item.type == mt5.BOOK_TYPE_BUY:
                bids.append(order_data)
        
        # Ordenar: Bids Decrescente (melhor preço primeiro), Asks Crescente
        return {
            "bids": sorted(bids, key=lambda x: x['price'], reverse=True),
            "asks": sorted(asks, key=lambda x: x['price'])
        }
    
    def get_daily_volume(self, symbol):
        """Helper para pegar volume do dia."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1)
            if rates is not None and len(rates) > 0:
                return rates[0]['tick_volume']
            return 0
        except:
            return 0

    def get_daily_realized_profit(self):
        """Calcula o lucro realizado no dia (00:00 até agora)."""
        if not self.connected: return 0.0
        try:
            now = datetime.utcnow()
            start_of_day = datetime(now.year, now.month, now.day)
            deals = mt5.history_deals_get(start_of_day, now + timedelta(hours=1)) # Margem de segurança
            
            if deals is None or len(deals) == 0:
                return 0.0
                
            total_profit = 0.0
            for deal in deals:
                # Filtrar deals de entrada/saída, ignorar depósitos se houver
                if deal.type in [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]:
                    total_profit += deal.profit + deal.swap + deal.commission
                    
            return total_profit
        except Exception as e:
            logging.error(f"Erro ao calcular lucro diário: {e}")
            return 0.0

    def get_trading_performance(self):
        """
        Calcula as estatísticas de performance diária acessando o histórico de deals do MT5.
        Retorna: Win Rate (%), Profit Factor, Trades Totais, Gross Profit, Gross Loss, Net Profit.
        """
        default_stats = {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "net_profit": 0.0
        }
        if not self.connected: return default_stats
        
        try:
            now = datetime.utcnow()
            start_of_day = datetime(now.year, now.month, now.day)
            deals = mt5.history_deals_get(start_of_day, now + timedelta(hours=1))
            
            if deals is None or len(deals) == 0:
                return default_stats
                
            total_trades = 0
            winning_trades = 0
            gross_profit = 0.0
            gross_loss = 0.0
            net_profit = 0.0
            
            for deal in deals:
                if deal.type in [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]:
                    # MT5 deals de SAÍDA (fechamento de posição) representam um trade finalizado.
                    # Vamos considerar DEAL_ENTRY_OUT ou INOUT. 
                    if deal.entry in [mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT]:
                        deal_profit = deal.profit + deal.swap + deal.commission
                        total_trades += 1
                        net_profit += deal_profit
                        
                        if deal_profit > 0:
                            winning_trades += 1
                            gross_profit += deal_profit
                        elif deal_profit < 0:
                            gross_loss += abs(deal_profit)
                            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            # Se não houver gross loss mas houver gross profit, define profit_factor como o gross_profit
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
            
            return {
                "total_trades": total_trades,
                "win_rate": round(win_rate, 2),
                "profit_factor": round(profit_factor, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "net_profit": round(net_profit, 2)
            }
        except Exception as e:
            logging.error(f"Erro ao calcular performance historica: {e}")
            return default_stats

    def get_settlement_price(self, symbol):
        """Retorna o preço de ajuste (Settlement) do dia anterior."""
        if not self.connected: return 0.0
        
        info = mt5.symbol_info(symbol)
        if not info: return 0.0
        
        # Tenta pegar do session_price_ref (geralmente é o ajuste na B3) usando getattr para segurança
        # Se o atributo não existir ou for zero, tenta pegar o prev_close
        settlement = getattr(info, 'session_price_ref', 0.0)
        if settlement <= 0:
             settlement = getattr(info, 'prev_close', 0.0)
             
        return settlement

    def get_bluechips_data(self):
        """
        Lê a variação percentual intradiária das Blue Chips.
        Usa Candle D1 Open para precisão máxima.
        """
        if not self.connected:
            return {}
        
        tickers = ["VALE3", "PETR4", "ITUB4", "BBDC4", "ELET3"]
        data = {}

        for symbol in tickers:
            try:
                if not mt5.symbol_select(symbol, True):
                    continue

                tick = mt5.symbol_info_tick(symbol)
                # Pegar candle D1 do dia atual (índice 0 com data especifica ou from_pos)
                # copy_rates_from_pos(msg, timeframe, start_pos, count)
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1)

                if tick and rates is not None and len(rates) > 0:
                    open_price = rates[0]['open']
                    current_price = tick.last
                    
                    if open_price > 0:
                        variation = ((current_price - open_price) / open_price) * 100
                        data[symbol] = round(variation, 2)
                    else:
                        data[symbol] = 0.0
                else:
                    data[symbol] = 0.0
            except Exception:
                data[symbol] = 0.0
        
        return data

    def get_macro_data(self):
        """
        Coleta variação percentual do S&P 500 para filtro Macro.
        Tenta símbolos comuns: WSP (Micro B3), US500, SPX, ISP.
        """
        if not self.connected:
            return 0.0

        candidates = ["WSP", "US500", "SPX", "ISP", "SP500"]
        macro_symbol = None
        
        # Tenta encontrar um símbolo válido
        if self._macro_symbol_cache:
            macro_symbol = self._macro_symbol_cache
        else:
            # Tenta encontrar um símbolo válido
            for sym in candidates:
                info = mt5.symbol_info(sym)
                if info is not None:
                    macro_symbol = sym
                    self._macro_symbol_cache = sym
                    break
            
            if macro_symbol is None:
                wsp_futures = self.get_current_symbol(base="WSP")
                if wsp_futures:
                    macro_symbol = wsp_futures
                    self._macro_symbol_cache = wsp_futures

        if macro_symbol is None:
            # logging.warning("Macro Monitor: Nenhum símbolo do S&P 500 encontrado.")
            return 0.0
            
        # Pega variação diária
        # Preço de fechamento ontem vs atual
        rates = mt5.copy_rates_from_pos(macro_symbol, mt5.TIMEFRAME_D1, 0, 2)
        if rates is None or len(rates) < 2:
            return 0.0
            
        close_yesterday = rates[0]['close']
        current_price = rates[1]['close'] # Ou 'close' do candle D1 atual que é o preço corrente
        
        if close_yesterday == 0:
            return 0.0
            
        change_pct = ((current_price - close_yesterday) / close_yesterday) * 100
        return change_pct

    def get_bulk_ticks(self, symbol, n=1000):
        """
        Coleta os últimos N ticks para análise de microestrutura (CVD).
        Retorna DataFrame com flags de agressão.
        """
        if not self.connected:
            return None
            
        # copy_ticks_from(symbol, from_date, count, flags)
        # Usamos time.time() * 1000 se fosse data, mas copy_ticks_from pede data datetime ou timestamp?
        # Melhor usar copy_ticks_from com data futura (pra pegar os últimos) ou copy_ticks_range?
        # mt5.copy_ticks_from(symbol, datetime.now(), n, mt5.COPY_TICKS_ALL) pega DO PASSADO a partir da data.
        # Então datetime.now() pega os últimos N.
        
        ticks = mt5.copy_ticks_from(symbol, datetime.utcnow(), n, mt5.COPY_TICKS_ALL)
        if ticks is None:
            logging.error(f"Erro ao obter ticks para {symbol}: {mt5.last_error()}")
            return pd.DataFrame()
            
        df = pd.DataFrame(ticks)
        df['time'] = pd.to_datetime(df['time'], unit='s') - timedelta(hours=3)
        return df

    # get_order_book unificado no topo

if __name__ == "__main__":
    # Teste de conexão básico
    bridge = MT5Bridge()
    if bridge.connect():
        symbol = bridge.get_current_symbol("WIN")
        print(f"Símbolo detectado: {symbol}")
        if symbol:
            data = bridge.get_market_data(symbol)
            print("Últimos dados:")
            print(data.tail())
        
        # Manter conexão aberta por 2 segundos para teste
        time.sleep(2)
        bridge.disconnect()
