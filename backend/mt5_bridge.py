import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import logging
import time

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend/trading_bridge.log"),
        logging.StreamHandler()
    ]
)

class MT5Bridge:
    def __init__(self):
        self.mt5 = mt5 # Expor módulo para acesso externo (HFT)
        self.connected = False
        self._macro_symbol_cache = None # [HFT v2.1] Cache para evitar busca repetitiva

        """Estabelece conexão com o MetaTrader 5 local."""
        if not mt5.initialize():
            logging.error(f"Falha ao inicializar MT5: {mt5.last_error()}")
            return False
        
        # Verificar se está conectado à corretora correta
        account_info = mt5.account_info()
        if account_info is None:
            logging.error("Não foi possível obter informações da conta.")
            self.disconnect()
            return False
            
        logging.info(f"Conectado com sucesso!")
        logging.info(f"Corretora: {account_info.company}")
        logging.info(f"Conta: {account_info.login}")
        logging.info(f"Saldo: R$ {account_info.balance:.2f}")
        
        # No ambiente local do usuário, validamos se a corretora contém 'Genial'
        if "Genial" not in account_info.company:
            logging.warning(f"Atenção: A corretora detectada é '{account_info.company}', mas o plano foca na Genial.")

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
                logging.error(f"MT5 order_send retornou None inesperadamente.")
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
            now = datetime.now()
            start_of_day = datetime(now.year, now.month, now.day)
            deals = mt5.history_deals_get(start_of_day, now)
            
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

    def get_settlement_price(self, symbol):
        """Retorna o preço de ajuste (Settlement) do dia anterior."""
        if not self.connected: return 0.0
        
        info = mt5.symbol_info(symbol)
        if not info: return 0.0
        
        # Tenta pegar do session_price_ref (geralmente é o ajuste na B3)
        # Se for zero, tenta pegar o prev_close
        settlement = info.session_price_ref
        if settlement <= 0:
             settlement = info.prev_close
             
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
        
        ticks = mt5.copy_ticks_from(symbol, datetime.now(), n, mt5.COPY_TICKS_ALL)
        if ticks is None:
            logging.error(f"Erro ao obter ticks para {symbol}: {mt5.last_error()}")
            return None
            
        df = pd.DataFrame(ticks)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_order_book(self, symbol):
        """Retorna o estado atual do Book de Ofertas (Separado em Bids/Asks)."""
        # Inscreve para receber atualizações do book se necessário
        mt5.market_book_add(symbol)
        book = mt5.market_book_get(symbol)
        if book is None:
            return {"bids": [], "asks": []}
            
        bids = []
        asks = []
        for b in book:
            item = {"price": b.price, "volume": b.volume}
            if b.type == mt5.BOOK_TYPE_SELL:
                asks.append(item)
            else: # BOOK_TYPE_BUY or others
                bids.append(item)
                
        # Ordenação padrão:
        # Bids: Maior preço primeiro (Topo do book)
        bids.sort(key=lambda x: x['price'], reverse=True)
    def update_sltp(self, ticket, sl, tp):
        """Modifica SL/TP de uma posição existente."""
        if not self.connected: return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": float(sl),
            "tp": float(tp),
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Falha ao atualizar SL/TP (Ticket {ticket}): {result.comment}")
            return False
            
        return True

    def close_position(self, ticket):
        """
        Encerra uma posição aberta (B3 Netting).
        Informa o ticket e envia ordem oposta para zeragem.
        """
        if not self.connected: return False

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logging.warning(f"Fechar Posição: Ticket {ticket} não encontrado.")
            return False
        
        pos = positions[0]
        symbol = pos.symbol
        volume = pos.volume
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 5,
            "magic": 123456,
            "comment": "ZEZERAGEM SOTA (EXIT)",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Falha ao fechar posição {ticket}: {result.comment}")
            return False
            
        logging.info(f"POSIÇÃO ENCERRADA: Ticket {ticket} ({symbol})")
        return True

    def validate_order_compliance(self, symbol, price):
        """
        Valida se o preço da ordem está dentro dos limites de oscilação permitidos pela B3.
        Retorna (bool, str): (Aprovado, Motivo)
        """
        if not self.connected:
             return False, "MT5 não conectado."
             
        info = mt5.symbol_info(symbol)
        if info is None:
            return False, f"Símbolo {symbol} não encontrado."
            
        # Limites informados pela corretora/bolsa
        lower_limit = info.session_price_limit_min
        upper_limit = info.session_price_limit_max
        
        # Fallback se os limites não estiverem preenchidos (comum em contas demo ou fora de hora)
        if lower_limit == 0 or upper_limit == 0:
            logging.warning(f"Limites de sessão zerados para {symbol}. Calculando manual base regras.")
            ref_price = info.session_price_ref if info.session_price_ref > 0 else info.last
            
            if ref_price > 0:
                if "WIN" in symbol or "IND" in symbol:
                    limit_pct = 0.10 # 10%
                elif "WDO" in symbol or "DOL" in symbol:
                    limit_pct = 0.06 # 6%
                else:
                    limit_pct = 0.05 # Default 5% para ações
                
                lower_limit = ref_price * (1 - limit_pct)
                upper_limit = ref_price * (1 + limit_pct)
            else:
                 return True, "AVISO: Sem referência de preço para validação. Ordem permitida com risco."

        # Se preço for 0 (Market Order), assumimos que será executado no preço atual, 
        # que teoricamente já está dentro do túnel, mas idealmente deveríamos checar o last.
        if price == 0:
            price = info.last

        if price < lower_limit:
            return False, f"REJEITADO: Preço {price} abaixo do limite inferior do túnel ({lower_limit:.2f})."
        
        if price > upper_limit:
            return False, f"REJEITADO: Preço {price} acima do limite superior do túnel ({upper_limit:.2f})."
            
        return True, f"OK: Dentro dos limites ({lower_limit:.2f} - {upper_limit:.2f})"

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
