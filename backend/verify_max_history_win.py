import asyncio
import json
import os
import sys
import MetaTrader5 as mt5

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_max_history_test():
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"Erro: Arquivo {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]
    initial_capital = 1000.0

    if not mt5.initialize():
        print("Falha ao inicializar MT5")
        return

    symbol = "WIN$"
    tf = mt5.TIMEFRAME_M1

    # 2. Descobrir limite de candles
    target_n = 140000
    available_n = 0

    print(f"🔍 Investigando limite de histórico para {symbol} M1...")

    # Busca binária ou decrescente simples para encontrar o limite
    test_sizes = [140000, 100000, 80000, 60000, 40000, 20000, 10000]
    for size in test_sizes:
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, size)
        if rates is not None and len(rates) > 0:
            available_n = len(rates)
            print(f"✅ Conseguimos obter {available_n} candles.")
            break

    if available_n == 0:
        print("❌ Nenhum histórico M1 disponível no terminal para este símbolo.")
        mt5.shutdown()
        return

    # 3. Configurar o Backtester com o máximo disponível
    print(
        f"🚀 Iniciando Teste de Longo Prazo | Período: ~{available_n // 540} dias úteis"
    )
    print(f"Capital Inicial: R$ {initial_capital:.2f}")

    bt = BacktestPro(
        symbol=symbol,
        n_candles=available_n,
        timeframe="M1",
        initial_balance=initial_capital,
        **params,
    )

    # 4. Rodar Backtest
    await bt.run()

    print(f"\n✅ Teste de {available_n} candles concluído.")


if __name__ == "__main__":
    asyncio.run(run_max_history_test())
