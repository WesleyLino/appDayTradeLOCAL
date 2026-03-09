import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

def test_bluechips():
    if not mt5.initialize():
        print("Falha ao inicializar MT5")
        return

    tickers = ["VALE3", "PETR4", "ITUB4", "BBDC4", "ELET3"]
    print(f"{'Ticker':<10} | {'Open':<10} | {'Last':<10} | {'Variation %':<12}")
    print("-" * 50)
    
    for symbol in tickers:
        selected = mt5.symbol_select(symbol, True)
        if not selected:
            print(f"{symbol:<10} | NÃO SELECIONADO")
            continue
            
        tick = mt5.symbol_info_tick(symbol)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1)
        
        if tick and rates is not None and len(rates) > 0:
            open_price = rates[0]['open']
            current_price = tick.last if tick.last > 0 else (tick.bid if tick.bid > 0 else tick.ask)
            variation = ((current_price - open_price) / open_price) * 100 if open_price > 0 else 0
            print(f"{symbol:<10} | {open_price:<10.2f} | {current_price:<10.2f} | {variation:<12.2f}%")
        else:
            print(f"{symbol:<10} | DADOS INSUFICIENTES")

    mt5.shutdown()

if __name__ == "__main__":
    test_bluechips()
