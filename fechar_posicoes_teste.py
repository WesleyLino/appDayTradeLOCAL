import MetaTrader5 as mt5
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")


def force_close_all():
    if not mt5.initialize():
        logging.error("Falha ao conectar MT5")
        return

    positions = mt5.positions_get()
    if not positions:
        logging.info("A conta está zerada. Nenhuma posição aberta. Seguro!")
        mt5.shutdown()
        return

    for pos in positions:
        symbol = pos.symbol
        lots = pos.volume
        order_type = (
            mt5.ORDER_TYPE_SELL
            if pos.type == mt5.POSITION_TYPE_BUY
            else mt5.ORDER_TYPE_BUY
        )

        tick = mt5.symbol_info_tick(symbol)
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": order_type,
            "position": pos.ticket,
            "price": float(price),
            "deviation": 20,
            "magic": 123456,
            "comment": "FORCE CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
            if "WIN" in symbol or "WDO" in symbol
            else mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(
                f"O teste fechou a posição pendente ({lots} lotes) em {symbol}."
            )
        else:
            logging.error(
                f"Erro ao forçar fechamento: {result.comment if result else 'None'}"
            )

    mt5.shutdown()


if __name__ == "__main__":
    force_close_all()
