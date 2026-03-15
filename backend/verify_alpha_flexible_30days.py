import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_30day_alpha_test():
    print(
        "📈 Iniciando Teste ALPHA de 30 Dias: Janela 10h-15h + Alpha Scaling (Lote Dinâmico)"
    )
    print("🚀 Foco: Maximização de lucro com capital R$ 1000.")

    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    # Sobrescrita para Modo Alpha
    params["end_time"] = "15:00"
    params["aggressive_mode"] = True

    # 15,000 candles para cobrir a janela expandida com sobra
    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=15000,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        dynamic_lot=True,  # ALPHA SCALING ATIVADO
        **params,
    )

    await backtester.run()

    print("\n=== RESUMO ALPHA (30 DIAS) ===")
    print(f"Saldo Final: R$ {backtester.balance:.2f}")
    print(f"Drawdown Máximo: {backtester.max_drawdown * 100:.2f}%")
    print(f"Total de Trades: {len(backtester.trades)}")

    print("\n=== LISTAGEM DE TRADES ALPHA (Últimos 10) ===")
    for t in backtester.trades[-10:]:
        print(
            f"Data: {t['exit_time'].date()} | Side: {t['side']} | Lote: {t['lots']} | Pts: {t['pnl_points']:.1f} | R$: {t['pnl_fin']:.2f} | Motivo: {t['reason']}"
        )

    print("\n✅ Teste ALPHA de 30 Dias Concluído.")


if __name__ == "__main__":
    asyncio.run(run_30day_alpha_test())
