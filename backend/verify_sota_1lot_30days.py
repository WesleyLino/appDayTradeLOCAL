import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_30day_conservative_test():
    print("📈 Iniciando Teste Conservador de 30 Dias: 1 Contrato / Cap R$ 1000")
    print("🚀 Foco: Estabilidade de longo prazo com Breakeven e Trailing Stop.")

    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    # 12,000 candles M1 ~= 30 dias operacionais (6h úteis por dia: 10h-16h)
    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=12000,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        dynamic_lot=False,
        **params,
    )

    await backtester.run()

    print("\n=== LISTAGEM DE TRADES (30 DIAS) ===")
    for t in backtester.trades:
        print(
            f"Data: {t['exit_time'].date()} | Side: {t['side']} | Pts: {t['pnl_points']:.1f} | R$: {t['pnl_fin']:.2f} | Motivo: {t['reason']}"
        )

    print("\n✅ Teste de 30 Dias Concluído.")


if __name__ == "__main__":
    asyncio.run(run_30day_conservative_test())
