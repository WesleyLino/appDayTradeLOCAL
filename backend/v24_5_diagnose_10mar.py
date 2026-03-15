import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def diagnose_10mar():
    # Logging detalhado para pegar os vetos
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    print("\n🔍 DIAGNÓSTICO PROFUNDO: 10/03/2026 (v24.5)")

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260310.csv",
        use_ai_core=True,
    )

    await bt.load_data()
    if bt.data is None:
        print("❌ Dados 10/03 não encontrados.")
        return

    # Vamos interceptar a simulação para ver os scores durante a Janela de Ouro
    print("\n--- Monitorando Janela de Ouro (10:00 - 11:30) ---")

    # Executar simulação normal mas com olhos nos logs
    summary = await bt.run()

    print(f"\nResultado Final 10/03: R$ {summary.get('net_profit', 0):.2f}")
    print(f"Shadow Signals: {summary.get('shadow_signals', {})}")


if __name__ == "__main__":
    asyncio.run(diagnose_10mar())
