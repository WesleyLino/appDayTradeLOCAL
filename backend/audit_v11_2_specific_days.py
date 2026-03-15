import asyncio
import json
import os
import sys
import logging
import pandas as pd
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


async def run_ultra_audit():
    logging.basicConfig(level=logging.ERROR)

    # 1. Configuração
    params_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "best_params_WIN.json")
    )
    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]
    params["use_ai_core"] = True
    params["dynamic_lot"] = False
    params["use_trailing_stop"] = True
    params["use_correlation_filter"] = True  # Ativando Filtro Ultra
    params.pop("force_lots", None)

    initial_capital = 3000.0
    target_dates_str = [
        "2026-02-19",
        "2026-02-20",
        "2026-02-23",
        "2026-02-24",
        "2026-02-25",
        "2026-02-26",
        "2026-02-27",
    ]

    print("\n" + "=" * 95)
    print("🦅 AUDITORIA MAESTRO ULTRA (V11.2) - TESTE DE ESTRESSE")
    print(f"Período: 19/02 a 27/02 | Capital: R$ {initial_capital:.2f}")
    print("=" * 95 + "\n")

    bt_loader = BacktestPro(symbol="WIN$", n_candles=15000, timeframe="M1")
    full_df = await bt_loader.load_data()

    if full_df is None or full_df.empty:
        print("❌ Erro ao carregar dados.")
        return

    full_df["date"] = full_df.index.date
    results = []

    print(
        f"{'DATA':<12} | {'PNL COMPRA':<12} | {'PNL VENDA':<12} | {'TOTAL':<10} | {'TRADES'} | {'MISS'}"
    )
    print("-" * 95)

    for date_str in target_dates_str:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
        day_data = full_df[full_df["date"] == day]

        if day_data.empty:
            print(
                f"{date_str:<12} | {'SEM DADOS':^12} | {'-':^12} | {'-':^10} | {'-'} | {'-'}"
            )
            continue

        day_start_idx = full_df.index.get_loc(day_data.index[0])
        start_idx = max(0, day_start_idx - 200)  # Buffer para indicadores
        end_idx = full_df.index.get_loc(day_data.index[-1]) + 1
        data_chunk = full_df.iloc[start_idx:end_idx].copy()

        bt = BacktestPro(
            symbol="WIN$",
            n_candles=len(data_chunk),
            timeframe="M1",
            initial_balance=initial_capital,
            **params,
        )
        bt.df = data_chunk

        async def mock_load():
            return data_chunk

        bt.load_data = mock_load

        report = await bt.run()
        trades = [
            t
            for t in report.get("trades", [])
            if pd.to_datetime(t["entry_time"]).date() == day
        ]

        pnl_buy = sum(t["pnl_fin"] for t in trades if t["side"] == "buy")
        pnl_sell = sum(t["pnl_fin"] for t in trades if t["side"] == "sell")
        total = sum(t["pnl_fin"] for t in trades)

        missed = report.get("shadow_signals", {}).get("total_missed", 0)

        results.append(
            {
                "date": date_str,
                "pnl_buy": pnl_buy,
                "pnl_sell": pnl_sell,
                "total": total,
                "trades": len(trades),
                "missed": missed,
            }
        )

        print(
            f"{day.strftime('%d/%m/%Y'):<12} | R$ {pnl_buy:>9.2f} | R$ {pnl_sell:>9.2f} | R$ {total:>8.2f} | {len(trades):^6} | {missed:^4}"
        )

    print("-" * 95)
    total_net = sum(r["total"] for r in results)
    print(f"SALDO FINAL MAESTRO ULTRA: R$ {total_net:.2f}")

    with open("backend/audit_ultra_specific.json", "w") as f:
        json.dump(results, f, indent=4)


if __name__ == "__main__":
    asyncio.run(run_ultra_audit())
