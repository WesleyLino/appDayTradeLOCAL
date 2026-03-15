import asyncio
import logging
from backend.backtest_pro import BacktestPro

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def run_comparative_audit():
    logging.info("🕵️ INICIANDO AUDITORIA COMPARATIVA PRO-MAX (SOTA v4 vs v3.1)")

    # Dias de teste: 19/02 (Tendência agressiva), 23/02 (Alta Performance), 24/02 (Alta Volatilidade)
    # n=1000 candles M1 (~2 dias de pregão por teste)
    test_days = [
        {"name": "19/02/2026 (Tendência Alta)", "n": 1000},
        {"name": "23/02/2026 (Sniper)", "n": 1000},
        {"name": "24/02/2026 (Volatilidade)", "n": 1000},
    ]

    results_v4 = []

    for day in test_days:
        logging.info(f"--- FASE: Testando v4 em {day['name']} ---")
        bt_v4 = BacktestPro(
            symbol="WIN$",
            n_candles=day["n"],
            use_ai_core=True,  # SOTA v4 (H1 + Lot Prob)
            initial_balance=3000.0,
            dynamic_lot=True,
        )
        report_v4 = await bt_v4.run()
        results_v4.append({"day": day["name"], "report": report_v4})

    # Gerar Relatório Comparativo Consolidado
    logging.info("📊 CONSOLIDANDO DADOS DE AUDITORIA...")

    print("\n" + "=" * 80)
    print(f"{'DIA':<30} | {'V4 PNL':<12} | {'WR %':<8} | {'TRADES'}")
    print("-" * 80)

    for res in results_v4:
        r = res["report"]
        pnl = f"R$ {r['total_pnl']:>8.2f}"
        wr = f"{r['win_rate']:>6.1f}%"
        trades = len(r["trades"])
        print(f"{res['day']:<30} | {pnl:<12} | {wr:<8} | {trades}")

        # Análise de Oportunidades Perdidas/Filtradas
        shadow = r.get("shadow_signals", {})
        print(
            f"   ↳ [SOTA v4 AI Audit]: Oportunidades Filtradas (Shadow): {shadow.get('filtered_by_ai', 0)}"
        )
        print(
            f"   ↳ [SOTA v4 H1 Filter]: Oportunidades Vetadas pela Tendência: {shadow.get('total_missed', 0) - shadow.get('filtered_by_ai', 0)}"
        )

    print("=" * 80)
    print("MÉTRICAS V3.1 (Baseline Anterior para R$ 3.000):")
    print("19/02: - R$ 114.05 | 23/02: + R$ 184.20 | 24/02: + R$ 62.10")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_comparative_audit())
