import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
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
        self.connected = False
        self.broker = "Genial Investimentos"
        self.mt5 = mt5 # Expor módulo para acesso externo (HFT)
        
    def connect(self):
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

    def get_current_symbol(self, base="WIN"):
        """
        Detecta automaticamente o símbolo atual do Mini Índice ou Mini Dólar.
        Implementação simplificada para B3 (WIN / WDO).
        """
        logging.info(f"Buscando símbolo atual para base: {base}")
        
        # Obter todos os símbolos que começam com a base
        symbols = mt5.symbols_get(group=f"*{base}*")
        
        if not symbols:
            logging.warning(f"Nenhum símbolo encontrado para base {base}")
            return None

        # Filtra símbolos que começam com a base e têm tamanho 6 (ex: WING24, WDOJ24)
        # Ignora opções ou outros derivativos complexos por enquanto
        futures = [s for s in symbols if s.name.startswith(base) and len(s.name) == 6]
        
        if not futures:
            logging.warning("Nenhum contrato futuro específico encontrado. Tentando retornar o primeiro da lista geral.")
            return symbols[0].name if symbols else None
            
        # Ordena por data de expiração (mais próxima/atual)
        # O contrato atual geralmente é o que tem expiração futura mais próxima, mas maior que hoje
        futures.sort(key=lambda x: x.expiration_time)
        
        # Pega o primeiro contrato com expiração futura (ou o último da lista se todos expiraram - edge case)
        now = datetime.now().timestamp()
        valid_futures = [s for s in futures if s.expiration_time > now]
        
        chosen_symbol = valid_futures[0].name if valid_futures else futures[-1].name
        
        logging.info(f"Símbolo selecionado: {chosen_symbol}")
        
        # Garante que o símbolo esteja visível no Market Watch para receber dados
        if not mt5.symbol_select(chosen_symbol, True):
             logging.error(f"Falha ao selecionar símbolo {chosen_symbol} no Market Watch")
             
        return chosen_symbol
    
    def get_market_data(self, symbol, timeframe=mt5.TIMEFRAME_M1, n_candles=60):
        """Retorna os últimos n candles para o símbolo especificado."""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n_candles)
        if rates is None:
            logging.error(f"Erro ao obter rates para {symbol}: {mt5.last_error()}")
            return None
            
        df = pd.DataFrame(rates)

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
        for sym in candidates:
            # Tenta pegar info (checa existência)
            info = mt5.symbol_info(sym) # type: ignore
            # Pode ser que precise de prefixo/sufixo dependendo da corretora, 
            # mas WSP geralmente é padrão na B3.
            # Se não achar exato, tenta com wildcard (lógica simplificada aqui)
            if info is not None:
                macro_symbol = sym
                break
        
        # Se não achou nenhum exato, tenta buscar nos símbolos disponíveis que contêm 'SP' ou '500'
        # (Fallback custoso, evitar em loop rápido, fazer cache se possível)
        if macro_symbol is None:
             # Tenta achar o atual (ex: WSPH24)
             wsp_futures = self.get_current_symbol(base="WSP")
             if wsp_futures:
                 macro_symbol = wsp_futures

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
        # Asks: Menor preço primeiro (Topo do book)
        asks.sort(key=lambda x: x['price'])
        
        return {"bids": bids, "asks": asks}

    def get_time_and_sales(self, symbol, n_ticks=100):
        """Retorna os últimos negócios realizados (agressão)."""
        ticks = mt5.copy_ticks_from_pos(symbol, datetime.now(), n_ticks, mt5.COPY_TICKS_ALL)
        if ticks is None:
            return None
        return pd.DataFrame(ticks)

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
