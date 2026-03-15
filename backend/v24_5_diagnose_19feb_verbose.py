import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def diagnose_19feb_verbose():
    # Logging no nível WARNING para pegar os [DEBUG-AI] Veto que agora são WARNING
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    print("\n🔍 DIAGNÓSTICO VERBOSO: 19/02/2026 (v24.5)")

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260219.csv",
        use_ai_core=True,
    )

    await bt.load_data()
    # Executar simulação
    await bt.run()


if __name__ == "__main__":
    asyncio.run(diagnose_19feb_verbose())
