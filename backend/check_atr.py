import asyncio
from datetime import datetime
import sys
import os
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.mt5_bridge import MT5Bridge
import MetaTrader5 as mt5

async def check_atr():
    bridge = MT5Bridge()
    if not bridge.connect():
        return
    
    symbol = "WIN$"
    n = 15000
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, n)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Cálculo de ATR M1 (Simples)
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                     abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    target_dates = ["19/02/2026", "23/02/2026", "27/02/2026"]
    for d_str in target_dates:
        d = datetime.strptime(d_str, "%d/%m/%Y").date()
        day_df = df[df['time'].dt.date == d]
        if not day_df.empty:
            avg_atr = day_df['atr'].mean()
            min_atr = day_df['atr'].min()
            max_atr = day_df['atr'].max()
            print(f"Dia {d_str} -> ATR Médio: {avg_atr:.1f} | Min: {min_atr:.1f} | Max: {max_atr:.1f}")

if __name__ == "__main__":
    asyncio.run(check_atr())
