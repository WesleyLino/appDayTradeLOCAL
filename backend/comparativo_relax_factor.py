"""
Backtest Comparativo — Teste do confidence_relax_factor = 0.75
Compara com o resultado base V22.5.4 (fator=0.80) nos mesmos 14 dias.
Capital: R$ 3.000,00 | WIN$ M1
NÃO altera o v22_locked_params.json — o fator é injetado em memória.
"""
import asyncio
import json
import os
import sys
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from backend.backtest_pro import BacktestPro

DIAS = [
    "19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026",
    "25/02/2026", "26/02/2026", "27/02/2026", "02/03/2026",
    "03/03/2026", "04/03/2026", "05/03/2026", "06/03/2026",
    "09/03/2026", "10/03/2026",
]

async def rodar_cenario(full_data, symbol, capital_inicial, strategy_params, relax_factor, label):
    """Executa backtest nos 14 dias com um confidence_relax_factor específico."""
    datas = [datetime.strptime(d, "%d/%m/%Y").date() for d in DIAS]

    resultados = []
    saldo = capital_inicial

    for data_alvo in datas:
        day_data = full_data[full_data.index.date == data_alvo].copy()
        if day_data.empty:
            resultados.append({"data": data_alvo.strftime('%d/%m'), "sem_dados": True, "pnl": 0.0, "trades": 0, "wins": 0, "wr": 0.0})
            continue

        tester = BacktestPro(
            symbol=symbol,
            n_candles=len(day_data),
            timeframe="M1",
            initial_balance=saldo,
            **strategy_params
        )
        # Injeta o fator em memória — NÃO toca o JSON
        tester.ai.confidence_relax_factor = relax_factor
        tester.data = day_data
        await tester.run()

        trades = tester.trades
        pnl = sum(t['pnl_fin'] for t in trades)
        wins = len([t for t in trades if t['pnl_fin'] > 0])
        wr = (wins / len(trades) * 100) if trades else 0.0
        saldo += pnl

        resultados.append({
            "data": data_alvo.strftime('%d/%m'),
            "sem_dados": False,
            "pnl": pnl,
            "trades": len(trades),
            "wins": wins,
            "wr": wr,
            "saldo": saldo,
        })

    pnl_total = sum(r["pnl"] for r in resultados)
    trades_total = sum(r["trades"] for r in resultados)
    wins_total = sum(r["wins"] for r in resultados)
    wr_global = (wins_total / trades_total * 100) if trades_total else 0.0
    dias_pos = len([r for r in resultados if not r.get("sem_dados") and r["pnl"] > 0])
    dias_neg = len([r for r in resultados if not r.get("sem_dados") and r["pnl"] < 0])

    return {
        "label": label,
        "factor": relax_factor,
        "pnl_total": pnl_total,
        "saldo_final": saldo,
        "retorno_pct": (pnl_total / capital_inicial) * 100,
        "trades": trades_total,
        "wr": wr_global,
        "dias_pos": dias_pos,
        "dias_neg": dias_neg,
        "resultados": resultados,
    }


async def comparar_fatores():
    logging.basicConfig(level=logging.WARNING, format='%(message)s')
    console = logging.getLogger("comp")
    console.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    console.addHandler(ch)

    console.info("=" * 70)
    console.info("📊 COMPARATIVO: confidence_relax_factor 0.80 vs 0.75")
    console.info("=" * 70)

    params_path = "backend/v22_locked_params.json"
    with open(params_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    strategy_params = config.get('strategy_params', {})
    capital = 3000.0
    symbol = "WIN$"

    console.info("📡 Carregando dados MT5...")
    loader = BacktestPro(symbol=symbol, n_candles=15_000, timeframe="M1")
    full_data = await loader.load_data()
    if full_data is None or full_data.empty:
        console.error("❌ Sem dados MT5.")
        return
    console.info(f"✅ {len(full_data)} candles carregados. Iniciando simulação dupla...\n")

    # Roda os dois cenários sequencialmente (mesmo full_data)
    console.info("🔷 Cenário A: fator = 0.80 (base V22.5.4)...")
    cenario_a = await rodar_cenario(full_data, symbol, capital, strategy_params, 0.80, "V22.5.4 (fator=0.80)")

    console.info("🔶 Cenário B: fator = 0.75 (teste)...")
    cenario_b = await rodar_cenario(full_data, symbol, capital, strategy_params, 0.75, "V22.5.4-B (fator=0.75)")

    # ─── Relatório comparativo ─────────────────────────────────────────────────
    console.info("")
    console.info("=" * 70)
    console.info("📋 RESULTADO COMPARATIVO — 14 dias")
    console.info("=" * 70)

    md = []
    md.append("# 📊 Comparativo: confidence_relax_factor 0.80 vs 0.75 — 14 Dias")
    md.append(f"- **Período**: 19/02 → 10/03/2026 | **Capital**: R$ {capital:.2f}\n")

    md.append("## 🏆 Resumo Consolidado\n")
    md.append("| Métrica | 🔷 V22.5.4 (0.80) | 🔶 Teste (0.75) | Δ Diferença |")
    md.append("|:--------|:-----------------:|:---------------:|:-----------:|")

    delta_pnl    = cenario_b['pnl_total'] - cenario_a['pnl_total']
    delta_trades = cenario_b['trades']    - cenario_a['trades']
    delta_wr     = cenario_b['wr']        - cenario_a['wr']

    md.append(f"| 💰 PnL Total | **R$ {cenario_a['pnl_total']:+.2f}** | **R$ {cenario_b['pnl_total']:+.2f}** | {delta_pnl:+.2f} |")
    md.append(f"| 🏦 Saldo Final | R$ {cenario_a['saldo_final']:.2f} | R$ {cenario_b['saldo_final']:.2f} | {delta_pnl:+.2f} |")
    md.append(f"| 📈 Retorno | {cenario_a['retorno_pct']:+.1f}% | {cenario_b['retorno_pct']:+.1f}% | {delta_pnl/capital*100:+.1f}pp |")
    md.append(f"| 🎯 Win Rate | {cenario_a['wr']:.1f}% | {cenario_b['wr']:.1f}% | {delta_wr:+.1f}pp |")
    md.append(f"| 📊 Total de Trades | {cenario_a['trades']} | {cenario_b['trades']} | {delta_trades:+d} |")
    md.append(f"| ✅ Dias Positivos | {cenario_a['dias_pos']}/14 | {cenario_b['dias_pos']}/14 | {cenario_b['dias_pos']-cenario_a['dias_pos']:+d} |")
    md.append(f"| ❌ Dias Negativos | {cenario_a['dias_neg']}/14 | {cenario_b['dias_neg']}/14 | {cenario_b['dias_neg']-cenario_a['dias_neg']:+d} |")

    # Tabela por dia
    md.append("\n## 📅 PnL por Pregão (Ambos os Cenários)\n")
    md.append("| Data | 🔷 PnL (0.80) | Trades | 🔶 PnL (0.75) | Trades | Δ PnL |")
    md.append("|:-----|:------------:|:------:|:-------------:|:------:|:-----:|")

    for ra, rb in zip(cenario_a['resultados'], cenario_b['resultados']):
        if ra.get('sem_dados'):
            md.append(f"| {ra['data']} | *sem dados* | - | *sem dados* | - | - |")
            continue
        delta = rb['pnl'] - ra['pnl']
        sinal = "🟢" if ra['pnl'] >= 0 else "🔴"
        sinal_b = "🟢" if rb['pnl'] >= 0 else "🔴"
        d_icon = "▲" if delta > 0 else ("▼" if delta < 0 else "=")
        md.append(f"| {ra['data']} | {sinal} R$ {ra['pnl']:+.2f} | {ra['trades']} | {sinal_b} R$ {rb['pnl']:+.2f} | {rb['trades']} | {d_icon} {delta:+.2f} |")

    # Análise
    md.append("\n## 💡 Análise de Impacto\n")
    if delta_pnl > 0:
        md.append(f"✅ **Fator 0.75 é MELHOR**: Ganho adicional de R$ {delta_pnl:+.2f} nos 14 dias.")
        md.append(f"   - {delta_trades:+d} trades adicionais foram executados.")
        if delta_wr >= 0:
            md.append(f"   - Win Rate melhorou {delta_wr:+.1f}pp → as novas entradas são de qualidade.")
            md.append("   - **Recomendação**: Atualizar `confidence_relax_factor = 0.75` no JSON.")
        else:
            md.append(f"   - Win Rate piorou {delta_wr:.1f}pp → mais trades, mas menor precisão.")
            md.append("   - **Recomendação**: Avaliar trade-off PnL×WR antes de aplicar.")
    elif delta_pnl < 0:
        md.append(f"⚠️ **Fator 0.80 é MELHOR**: Fator 0.75 gerou {delta_pnl:.2f} de resultado inferior.")
        md.append("   - As entradas adicionais liberadas com 0.75 não foram lucrativas.")
        md.append("   - **Recomendação**: Manter `confidence_relax_factor = 0.80` (V22.5.4 original).")
    else:
        md.append("➡️ **Resultados iguais**: O fator não gerou diferença nos 14 dias testados.")
        md.append("   - Manter `confidence_relax_factor = 0.80`.")

    md.append(f"\n---\n*Comparativo gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | SOTA V22.5.4*")

    output = "backend/comparativo_relax_factor_results.md"
    with open(output, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    console.info(f"\n{'='*70}")
    for k, v in [("🔷 V22.5.4 (0.80)", cenario_a), ("🔶 Teste (0.75)", cenario_b)]:
        console.info(f"  {k}: PnL={v['pnl_total']:+.2f} | WR={v['wr']:.1f}% | Trades={v['trades']} | Dias+={v['dias_pos']}/14")
    console.info(f"  Δ PnL : {delta_pnl:+.2f} | Δ Trades: {delta_trades:+d} | Δ WR: {delta_wr:+.1f}pp")
    console.info(f"{'='*70}")
    console.info(f"✅ Relatório salvo em: {output}")


if __name__ == "__main__":
    asyncio.run(comparar_fatores())
