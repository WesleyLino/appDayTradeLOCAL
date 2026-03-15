import MetaTrader5 as mt5


def check_history():
    if not mt5.initialize():
        print("Falha ao inicializar MT5")
        return

    symbol = "WIN$"
    if not mt5.symbol_select(symbol, True):
        print(f"Símbolo {symbol} não encontrado")
        mt5.shutdown()
        return

    # Tenta pegar o máximo possível de candles
    # No MT5, podemos pedir por data
    import datetime
    from datetime import timezone

    utc_from = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=365)
    utc_to = datetime.datetime.now(timezone.utc)

    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)

    if rates is None or len(rates) == 0:
        print(f"Erro ao copiar rates para {symbol}")
        # Tenta pegar os últimos N candles
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 140000)
        if rates is not None:
            print(f"Conseguimos obter {len(rates)} candles usando copy_rates_from_pos")
        else:
            print("Falha total na obtenção de dados históricos via pos.")
    else:
        print(
            f"Histórico disponível para {symbol}: {len(rates)} candles (M1) nos últimos 365 dias."
        )

    mt5.shutdown()


if __name__ == "__main__":
    check_history()
