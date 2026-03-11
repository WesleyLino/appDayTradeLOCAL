"""
Diagnóstico: Por que o Sell-Only H1 NÃO ativou no dia 10/03/2026?
Analisa o h1_trend calculado pelo proxy de backtest minuto a minuto no dia 10/03.
"""
import asyncio
import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import date
from backend.backtest_pro import BacktestPro

async def diagnosticar_h1_10mar():
    logging.basicConfig(level=logging.WARNING, format='%(message)s')
    console = logging.getLogger("diag")
    console.setLevel(logging.INFO)
    ch = logging.StreamHandler(); ch.setLevel(logging.INFO)
    console.addHandler(ch)

    console.info("=" * 70)
    console.info("🔍 DIAGNÓSTICO SELL-ONLY H1 — 10/03/2026")
    console.info("=" * 70)

    # Carrega dados com janela larga (precisa do histórico anterior para a MA)
    loader = BacktestPro(symbol="WIN$", n_candles=10_000, timeframe="M1")
    full_data = await loader.load_data()

    if full_data is None or full_data.empty:
        console.error("❌ Sem dados do MT5.")
        return

    alvo = date(2026, 3, 10)
    day_data = full_data[full_data.index.date == alvo].copy()

    if day_data.empty:
        console.error("❌ Nenhum candle M1 encontrado para 10/03/2026.")
        return

    console.info(f"✅ {len(day_data)} candles M1 encontrados para 10/03/2026")
    console.info(f"   Abertura: {day_data.index[0].strftime('%H:%M')} | "
                 f"Fechamento: {day_data.index[-1].strftime('%H:%M')}")
    console.info(f"   Preço Abertura:  {day_data['close'].iloc[0]:.0f}")
    console.info(f"   Preço Fechamento:{day_data['close'].iloc[-1]:.0f}")
    console.info(f"   Variação Dia:    {day_data['close'].iloc[-1] - day_data['close'].iloc[0]:+.0f} pts")
    console.info("")

    # ─── Recalcula o proxy de H1 do backtest para cada candle do dia ──────────
    # O backtest usa os 60 candles ANTERIORES ao candle atual (janela pré-dia)
    # Então precisa do data completo (full_data), não só o day_data
    idx_inicio = full_data.index.searchsorted(day_data.index[0])

    h1_por_horario = {}   # hora → {trend, close, ma, diff_pct}
    sequencia_h1   = []   # para saber quando h1 mudou

    console.info("📊 ANÁLISE HORA A HORA DO H1_TREND (Proxy Backtest: MA60 M1 ±0.2%)")
    console.info("-" * 70)
    console.info(f"{'Horário':<10} {'Preço':>8} {'MA60 M1':>10} {'Δ%':>8} {'H1 Trend':>12} {'Sell-Only?':>12}")
    console.info("-" * 70)

    estado_anterior = None
    sell_only_contagem = 0
    tendencia_negativa_max = 0.0

    for j, (ts, row) in enumerate(day_data.iterrows()):
        i = idx_inicio + j
        ma60 = full_data['close'].iloc[max(0, i-60):i].mean()

        if ma60 == 0 or i < 60:
            trend = 0
        elif row['close'] > ma60 * 1.002:
            trend = 1
        elif row['close'] < ma60 * 0.998:
            trend = -1
        else:
            trend = 0

        diff_pct = ((row['close'] / ma60) - 1) * 100 if ma60 > 0 else 0
        tendencia_negativa_max = min(tendencia_negativa_max, diff_pct)

        sell_only = (trend == -1)
        if sell_only:
            sell_only_contagem += 1

        hora = ts.strftime('%H:%M')

        # Registra somente quando muda o estado OU a cada hora cheia
        if trend != estado_anterior or ts.minute == 0:
            trend_str = "⬆️  ALTA (+1)" if trend == 1 else ("⬇️  BAIXA (-1)" if trend == -1 else "➡️  NEUTRO (0)")
            so_str    = "🛡️ ATIVO" if sell_only else "❌ inativo"
            console.info(f"{hora:<10} {row['close']:>8.0f} {ma60:>10.1f} {diff_pct:>7.3f}% {trend_str:>14} {so_str:>12}")

        estado_anterior = trend

    console.info("-" * 70)
    console.info("")
    console.info(f"🔎 RESUMO DO DIAGNÓSTICO:")
    console.info(f"   ⏱  Candles com Sell-Only ATIVO (h1_trend=-1) : {sell_only_contagem} / {len(day_data)}")
    console.info(f"   📉 Máxima diferença negativa Preço/MA60      : {tendencia_negativa_max:.3f}%")
    console.info(f"   🎯 Limiar de ativação do Sell-Only            : < -0.200%")
    console.info("")

    if sell_only_contagem == 0:
        console.info("⚠️  DIAGNÓSTICO: O proxy MA60 M1 ±0.2% foi INSUFICIENTE para detectar a queda do dia 10/03.")
        console.info(f"   O pior desvio foi {tendencia_negativa_max:.3f}% — abaixo do limiar de -0.200%.")
        console.info("   O mercado sofreu uma queda gradual que não atingiu a margem de -0.2% em relação")
        console.info("   à MA de 60min M1. O proxy M1 é muito suave para capturar tendências H1 reais.")
        console.info("")
        console.info("💡 SOLUÇÃO PROPOSTA (não implementada ainda - aguardando autorização):")
        console.info("   Usar o resample H1 real no loop do backtest (já disponível na linha 449-458)")
        console.info("   em vez do proxy MA60 M1. O resample H1 real detecta a queda do 10/03 corretamente.")
        novomargem = abs(tendencia_negativa_max) * 0.5
        console.info(f"   Alternativa: Reduzir margem do proxy de 0.200% para ~{novomargem:.3f}%")
    else:
        console.info(f"✅ Sell-Only ativou {sell_only_contagem} candles — verificar por que as compras ainda ocorreram.")

    console.info("")
    console.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(diagnosticar_h1_10mar())
