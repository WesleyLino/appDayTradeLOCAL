"""
Backtest Comparativo: Threshold 0.85 (atual) vs 0.82 (proposto)
Datas: 20/02, 23/02, 24/02, 25/02, 26/02, 27/02/2026
Capital: R$ 3.000
Símbolo: WIN$
"""

import asyncio
import logging
import sys
import os
import MetaTrader5 as mt5
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro

# Silencia logs internos para o relatório ficar legível
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")

SYMBOL = "WIN$"
CAPITAL = 3000.0
DATAS = [
    (2026, 2, 20),
    (2026, 2, 23),
    (2026, 2, 24),
    (2026, 2, 25),
    (2026, 2, 26),
    (2026, 2, 27),
]
THRESHOLDS = {
    "85% (ATUAL)": 0.85,
    "82% (PROPOSTO)": 0.82,
}


async def rodar_dia(ano, mes, dia, threshold):
    """Executa o BacktestPro para um único dia com o threshold dado."""
    from datetime import datetime

    tester = BacktestPro(
        symbol=SYMBOL,
        n_candles=1500,
        timeframe="M1",
        initial_balance=CAPITAL,
        base_lot=1,
        confidence_threshold=threshold,
    )

    utc_from = datetime(ano, mes, dia, 8, 0)
    utc_to = datetime(ano, mes, dia, 18, 30)
    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, utc_from, utc_to)

    if rates is None or len(rates) == 0:
        return None

    data = pd.DataFrame(rates)
    data["time"] = pd.to_datetime(data["time"], unit="s")
    data.set_index("time", inplace=True)
    tester.data = data

    await tester.run()
    return tester


async def main():
    if not mt5.initialize():
        print("ERRO: Falha ao inicializar MT5. Verifique se o terminal está aberto.")
        sys.exit(1)

    print()
    print("=" * 72)
    print("  BACKTEST COMPARATIVO — THRESHOLD 85% vs 82%")
    print(
        f"  Símbolo: {SYMBOL} | Capital: R$ {CAPITAL:.2f} | Período: 20/02–27/02/2026"
    )
    print("=" * 72)

    resumo = {}  # {label: {dias, trades, wins, pnl_total}}
    detalhe = {}  # {label: [linhas de detalhe]}

    for label, thresh in THRESHOLDS.items():
        resumo[label] = {"dias": 0, "trades": 0, "wins": 0, "pnl": 0.0, "pnl_dias": []}
        detalhe[label] = []

        for ano, mes, dia in DATAS:
            tester = await rodar_dia(ano, mes, dia, thresh)
            data_str = f"{dia:02d}/{mes:02d}/{ano}"

            if tester is None:
                detalhe[label].append(f"  {data_str}  | SEM DADOS MT5")
                continue

            trades = tester.trades
            pnl = tester.balance - CAPITAL
            wins = len([t for t in trades if t.get("pnl_fin", 0) > 0])
            wr = (wins / len(trades) * 100) if trades else 0

            resumo[label]["dias"] += 1
            resumo[label]["trades"] += len(trades)
            resumo[label]["wins"] += wins
            resumo[label]["pnl"] += pnl
            resumo[label]["pnl_dias"].append(pnl)

            sinal = "+" if pnl >= 0 else ""
            detalhe[label].append(
                f"  {data_str}  | {len(trades):>3} trades | "
                f"{wr:>5.1f}% WR | PnL: R$ {sinal}{pnl:>7.2f}"
            )

    # ── IMPRESSÃO DETALHADA POR CONFIGURAÇÃO ──────────────────────
    for label in THRESHOLDS:
        r = resumo[label]
        print()
        print(
            f"  ▸ Configuração: {label}  (confidence_threshold={THRESHOLDS[label]:.2f})"
        )
        print("  " + "-" * 62)
        for linha in detalhe[label]:
            print(linha)
        print("  " + "-" * 62)
        total_wr = (r["wins"] / r["trades"] * 100) if r["trades"] else 0
        print(
            f"  TOTAL  | {r['trades']:>3} trades | {total_wr:>5.1f}% WR | PnL: R$ {r['pnl']:>+8.2f}"
        )

    # ── COMPARATIVO FINAL ─────────────────────────────────────────
    print()
    print("=" * 72)
    print("  COMPARATIVO FINAL")
    print("=" * 72)

    labels = list(THRESHOLDS.keys())
    r1, r2 = resumo[labels[0]], resumo[labels[1]]

    delta_trades = r2["trades"] - r1["trades"]
    delta_pnl = r2["pnl"] - r1["pnl"]
    delta_wr = (r2["wins"] / r2["trades"] * 100 if r2["trades"] else 0) - (
        r1["wins"] / r1["trades"] * 100 if r1["trades"] else 0
    )

    sinal_p = "+" if delta_pnl >= 0 else ""
    sinal_t = "+" if delta_trades >= 0 else ""
    sinal_w = "+" if delta_wr >= 0 else ""

    print(
        f"  {labels[0]:30s}  Trades: {r1['trades']:>3} | WR: {(r1['wins'] / r1['trades'] * 100 if r1['trades'] else 0):>5.1f}% | PnL: R$ {r1['pnl']:>+8.2f}"
    )
    print(
        f"  {labels[1]:30s}  Trades: {r2['trades']:>3} | WR: {(r2['wins'] / r2['trades'] * 100 if r2['trades'] else 0):>5.1f}% | PnL: R$ {r2['pnl']:>+8.2f}"
    )
    print()
    print(f"  Δ trades : {sinal_t}{delta_trades}")
    print(f"  Δ PnL    : R$ {sinal_p}{delta_pnl:.2f}")
    print(f"  Δ WR     : {sinal_w}{delta_wr:.1f}%")
    print()

    if delta_pnl > 0 and delta_wr >= -3:
        print(
            "  ✅ CONCLUSÃO: Threshold 82% SUPERIOR — mais trades C/ PnL positivo e WR aceitável"
        )
        print("     ⚠️  Autorização necessária para alterar threshold em produção.")
    elif delta_pnl > 0 and delta_wr < -3:
        print("  ⚖️  CONCLUSÃO: Threshold 82% gera MAIS PnL mas reduz assertividade.")
        print("     Trade-off: quantidade vs qualidade. Decidir com o Mestre.")
    elif delta_pnl <= 0:
        print(
            "  🔒 CONCLUSÃO: Threshold 85% (ATUAL) é SUPERIOR — manter configuração atual."
        )
    print("=" * 72)

    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
