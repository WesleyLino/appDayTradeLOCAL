import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_analysis():
    # Carregar parâmetros
    params_path = "best_params_WIN.json"
    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]

    # Configurar Backtester Pro
    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        **params,
    )

    await backtester.run()

    print("\n--- DETALHAMENTO DE TRADES ---")
    for i, trade in enumerate(backtester.trades):
        print(f"Trade {i + 1}:")
        print(f"  Entrada: {trade['entry_time']} @ {trade['entry']}")
        print(f"  Saída:   {trade['exit_time']} @ {trade['exit']} ({trade['reason']})")
        print(f"  Pontos:  {trade['pnl_points']:.1f}")
        print(f"  Lucro:   R$ {trade['pnl_fin']:.2f}")
        print("-" * 30)


if __name__ == "__main__":
    asyncio.run(run_analysis())
