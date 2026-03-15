import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def experiment_27feb_relaxed():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("\n🧪 EXPERIMENTO: Threshold Relaxado (52.0) em 27/02")

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260227.csv",
        use_ai_core=True,
    )

    # Simula o threshold da v24.4.1
    bt.ai.confidence_buy_threshold = 52.0
    bt.ai.confidence_sell_threshold = 48.0

    await bt.load_data()
    summary = await bt.run()

    print(f"\nResultado com Threshold 52.0: R$ {summary.get('net_profit', 0):.2f}")
    print(f"Número de Trades: {summary.get('total_trades', 0)}")


if __name__ == "__main__":
    asyncio.run(experiment_27feb_relaxed())
