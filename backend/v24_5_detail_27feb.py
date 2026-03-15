import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def detail_vetos_27feb():
    # Logging INFO para pegar as mensagens formatadas no ai_core
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("\n🔍 DETALHAMENTO DE VETOS: 27/02/2026 (v24.5)")

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260227.csv",
        use_ai_core=True,
    )

    await bt.load_data()
    # Executar simulação e capturar logs de veto
    await bt.run()


if __name__ == "__main__":
    asyncio.run(detail_vetos_27feb())
