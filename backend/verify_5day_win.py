import asyncio
import json
import os
import sys

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_5day_test():
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"Erro: Arquivo {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]
    print(f"🚀 Iniciando teste de 5 dias para WIN$ com parâmetros: {params}")

    # 2. Configurar o Backtester
    # 5 dias de M1 ~ 5 * 9 horas * 60 min = 2700 candles
    # Vamos usar 3000 para garantir a cobertura completa.
    bt = BacktestPro(symbol="WIN$", n_candles=3000, timeframe="M1", **params)

    # 3. Rodar Backtest
    print("⏳ Coletando dados e processando indicadores SOTA...")
    await bt.run()
    print("\n✅ Teste de 5 dias concluído com sucesso.")


if __name__ == "__main__":
    asyncio.run(run_5day_test())
