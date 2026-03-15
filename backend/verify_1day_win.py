import asyncio
import json
import os
import sys

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_1day_test():
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"Erro: Arquivo {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]
    initial_capital = 1000.0
    print(f"🚀 Iniciando teste de 1 dia para WIN$ | Capital: R$ {initial_capital:.2f}")
    print(f"Parâmetros: {params}")

    # 2. Configurar o Backtester
    # 1 dia de M1 ~ 9 horas * 60 min = 540 candles
    # Vamos usar 600 para garantir a cobertura.
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=600,
        timeframe="M1",
        initial_balance=initial_capital,
        **params,
    )

    # 3. Rodar Backtest
    print("⏳ Coletando dados reais via MT5 Bridge...")
    df = await bt.load_data()
    if df is not None:
        start_date = df.index[0].strftime("%d/%m/%Y %H:%M")
        end_date = df.index[-1].strftime("%d/%m/%Y %H:%M")
        print(f"📅 Período Detectado: {start_date} até {end_date}")

        print("⏳ Processando indicadores e executando simulação...")
        await bt.run()

    print("\n✅ Teste de 1 dia concluído.")


if __name__ == "__main__":
    asyncio.run(run_1day_test())
