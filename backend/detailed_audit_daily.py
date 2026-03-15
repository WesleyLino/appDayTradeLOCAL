import asyncio
import json
import os
import sys
import pandas as pd

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_detailed_daily_audit():
    params_path = "backend/v22_locked_params.json"
    if not os.path.exists(params_path):
        print("❌ Erro: Arquivo de parâmetros não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["strategy_params"]
    initial_capital = 3000.0
    n_candles = 15000  # Aumentado para garantir cobertura total de 19/02 a 09/03

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=n_candles,
        timeframe="M1",
        initial_balance=initial_capital,
        **params,
    )
    bt.opt_params["force_lots"] = 3

    print("\n" + "🚀" * 15)
    print("AUDITORIA DIÁRIA DETALHADA SOTA")
    print("Período: 19/02 a 09/03 | Capital: R$ 3.000")
    print("🚀" * 15 + "\n")

    report = await bt.run()
    trades = report["trades"]

    if not trades:
        print("❌ Nenhum trade realizado no período.")
        return

    df = pd.DataFrame(trades)
    df["date"] = pd.to_datetime(df["exit_time"]).dt.date

    daily_stats = []

    for date, group in df.groupby("date"):
        buys = group[group["side"] == "buy"]
        sells = group[group["side"] == "sell"]

        wins = len(group[group["pnl_fin"] > 0])
        wr = (wins / len(group)) * 100
        pnl = group["pnl_fin"].sum()

        daily_stats.append(
            {
                "Data": date,
                "Total Trades": len(group),
                "Compras": len(buys),
                "Vendas": len(sells),
                "Win Rate": f"{wr:.1f}%",
                "PnL": f"R$ {pnl:.2f}",
            }
        )

    # Imprimir tabela formatada
    print(pd.DataFrame(daily_stats).to_string(index=False))

    print("\n" + "=" * 50)
    print("🔍 ANÁLISE DE OPORTUNIDADES PERDIDAS (GERAL)")
    shadow = report.get("shadow_signals", {})
    print(f"Gatilhos V22 Identificados: {shadow.get('v22_candidates', 0)}")
    print(f"Vetos pela IA (SOTA): {shadow.get('filtered_by_ai', 0)}")

    veto_reasons = shadow.get("veto_reasons", {})
    if veto_reasons:
        print("\nRAZÕES DE VETO MAIS FREQUENTES:")
        sorted_reasons = sorted(veto_reasons.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]
        for reason, count in sorted_reasons:
            print(f" - {reason}: {count}")

    print("\n" + "=" * 50)
    print("🏆 RESUMO FINAL")
    print(f"Lucro Total: R$ {report['total_pnl']:.2f}")
    print(f"Drawdown Máximo: {report['max_drawdown']:.2f}%")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_detailed_daily_audit())
