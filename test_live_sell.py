import logging
import time
from backend.mt5_bridge import MT5Bridge
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def run_ping_test_sell():
    logging.info("Iniciando Teste Rápido de Roteamento MT5 (VENDA)...")
    bridge = MT5Bridge()

    if not bridge.connect():
        logging.error("Falha ao conectar no MetaTrader 5.")
        return

    # Buscar ativo atual
    symbol = bridge.get_current_symbol("WIN")
    logging.info(f"Ativo atual selecionado para o teste: {symbol}")

    # Injetar ativo no market watch, se necessário
    if not mt5.symbol_select(symbol, True):
        logging.error(f"Falha ao selecionar {symbol} no Market Watch.")
        bridge.disconnect()
        return

    # Validar volume e enviar
    volume = 1.0
    logging.info(f"Enviando ordem a mercado VENDA (SELL) -> {volume} lote de {symbol}")

    # Place market order returns o order_send result
    result = bridge.place_market_order(
        symbol, mt5.ORDER_TYPE_SELL, volume, sl=0.0, tp=0.0, comment="PING TEST SELL"
    )

    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        ticket = result.deal
        logging.info(
            f"SUCESSO! Ordem de venda executada no MT5. Ticket do Deal: {ticket}"
        )
        logging.info("Aguardando 1 segundo (Ping de Roteamento)...")
        time.sleep(1)

        # Como bridge usa pos.ticket (Position ID que geralmente é o order ticket de abertura)
        pos_ticket = result.order
        logging.info(f"Zerando a posição de venda a mercado (CLOSING {pos_ticket})...")

        closed = bridge.close_position(pos_ticket)
        if closed:
            logging.info(
                "SUCESSO ABSOLUTO! O Circuito de Venda -> Encerramento de Posições está perfeito."
            )
        else:
            logging.error(
                "Falha ao fechar posição de venda instantaneamente. VERIFIQUE SEU PAINEL DO MT5."
            )
    else:
        logging.error(
            f"Falha ao executar ordem de venda inicial. Retcode: {result.retcode if result else 'N/A'}"
        )

    bridge.disconnect()
    logging.info("Teste de Venda Finalizado.")


if __name__ == "__main__":
    run_ping_test_sell()
