import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def experiment_uncertainty():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("\n🧪 EXPERIMENTO: Relaxamento de Incerteza (Threshold 0.6) em 10/03")

    # Injeta threshold maior diretamente no AICore via kwargs se o BacktestPro permitir
    # ou modificamos o objeto após o init
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260310.csv",
        use_ai_core=True,
    )

    # Relaxa incerteza para o experimento
    bt.ai.uncertainty_threshold = 0.6

    await bt.load_data()
    summary = await bt.run()

    print(f"\nResultado com Incerteza 0.6: R$ {summary.get('net_profit', 0):.2f}")
    print(f"Shadow Signals: {summary.get('shadow_signals', {})}")


if __name__ == "__main__":
    asyncio.run(experiment_uncertainty())
