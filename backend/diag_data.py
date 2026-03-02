import asyncio
from datetime import datetime
import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.mt5_bridge import MT5Bridge
import MetaTrader5 as mt5

async def check_data():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("Erro conexão")
        return
    
    symbol = "WIN$"
    n = 15000
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, n)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print(f"Total velas: {len(df)}")
    print(f"Primeira: {df['time'].min()}")
    print(f"Ultima: {df['time'].max()}")
    
    target_dates = ["19/02/2026", "27/02/2026"]
    for d_str in target_dates:
        d = datetime.strptime(d_str, "%d/%m/%Y").date()
        count = len(df[df['time'].dt.date == d])
        print(f"Velas em {d_str}: {count}")

if __name__ == "__main__":
    asyncio.run(check_data())
