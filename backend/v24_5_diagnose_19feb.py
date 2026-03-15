import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def diagnose_19feb():
    # Logging detalhado para pegar os vetos no AICore
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    print("\nDIAGNOSTICO PROFUNDO: 19/02/2026 (v24.5)")

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260219.csv",
        use_ai_core=True,
    )

    await bt.load_data()
    # Executar simulação
    summary = await bt.run()

    print(f"\nResultado Final 19/02: R$ {summary.get('net_profit', 0):.2f}")
    print("Shadow Signals (Oportunidades Vetadas):")
    for k, v in summary.get("shadow_signals", {}).items():
        print(f" - {k}: {v}")


if __name__ == "__main__":
    asyncio.run(diagnose_19feb())
