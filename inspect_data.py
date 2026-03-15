import asyncio
import MetaTrader5 as mt5
from datetime import datetime
import sys
import os

# Caminho para backend
sys.path.append(os.path.abspath("backend"))
from mt5_bridge import MT5Bridge
from backtest_pro import BacktestPro


async def inspect():
    bridge = MT5Bridge()
    bridge.connect()

    dia = datetime(2026, 2, 25)
    df = bridge.get_market_data_range(
        "WIN$",
        mt5.TIMEFRAME_M1,
        dia.replace(hour=8, minute=0),
        dia.replace(hour=17, minute=45),
    )

    bt = BacktestPro(symbol="WIN$", initial_balance=3000)
    bt.data = df
    await bt.run()

    # Salva os indicadores para inspeção
    bt.data.to_csv("inspect_backtest_data.csv")
    print(f"Arquivo de inspeção gerado: {len(bt.data)} linhas.")
    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(inspect())
