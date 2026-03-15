import asyncio
import logging
import pandas as pd
from backend.backtest_pro import BacktestPro

logging.basicConfig(level=logging.WARNING)


async def debug_10mar():
    df = pd.read_csv("backend/historico_WIN_10mar_warmup.csv")
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)

    bt = BacktestPro(symbol="WIN$", capital=3000.0)
    bt.data = df

    print("Iniciando varredura de sinais em 10/03...")
    await bt.run()

    # O BacktestPro já logou quando houveram vetos se configurado,
    # mas vamos ver os shadow_signals
    print("\nRESUMO DE VETOS:")
    print(bt.shadow_signals.get("veto_reasons", {}))


if __name__ == "__main__":
    asyncio.run(debug_10mar())
