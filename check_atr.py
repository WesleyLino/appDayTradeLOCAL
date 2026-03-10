import asyncio
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta

async def check_triggers(symbol, date_str):
    start_dt = datetime.strptime(date_str, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=1)
    
    if not mt5.initialize():
        return
        
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_dt, end_dt)
    if rates is None:
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Simple ATR and ADX calculation for check
    close = df['close']
    high = df['high']
    low = df['low']
    
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    
    # ADX Simplified
    plus_dm = high.diff().clip(lower=0)
    minus_dm = low.diff().iloc[::-1].diff().iloc[::-1].clip(lower=0) # Simple DM
    # ... actually I'll just look at the max ATR
    
    print(f"--- {date_str} ---")
    print(f"Max ATR: {atr.max():.2f}")
    print(f"Avg ATR: {atr.mean():.2f}")
    
    mt5.shutdown()

asyncio.run(check_triggers("WIN$", "2026-03-09"))
