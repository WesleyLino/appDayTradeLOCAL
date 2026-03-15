import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_365day_long_test():
    print("📈 Iniciando Audit MT5 de 365 Dias: 1 Contrato / Cap R$ 1000")
    print("🚀 Foco: Sobrevivência e Consistência de Longo Prazo (Full Year).")

    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    # Parâmetros solicitados pelo usuário
    params["start_time"] = "10:00"
    params["end_time"] = "15:00"
    params["aggressive_mode"] = True

    # ~250 dias úteis * 300 candles/dia (10h-15h) = 75.000 + margem para indicadores
    n_candles = 85000
    print(f"📥 Solicitando {n_candles} candles M1 do MT5...")

    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=n_candles,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        dynamic_lot=False,  # 1 CONTRATO FIXO
        **params,
    )

    await backtester.run()

    print("\n=== RESUMO ANUAL (1 LOTE) ===")
    print(f"Saldo Final: R$ {backtester.balance:.2f}")
    if len(backtester.trades) > 0:
        profit_total = backtester.balance - 1000.0
        print(f"Lucro Líquido Acumulado: R$ {profit_total:.2f}")
        print(f"Drawdown Máximo: {backtester.max_drawdown * 100:.2f}%")
        print(f"Total de Trades: {len(backtester.trades)}")

        win_trades = [t for t in backtester.trades if t["pnl_fin"] > 0]
        wr = (len(win_trades) / len(backtester.trades)) * 100
        print(f"Win Rate: {wr:.1f}%")

        pf = 0.0
        gross_profit = sum(t["pnl_fin"] for t in backtester.trades if t["pnl_fin"] > 0)
        gross_loss = abs(
            sum(t["pnl_fin"] for t in backtester.trades if t["pnl_fin"] < 0)
        )
        if gross_loss > 0:
            pf = gross_profit / gross_loss
            print(f"Profit Factor: {pf:.2f}")
    else:
        print("Nenhum trade realizado no período.")

    print("\n=== TOP 5 MAIORES GANHOS ===")
    sorted_trades = sorted(backtester.trades, key=lambda x: x["pnl_fin"], reverse=True)
    for t in sorted_trades[:5]:
        print(
            f"Data: {t['exit_time'].date()} | Pts: {t['pnl_points']:.1f} | R$: {t['pnl_fin']:.2f}"
        )

    print("\n✅ Auditoria de 365 Dias Concluída.")


if __name__ == "__main__":
    asyncio.run(run_365day_long_test())
