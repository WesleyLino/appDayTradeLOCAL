import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_verification():
    print("📈 Iniciando Verificação de 1 dia: Trailing Stop SOTA (Cap: R$ 1000)")

    # Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]

    # Configurar Backtester Pro
    # n=600 candles M1 cobrem a janela principal (09:00 - 18:00 + folga)
    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        **params,
    )

    print(
        f"DEBUG: Params loaded - Trigger: {params['trailing_trigger']} | Lock: {params['trailing_lock']} | Step: {params['trailing_step']}"
    )

    await backtester.run()

    print("\n✅ Verificação Concluída.")


if __name__ == "__main__":
    asyncio.run(run_verification())
