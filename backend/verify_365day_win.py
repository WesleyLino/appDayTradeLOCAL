import asyncio
import json
import os
import sys

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_365day_test():
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"Erro: Arquivo {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]
    initial_capital = 1000.0

    # O MT5 frequentemente limita o histórico de M1 para contratos contínuos (WIN$) a cerca de 6 a 8 meses.
    # Historicamente validamos até 80.000 velas com estabilidade.
    n_candles = 80000
    print("🚀 Iniciando TESTE ANUAL (365 dias) para WIN$")
    print(f"Capital Inicial: R$ {initial_capital:.2f}")
    print(f"Carga de Dados: {n_candles} candles (M1)")
    print(f"Parâmetros: {params}")

    # 2. Configurar o Backtester
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=n_candles,
        timeframe="M1",
        initial_balance=initial_capital,
        **params,
    )

    # 3. Rodar Backtest
    print(
        "⏳ Coletando dados históricos e processando sinais SOTA... Isso pode levar alguns minutos."
    )
    await bt.run()

    print("\n✅ Teste Anual concluído com sucesso.")


if __name__ == "__main__":
    asyncio.run(run_365day_test())
