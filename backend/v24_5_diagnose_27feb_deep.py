import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def diagnose_27feb_deep():
    # Logging DEBUG para pegar TUDO
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    print("\n🔍 DIAGNÓSTICO PROFUNDO: 27/02/2026 (v24.5)")

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260227.csv",
        use_ai_core=True,
    )

    await bt.load_data()
    # Executar simulação
    await bt.run()


if __name__ == "__main__":
    asyncio.run(diagnose_27feb_deep())
