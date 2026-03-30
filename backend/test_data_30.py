import asyncio
import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro

async def main():
    bt = BacktestPro(symbol="WIN$", n_candles=20000, timeframe="M1")
    data = await bt.load_data()
    if data is not None and not data.empty:
        print("Data loaded!")
        print(f"Total rows: {len(data)}")
        print(f"Index head: {data.index[0]}")
        print(f"Index tail: {data.index[-1]}")
        print("\nLast 10 rows:")
        print(data.tail(10))
    else:
        print("No data loaded.")

if __name__ == "__main__":
    asyncio.run(main())
