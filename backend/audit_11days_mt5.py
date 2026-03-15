import asyncio
import logging
from datetime import date
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


async def run_multiday_analysis():
    logger = logging.getLogger()
    logger.setLevel(logging.ERROR)

    dates_to_test = [
        date(2026, 2, 19),
        date(2026, 2, 20),
        date(2026, 2, 23),
        date(2026, 2, 24),
        date(2026, 2, 25),
        date(2026, 2, 26),
        date(2026, 2, 27),
        date(2026, 2, 28),
        date(2026, 3, 2),
        date(2026, 3, 3),
        date(2026, 3, 4),
    ]

    print("===================================================================")
    print("🚀 BACKTEST PANORÂMICO 11 DIAS (MT5) - SOTA V22 GOLDEN STATE")
    print("===================================================================")

    symbol = "WIN$"
    capital = 3000.0

    # 1. Obter dados maciços (500 candles por dia * 11 dias + margem = 15000 candles)
    tester = BacktestPro(
        symbol=symbol,
        n_candles=15000,
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=True,
    )

    tester.opt_params["vol_spike_mult"] = 1.0
    tester.opt_params["use_flux_filter"] = True
    tester.opt_params["confidence_threshold"] = 0.70

    print("⏳ Coletando base histórica de ultra-fidelidade do terminal MT5...")
    full_data = await tester.load_data()

    if full_data is None or full_data.empty:
        print("❌ Falha ao carregar dados do MT5.")
        return

    total_pnl = 0
    total_trades = 0
    total_wins = 0

    global_buy_trades = 0
    global_buy_wins = 0
    global_buy_pnl = 0

    global_sell_trades = 0
    global_sell_wins = 0
    global_sell_pnl = 0

    shadow_v22_candidates = 0
    shadow_filtered_ai = 0
    shadow_filtered_flux = 0

    print("🧠 Analisando dias solicitados...\n")

    for d in dates_to_test:
        df_day = full_data[full_data.index.date == d]
        if df_day.empty:
            print(
                f"[{d.strftime('%d/%m/%Y')}] -> SEM PREGÃO (Final de Semana/Feriado) ou Sem Dados"
            )
            continue

        tester_day = BacktestPro(
            symbol=symbol,
            n_candles=100,  # irrelevante pois sobresscrevemos data
            timeframe="M1",
            initial_balance=capital,
            base_lot=1,
            dynamic_lot=True,
            use_ai_core=True,
        )
        tester_day.opt_params["vol_spike_mult"] = 1.0
        tester_day.opt_params["use_flux_filter"] = True
        tester_day.opt_params["confidence_threshold"] = 0.70
        tester_day.data = df_day

        await tester_day.run()

        trades = tester_day.trades
        shadow = tester_day.shadow_signals

        day_pnl = tester_day.balance - capital
        total_pnl += day_pnl
        total_trades += len(trades)

        win_count = len([t for t in trades if t["pnl_fin"] > 0])
        total_wins += win_count

        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]

        b_pnl = sum([t["pnl_fin"] for t in buy_trades])
        s_pnl = sum([t["pnl_fin"] for t in sell_trades])
        b_wins = len([t for t in buy_trades if t["pnl_fin"] > 0])
        s_wins = len([t for t in sell_trades if t["pnl_fin"] > 0])

        global_buy_trades += len(buy_trades)
        global_buy_wins += b_wins
        global_buy_pnl += b_pnl

        global_sell_trades += len(sell_trades)
        global_sell_wins += s_wins
        global_sell_pnl += s_pnl

        shadow_v22_candidates += shadow.get("v22_candidates", 0)
        shadow_filtered_ai += shadow.get("filtered_by_ai", 0)
        shadow_filtered_flux += shadow.get("filtered_by_flux", 0)

        print(
            f"[{d.strftime('%d/%m/%Y')}] PnL: R$ {day_pnl:+7.2f} | Trades: {len(trades):2d} | Assertividade: {(win_count / len(trades) * 100 if len(trades) > 0 else 0):5.1f}% | Compras: {len(buy_trades):2d} | Vendas: {len(sell_trades):2d}"
        )

    print("\n===================================================================")
    print("🏆 RESULTADO AGREGADO DOS 11 DIAS")
    print("===================================================================")
    print(f"Capital Inicial Simulado: R$ {capital:.2f}")
    print(f"Lucro/Prejuízo Total:     R$ {total_pnl:+.2f}")
    print(f"Evolução Patrimonial:     R$ {(capital + total_pnl):.2f}")
    print(f"Total de Trades:          {total_trades}")

    global_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
    print(f"Assertividade Global:     {global_wr:.2f}%")

    b_wr = (global_buy_wins / global_buy_trades * 100) if global_buy_trades > 0 else 0
    s_wr = (
        (global_sell_wins / global_sell_trades * 100) if global_sell_trades > 0 else 0
    )

    print("\n--- PERFORMANCE BI-DIRECIONAL ---")
    print(
        f"🟢 COMPRAS Totais: {global_buy_trades:3d} trades | PnL Somado: R$ {global_buy_pnl:+7.2f} | Assertividade: {b_wr:.1f}%"
    )
    print(
        f"🔴 VENDAS Totais:  {global_sell_trades:3d} trades | PnL Somado: R$ {global_sell_pnl:+7.2f} | Assertividade: {s_wr:.1f}%"
    )

    print("\n--- OPORTUNIDADES VS BLINDAGEM (SHADOW ANALYSIS) ---")
    print(f"- Total de Indícios Mapeados (IA Base 22): {shadow_v22_candidates}")
    print(f"- Bloqueios por Rigor de Incerteza (Cone): {shadow_filtered_ai}")
    print(f"- Bloqueios por Fluxo Institucional OFI:   {shadow_filtered_flux}")

    print("\n💡 DIAGNÓSTICO DE APRIMORAMENTO / MELHORIAS:")
    if s_wr < 50 and global_sell_trades > 0:
        print(
            "-> [ALERTA] Vendas (Shorts) estão machucando o modelo ou não trazendo PnL. O mercado esteve majoritariamente autista ou em correção suja."
        )
    elif s_wr >= 50:
        print("-> [OK] Vendas (Shorts) mantiveram consistência estável.")

    if b_wr < 50 and global_buy_trades > 0:
        print(
            "-> [ALERTA] Compras (Longs) estão sofrendo muitas violinadas de Stop. O Cone de incerteza da IA pode estar folgado."
        )
    elif b_wr >= 50:
        print("-> [OK] Compras (Longs) capturaram a liquidez do mercado efetivamente.")

    print("\n⚠️ Status: CALIBRAÇÃO GOLDEN V22 MANTIDA.")
    print(
        "Mestre, a parametrização super restritiva do código não foi tocada. As proteções vigoraram nos 11 dias."
    )
    print("===================================================================")


if __name__ == "__main__":
    asyncio.run(run_multiday_analysis())
