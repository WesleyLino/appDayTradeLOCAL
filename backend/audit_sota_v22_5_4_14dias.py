"""
Auditoria SOTA V22.5.4 — 14 Dias Históricos (Fevereiro-Março 2026)
Capital operacional: R$ 3.000,00
Ativo: WIN$ M1
"""
import asyncio
import json
import os
import sys
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from backend.backtest_pro import BacktestPro

async def rodar_auditoria_14dias():
    logging.basicConfig(
        level=logging.WARNING,   # Silencia DEBUG/INFO do backtest em cada dia
        format='%(message)s'
    )
    console = logging.getLogger("auditoria")
    console.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    console.addHandler(handler)

    # ─── Parâmetros Golden V22.5.4 ───────────────────────────────────────────
    params_path = "backend/v22_locked_params.json"
    with open(params_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    strategy_params = config.get('strategy_params', {})
    initial_capital = 3000.0
    symbol = "WIN$"
    timeframe = "M1"

    # ─── Dias solicitados ─────────────────────────────────────────────────────
    # 14 pregões: fevereiro (19-27/02) + março (02-10/03)
    dias_str = [
        "19/02/2026",
        "20/02/2026",
        "23/02/2026",
        "24/02/2026",
        "25/02/2026",
        "26/02/2026",
        "27/02/2026",
        "02/03/2026",
        "03/03/2026",
        "04/03/2026",
        "05/03/2026",
        "06/03/2026",
        "09/03/2026",
        "10/03/2026",
    ]
    datas = [datetime.strptime(d, "%d/%m/%Y").date() for d in dias_str]

    console.info("=" * 70)
    console.info("🚀 AUDITORIA SOTA V22.5.4 — 14 DIAS HISTÓRICOS")
    console.info(f"   Capital: R$ {initial_capital:.2f} | Ativo: {symbol} | Timeframe: {timeframe}")
    console.info("=" * 70)

    # ─── Carga única de dados (n_candles suficiente para cobrir fev+mar) ──────
    console.info("📡 Conectando ao MT5 e carregando dados históricos...")
    loader = BacktestPro(symbol=symbol, n_candles=15_000, timeframe=timeframe)
    full_data = await loader.load_data()

    if full_data is None or full_data.empty:
        console.error("❌ Falha crítica: sem conexão com MT5 ou dados vazios.")
        return

    console.info(f"✅ Total de candles carregados: {len(full_data)} M1")
    console.info("")

    # ─── Estruturas de resultado ─────────────────────────────────────────────
    resultados_dia = []       # lista de dicts por dia
    pnl_acumulado = 0.0
    saldo_corrente = initial_capital

    # ─── Loop por dia ─────────────────────────────────────────────────────────
    for data_alvo in datas:
        data_str = data_alvo.strftime('%d/%m/%Y')
        console.info(f"📅 Processando {data_str}...")

        day_data = full_data[full_data.index.date == data_alvo].copy()

        if day_data.empty:
            console.warning(f"   ⚠️  Sem dados para {data_str} (feriado ou dado ausente).")
            resultados_dia.append({
                "data": data_str, "sem_dados": True,
                "pnl": 0.0, "trades": 0,
                "compras": 0, "vendas": 0,
                "pnl_compra": 0.0, "pnl_venda": 0.0,
                "wins": 0, "losses": 0, "win_rate": 0.0,
                "shadow": {}
            })
            continue

        tester = BacktestPro(
            symbol=symbol,
            n_candles=len(day_data),
            timeframe=timeframe,
            initial_balance=saldo_corrente,   # saldo composto acumulado
            **strategy_params
        )
        tester.data = day_data
        await tester.run()

        trades = tester.trades
        compras  = [t for t in trades if t['side'] == 'buy']
        vendas   = [t for t in trades if t['side'] == 'sell']
        pnl_dia  = sum(t['pnl_fin'] for t in trades)
        pnl_c    = sum(t['pnl_fin'] for t in compras)
        pnl_v    = sum(t['pnl_fin'] for t in vendas)
        wins     = len([t for t in trades if t['pnl_fin'] > 0])
        losses   = len([t for t in trades if t['pnl_fin'] <= 0])
        wr       = (wins / len(trades) * 100) if trades else 0.0

        pnl_acumulado += pnl_dia
        saldo_corrente += pnl_dia

        shadow = tester.shadow_signals
        oport_ia   = shadow.get('filtered_by_ai', 0)
        oport_flux = shadow.get('filtered_by_flux', 0)
        veto_h1    = shadow.get('veto_reasons', {}).get('VETO_TENDENCIA_BAIXA_H1', 0) + \
                     shadow.get('veto_reasons', {}).get('VETO_TENDENCIA_ALTA_H1', 0)
        veto_conf  = shadow.get('veto_reasons', {}).get('LOW_CONFIDENCE', 0)
        sell_only_block = shadow.get('veto_reasons', {}).get('SELL_ONLY_MODE', 0)

        resultados_dia.append({
            "data": data_str,
            "sem_dados": False,
            "pnl": pnl_dia,
            "pnl_c": pnl_c,
            "pnl_v": pnl_v,
            "trades": len(trades),
            "compras": len(compras),
            "vendas": len(vendas),
            "wins": wins,
            "losses": losses,
            "win_rate": wr,
            "oport_ia": oport_ia,
            "oport_flux": oport_flux,
            "veto_h1": veto_h1,
            "veto_conf": veto_conf,
            "sell_only": sell_only_block,
            "saldo": saldo_corrente,
        })

        icone = "🟢" if pnl_dia >= 0 else "🔴"
        console.info(f"   {icone}  PnL={pnl_dia:+.2f} | Trades={len(trades)} ({len(compras)}C/{len(vendas)}V) | WR={wr:.1f}%")

    # ─── Geração de relatório ─────────────────────────────────────────────────
    console.info("")
    console.info("📝 Gerando relatório...")

    md = []
    md.append("# 📊 Auditoria SOTA V22.5.4 — 14 Dias (19/02 → 10/03/2026)")
    md.append(f"- **Ativo**: {symbol} | **Timeframe**: M1")
    md.append(f"- **Capital Inicial**: R$ {initial_capital:.2f}")
    md.append("- **Configurações**: V22.5.4 (Confidence Relax H1 + Sell-Only Mode)\n")

    # Tabela resumo
    md.append("## 📈 Resumo Diário\n")
    md.append("| Data | PnL do Dia | Trades | 🟢 Compra | 🔴 Venda | Win Rate | Oport. Perdidas (IA/Flux) | Veto H1 | Saldo |")
    md.append("|:-----|:----------:|:------:|:---------:|:--------:|:--------:|:-------------------------:|:-------:|------:|")

    dias_positivos = 0
    dias_negativos = 0
    max_win = ("", -float('inf'))
    max_loss = ("", float('inf'))

    for r in resultados_dia:
        if r['sem_dados']:
            md.append(f"| {r['data']} | *sem dados* | - | - | - | - | - | - | - |")
            continue
        sinal = "🟢" if r['pnl'] >= 0 else "🔴"
        if r['pnl'] >= 0:
            dias_positivos += 1
            if r['pnl'] > max_win[1]:
                max_win = (r['data'], r['pnl'])
        else:
            dias_negativos += 1
            if r['pnl'] < max_loss[1]:
                max_loss = (r['data'], r['pnl'])

        md.append(
            f"| {r['data']} | {sinal} **R$ {r['pnl']:+.2f}** | {r['trades']} | "
            f"{r['compras']}t (R$ {r['pnl_c']:+.2f}) | {r['vendas']}t (R$ {r['pnl_v']:+.2f}) | "
            f"{r['win_rate']:.1f}% | {r['oport_ia']} / {r['oport_flux']} | "
            f"{r['veto_h1']} | R$ {r['saldo']:.2f} |"
        )

    dias_validos = [r for r in resultados_dia if not r['sem_dados']]
    total_trades_acum  = sum(r['trades'] for r in dias_validos)
    total_wins_acum    = sum(r['wins'] for r in dias_validos)
    total_losses_acum  = sum(r['losses'] for r in dias_validos)
    total_compras      = sum(r['compras'] for r in dias_validos)
    total_vendas       = sum(r['vendas'] for r in dias_validos)
    pnl_compras_total  = sum(r['pnl_c'] for r in dias_validos)
    pnl_vendas_total   = sum(r['pnl_v'] for r in dias_validos)
    wr_global          = (total_wins_acum / total_trades_acum * 100) if total_trades_acum else 0

    md.append("\n---\n")
    md.append("## 🏆 Resultado Consolidado (14 Pregões)\n")
    md.append("| Métrica | Valor |")
    md.append("|:--------|------:|")
    md.append(f"| 💰 PnL Total Acumulado | **R$ {pnl_acumulado:+.2f}** |")
    md.append(f"| 🏦 Saldo Final | **R$ {saldo_corrente:.2f}** |")
    md.append(f"| 📈 Retorno sobre Capital | **{(pnl_acumulado/initial_capital*100):+.1f}%** |")
    md.append(f"| 📅 Dias Positivos | {dias_positivos} / {len(dias_validos)} |")
    md.append(f"| 📅 Dias Negativos | {dias_negativos} / {len(dias_validos)} |")
    md.append(f"| 🎯 Win Rate Global | {wr_global:.1f}% ({total_wins_acum}W/{total_losses_acum}L) |")
    md.append(f"| 📊 Total de Trades | {total_trades_acum} ({total_compras}C / {total_vendas}V) |")
    md.append(f"| 🟢 PnL Operações Compradas | R$ {pnl_compras_total:+.2f} |")
    md.append(f"| 🔴 PnL Operações Vendidas | R$ {pnl_vendas_total:+.2f} |")
    md.append(f"| 🏅 Melhor Dia | {max_win[0]} (+R$ {max_win[1]:.2f}) |")
    md.append(f"| 💔 Pior Dia | {max_loss[0]} (R$ {max_loss[1]:.2f}) |")

    # ─── Análise detalhada por dia ────────────────────────────────────────────
    md.append("\n---\n")
    md.append("## 🔍 Análise Detalhada por Pregão\n")

    for r in resultados_dia:
        if r['sem_dados']:
            md.append(f"### 📅 {r['data']} — *Sem Dados (Feriado/Ausente)*\n")
            continue

        sinal = "🟢 LUCRO" if r['pnl'] >= 0 else "🔴 PREJUÍZO"
        md.append(f"### 📅 {r['data']} — {sinal}: R$ {r['pnl']:+.2f}")
        md.append(f"- **Operações Compradas**: {r['compras']} trades → PnL R$ {r['pnl_c']:+.2f}")
        md.append(f"- **Operações Vendidas**: {r['vendas']} trades → PnL R$ {r['pnl_v']:+.2f}")
        md.append(f"- **Win Rate**: {r['win_rate']:.1f}% ({r['wins']}W / {r['losses']}L)")
        md.append(f"- **Shadow — Oport. Perdidas por IA**: {r['oport_ia']} entradas vetadas por baixa confiança")
        md.append(f"- **Shadow — Oport. Perdidas por Fluxo**: {r['oport_flux']} entradas vetadas por fluxo insuficiente")
        md.append(f"- **Vetos H1 (Filtro Anti-Contratendência)**: {r['veto_h1']}")

        # Insights automáticos
        alertas = []
        if r['pnl'] < -50:
            alertas.append("⚠️ **Drawdown elevado**: Revisar se o Sell-Only H1 estava ativo durante a queda.")
        if r['pnl_c'] < -30 and r['veto_h1'] > 0:
            alertas.append("🛡️ **Proteção Sell-Only**: Vetos H1 ativos — compras que passaram podem ter sido contra tendência residual.")
        if r['oport_ia'] > 10:
            alertas.append(f"🔍 **Alta filtragem IA**: {r['oport_ia']} oportunidades vetadas. Avaliar se o `confidence_relax_factor` deve ser ajustado.")
        if r['oport_flux'] > 10:
            alertas.append(f"📉 **Alta filtragem de Fluxo**: {r['oport_flux']} vetos por volume insuficiente. Mercado lateral/fraco.")
        if r['win_rate'] > 75 and r['trades'] >= 3:
            alertas.append("🏆 **Dia de alto rendimento**: Win Rate > 75%. Candidato a aumentar lote dinâmico.")
        if not alertas:
            alertas.append("✅ Desempenho dentro do esperado para o perfil V22.5.4.")

        for a in alertas:
            md.append(f"  - {a}")
        md.append("")

    # ─── Análise COMPRA vs VENDA ──────────────────────────────────────────────
    md.append("---\n")
    md.append("## ⚖️ Análise COMPRA vs VENDA — Contribuição para o Resultado\n")
    md.append("| Lado | Total Trades | PnL Acumulado | % do Resultado |")
    md.append("|:-----|:------------:|:-------------:|:--------------:|")
    contrib_c = (pnl_compras_total / abs(pnl_acumulado) * 100) if pnl_acumulado != 0 else 0
    contrib_v = (pnl_vendas_total / abs(pnl_acumulado) * 100) if pnl_acumulado != 0 else 0
    md.append(f"| 🟢 COMPRA | {total_compras} | R$ {pnl_compras_total:+.2f} | {contrib_c:+.1f}% |")
    md.append(f"| 🔴 VENDA  | {total_vendas} | R$ {pnl_vendas_total:+.2f} | {contrib_v:+.1f}% |")

    # ─── Sugestões de melhoria ────────────────────────────────────────────────
    md.append("\n---\n")
    md.append("## 🚀 Análise de Melhorias para Assertividade\n")
    md.append("### Pontos de Atenção\n")

    total_ia   = sum(r.get('oport_ia', 0) for r in dias_validos)
    total_flux = sum(r.get('oport_flux', 0) for r in dias_validos)
    total_h1   = sum(r.get('veto_h1', 0) for r in dias_validos)

    md.append(f"- **Total de oportunidades vetadas pela IA** (baixa confiança): **{total_ia}**")
    md.append(f"- **Total de oportunidades vetadas por fluxo**: **{total_flux}**")
    md.append(f"- **Total de vetos H1** (proteção anti-contratendência V22.5.4): **{total_h1}**")
    md.append("")
    md.append("### Sugestões de Calibragem (Baseadas nos 14 Pregões)\n")

    if total_ia > 50:
        md.append(f"1. **Confidence Relax Factor**: Com {total_ia} vetos, considerar reduzir `confidence_relax_factor` de 0.80 para 0.75 "
                  f"para relaxar ainda mais o threshold em dias de ATR alto + H1 alinhado.")
    else:
        md.append("1. **Confidence Threshold**: Filtragem de IA equilibrada. Manter `confidence_relax_factor = 0.80`.")

    if total_flux > 30:
        md.append(f"2. **Fluxo/Volume**: {total_flux} oportunidades vetadas por volume. Avaliar reduzir `vol_spike_mult` de 1.5 para 1.3 "
                  f"em períodos de baixa liquidez (antes de 10h).")
    else:
        md.append("2. **Filtro de Fluxo/Volume**: Calibrado adequadamente. Manter configurações atuais.")

    if pnl_compras_total < 0 and pnl_vendas_total > 0:
        md.append("3. **Bias Direcional**: Compras estão no vermelho enquanto vendas são lucrativas — confirma eficácia do Sell-Only H1. "
                  "Considerar aumentar o rigor do filtro de compras em dias de H1 neutro.")
    elif pnl_vendas_total < 0 and pnl_compras_total > 0:
        md.append("3. **Bias Direcional**: Vendas estão no vermelho — revisar gatilhos de venda, especialmente RSI sell level e BB superior.")
    else:
        md.append("3. **Bias Direcional**: Ambos os lados contribuindo positivamente. Estratégia equilibrada.")

    if wr_global < 55:
        md.append("4. **Win Rate Global abaixo de 55%**: Revisar o `adx_min_threshold` — entradas em mercados fracos podem estar diluindo o WR.")
    elif wr_global > 65:
        md.append(f"4. **Win Rate Global de {wr_global:.1f}%**: Excelente! Pode-se estudar aumentar o tamanho do lote em dias de alta volatilidade alinhada.")
    else:
        md.append(f"4. **Win Rate Global de {wr_global:.1f}%**: Dentro do target. Manter configurações V22.5.4.")

    md.append("\n---\n")
    md.append(f"*Auditoria gerada automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')} | SOTA V22.5.4*")

    # ─── Salvar ───────────────────────────────────────────────────────────────
    output_path = "backend/audit_sota_v22_5_4_14dias_results.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    console.info(f"✅ Relatório salvo em: {output_path}")
    console.info("")
    console.info("=" * 70)
    console.info(f"  PnL TOTAL 14 DIAS : R$ {pnl_acumulado:+.2f}")
    console.info(f"  SALDO FINAL       : R$ {saldo_corrente:.2f}")
    console.info(f"  RETORNO           : {(pnl_acumulado/initial_capital*100):+.1f}%")
    console.info(f"  WIN RATE GLOBAL   : {wr_global:.1f}%")
    console.info(f"  DIAS POSITIVOS    : {dias_positivos}/{len(dias_validos)}")
    console.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(rodar_auditoria_14dias())
