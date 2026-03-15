import asyncio
import logging
from datetime import datetime
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro
import MetaTrader5 as mt5
import json

# Configuração de Logs
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


async def audit_day_params(bridge, date, symbol, params, data_cache):
    date_from = date.replace(hour=8, minute=0, second=0)
    date_to = date.replace(hour=18, minute=30, second=0)

    cache_key = date.strftime("%Y-%m-%d")
    if cache_key not in data_cache:
        data = bridge.get_market_data_range(
            symbol, mt5.TIMEFRAME_M1, date_from, date_to
        )
        data_cache[cache_key] = data
    else:
        data = data_cache[cache_key]

    if data is None or data.empty:
        return None

    # Configurar Backtest com Parâmetros Customizados
    back = BacktestPro(symbol=symbol, initial_balance=3000.0, use_ai_core=True)

    # Injetar parâmetros no AI-Core
    back.ai.uncertainty_threshold_base = params["threshold"]
    back.ai.lot_multiplier_partial = params["multiplier"]

    back.data = data.copy()
    results = await back.run()
    return results


async def run_deep_search():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Falha ao conectar ao Terminal MetaTrader 5.")
        return

    symbol = "WIN$N"
    # Datas de teste (Amostra robusta de diferentes comportamentos)
    dates = [
        datetime(2026, 2, 19),
        datetime(2026, 2, 23),
        datetime(2026, 2, 24),
        datetime(2026, 2, 25),
    ]

    # Grid de Parâmetros
    thresholds = [0.15, 0.20, 0.25, 0.30, 0.35]
    multipliers = [0.25, 0.50, 0.75]

    results_grid = []
    data_cache = {}

    print("\n" + "=" * 60)
    print("🔍 BUSCA PROFUNDA (GRID SEARCH): CAPITAL R$ 3.000")
    print(
        f"📊 Testando {len(thresholds) * len(multipliers)} combinações em {len(dates)} dias."
    )
    print("=" * 60)

    for t in thresholds:
        for m in multipliers:
            print(f"⚙️ Testando: Threshold={t:.2f} | Multiplier={m:.2f}...", end="\r")

            total_pnl = 0
            total_trades = 0
            max_dd = 0
            days_count = 0

            for d in dates:
                res = await audit_day_params(
                    bridge, d, symbol, {"threshold": t, "multiplier": m}, data_cache
                )
                if res:
                    total_pnl += res["total_pnl"]
                    total_trades += len(res["trades"])
                    max_dd = max(max_dd, res["max_drawdown"])
                    days_count += 1

            avg_pnl = total_pnl / days_count if days_count > 0 else 0

            results_grid.append(
                {
                    "threshold": t,
                    "multiplier": m,
                    "total_pnl": total_pnl,
                    "avg_pnl_day": avg_pnl,
                    "total_trades": total_trades,
                    "max_dd": max_dd,
                }
            )

    # Ordenar por PNL Total
    sorted_results = sorted(results_grid, key=lambda x: x["total_pnl"], reverse=True)

    print("\n\n" + "=" * 80)
    print(
        f"{'RANK':<5} | {'THR':<5} | {'MULT':<5} | {'PNL TOTAL':<12} | {'AVG/DAY':<10} | {'TRADES':<6} | {'MAX DD':<8}"
    )
    print("-" * 80)

    for i, r in enumerate(sorted_results[:10]):
        rank_icon = (
            "🏆" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f" {i + 1} "
        )
        print(
            f"{rank_icon:<5} | {r['threshold']:<5.2f} | {r['multiplier']:<5.2f} | R$ {r['total_pnl']:<9.2f} | R$ {r['avg_pnl_day']:<7.2f} | {r['total_trades']:<6} | {r['max_dd']:>6.2f}%"
        )

    print("=" * 80)

    # Salvar o melhor resultado
    best = sorted_results[0]
    with open("backend/high_gain_parameters.json", "w") as f:
        json.dump(best, f, indent=4)
    print("\n✅ Melhores parâmetros salvos em 'backend/high_gain_parameters.json'")

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(run_deep_search())
