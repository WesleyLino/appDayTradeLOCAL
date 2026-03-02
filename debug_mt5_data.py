import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd

def debug_data():
    if not mt5.initialize():
        print("Erro ao inicializar MT5")
        return

    symbol = "WIN$"
    timeframe = mt5.TIMEFRAME_M1
    
    # Verificar última vela disponível
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
    if rates is not None and len(rates) > 0:
        last_time = datetime.fromtimestamp(rates[0][0])
        print(f"Última vela disponível no MT5 para {symbol}: {last_time}")
    else:
        print(f"Não foi possível obter dados para {symbol}")

    # Verificar dados no range solicitado
    date_from = datetime(2026, 2, 19)
    date_to = datetime(2026, 2, 27, 23, 59)
    
    rates_range = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates_range is not None:
        print(f"Total de velas no range (19/02 a 27/02): {len(rates_range)}")
        if len(rates_range) > 0:
            first = datetime.fromtimestamp(rates_range[0][0])
            last = datetime.fromtimestamp(rates_range[-1][0])
            print(f"Primeira vela no range: {first}")
            print(f"Última vela no range: {last}")
    else:
        print("Erro ao coletar dados no range solicitado.")

    mt5.shutdown()

if __name__ == "__main__":
    debug_data()
