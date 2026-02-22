import asyncio
import logging
import time
from mt5_bridge import MT5Bridge
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    logging.info("=========== TESTE DE ROTEAMENTO (WDO) ===========")
    bridge = MT5Bridge()
    if not bridge.connect():
        logging.error("Falha ao conectar na corretora pela MT5 Bridge.")
        return
    
    # Vamos usar WDO como padrão para o teste
    symbol = "WDO$N" # Dólar contínuo ou mude para o contrato vigente (ex: WDOH24)
    # Tenta descobrir o contrato do dólar pelo MT5
    symbols = mt5.symbols_get()
    wdo_symbols = [s.name for s in symbols if s.name.startswith("WDO")]
    if not wdo_symbols:
         logging.error("Nenhum contrato WDO encontrado para o teste.")
         return
    
    # Filtra contratos vigentes (6 caracteres, ignorar M2 e WDO$N)
    valid_symbols = [s for s in wdo_symbols if len(s) == 6 and s[3] in "FGHJKMNQUVXZ"]
    symbol_test = "WDO$N"
    tick = None
    if valid_symbols:
        logging.info(f"Testando tick de cotação real nos ativos vigentes: {valid_symbols}")
        # Testa do último para o primeiro (geralmente os de vencimentos distantes são os de letras maiores, ex: H, J, etc)
        # Mais seguro testar a cotação real.
        for s in valid_symbols:
            t = bridge.mt5.symbol_info_tick(s)
            if t is not None and t.ask > 0:
                symbol_test = s
                tick = t
                break
    else:
        symbol_test = "WDO$N"
        tick = bridge.mt5.symbol_info_tick(symbol_test)
        
    logging.info(f"Ativo de Teste Escolhido com Liquidez: {symbol_test}")
    
    if not tick:
        logging.error(f"Erro ao obter tick para todos os ativos testados (incluindo {symbol_test}). Terminal aberto no ativo com cotações chegando?")
        return

    # Ordem Simples de Compra a Mercado (1 Lote) com spread zero virtual
    price = tick.ask
    logging.info(f"Preço Ask atual: {price}")
    
    # 1 ponto de spread/SL no WDO = R$ 10 de risco máximo
    sl = price - 1.0 
    
    params = {
        "action": bridge.mt5.TRADE_ACTION_DEAL,
        "symbol": symbol_test,
        "volume": 1.0,
        "type": bridge.mt5.ORDER_TYPE_BUY,
        "price": price,
        "sl": sl,
        "tp": 0.0,
        "deviation": 5,                       
        "magic": 1337,                        
        "comment": "TESTE_ROTEAMENTO_HFT",
        "type_time": bridge.mt5.ORDER_TIME_GTC,    
        "type_filling": bridge.mt5.ORDER_FILLING_RETURN, # B3 usa RETURN ou FOK
    }

    logging.info(f"Submetendo Pacote FIX p/ Corretora: {params}")
    
    # Usando place_resilient_order para testar retentativas se requote
    t0 = time.time()
    result = bridge.place_resilient_order(params)
    latency_ms = (time.time() - t0) * 1000
    
    if result is None:
        logging.error("Falha crítica: Retorno None")
        return

    if result.retcode == bridge.mt5.TRADE_RETCODE_DONE:
        logging.info(f"✅ ORDEM EXECUTADA B3: TICKET {result.order}")
        logging.info(f"⚡ Latência End-to-End da Corretora: {latency_ms:.2f}ms")
        
        logging.warning("⏳ Aguardando 3 segundos de teste de mercado antes do Panic Close...")
        await asyncio.sleep(3.0)
        
        logging.warning("🔪 FECHANDO POSIÇÃO (PANIC CLOSE) PARA BLINDAGEM DO TESTE!")
        bridge.close_position(result.order)
    else:
         logging.error(f"❌ ORDEM REJEITADA ({result.retcode}): {result.comment}")

if __name__ == "__main__":
    asyncio.run(main())
