import MetaTrader5 as mt5
from datetime import datetime, timedelta

if not mt5.initialize():
    print("Erro ao inicializar MT5")
    quit()

symbol = "WIN$"
date_from = datetime(2026, 2, 27, 9, 0)
date_to = datetime(2026, 2, 27, 18, 0)

rates = mt5.copy_rates_range(
    symbol,
    mt5.TIMEFRAME_M1,
    date_from + timedelta(hours=3),
    date_to + timedelta(hours=3),
)

if rates is None or len(rates) == 0:
    print(f"Sem dados para {symbol} em {date_from}")
    # Tenta resolver o contrato real
    print("Tentando resolver contrato real...")
    # No bridge temos get_current_symbol, mas vamos tentar manual
    s_test = "WING26"
    rates = mt5.copy_rates_range(
        s_test,
        mt5.TIMEFRAME_M1,
        date_from + timedelta(hours=3),
        date_to + timedelta(hours=3),
    )
    if rates is not None and len(rates) > 0:
        print(f"Dados encontrados para {s_test}!")
    else:
        print(f"Sem dados para {s_test} também.")
else:
    print(f"Dados encontrados para {symbol}: {len(rates)} candles")

mt5.shutdown()
