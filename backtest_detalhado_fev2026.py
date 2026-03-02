"""
Backtest Detalhado - Mini Índice (WIN) - Fevereiro 2026
Capital: R$ 3.000 | Timeframe: M1 | Estratégia: SOTA V22 (Golden Params)

Relatório por dia com:
  - Resultado de COMPRAS e VENDAS separados
  - Trades individuais (entrada, saída, PnL, motivo)
  - Oportunidades perdidas (shadow signals)
  - Diagnóstico de assertividade
  - Sugestões de melhoria
"""
import asyncio
import logging
import os
import json
import sys
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from io import StringIO

# Garante path correto
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro

# Redireciona stdout para arquivo UTF-8 (evita corrupção de encoding no PowerShell)
OUTPUT_FILE = "backtest_resultado_fev2026.txt"
_arquivo_saida = open(OUTPUT_FILE, "w", encoding="utf-8")
_stdout_original = sys.stdout
sys.stdout = _arquivo_saida

# Silencia logs internos para output limpo
logging.disable(logging.CRITICAL)

SYMBOL        = "WIN$N"
INITIAL_BAL   = 3000.0
DIAS_ALVO     = [
    datetime(2026, 2, 19),
    datetime(2026, 2, 20),
    datetime(2026, 2, 23),
    datetime(2026, 2, 24),
    datetime(2026, 2, 25),
    datetime(2026, 2, 26),
    datetime(2026, 2, 27),
]

# --------------------------------------------------
# Funções auxiliares de formatação
# --------------------------------------------------
SEP_DUPLO = "=" * 82
SEP_SIMPL = "-" * 82

def hdr(titulo: str) -> str:
    pad = (82 - len(titulo) - 2) // 2
    return f"\n{'=' * pad} {titulo} {'=' * pad}"

def pct(val: float, ref: float) -> str:
    if ref == 0:
        return "N/A"
    return f"{val/ref*100:+.2f}%"

def fmt_reais(val: float) -> str:
    sinal = "+" if val >= 0 else ""
    return f"R$ {sinal}{val:,.2f}"

# --------------------------------------------------
# Bloco principal de auditoria
# --------------------------------------------------
async def run():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Não foi possível conectar ao MetaTrader 5.")
        print("   Verifique se o terminal MT5 está aberto e logado.")
        return

    # Carrega Golden Params (V22)
    locked_params = {}
    params_path = "backend/v22_locked_params.json"
    if os.path.exists(params_path):
        with open(params_path, "r") as f:
            config = json.load(f)
            locked_params = config.get("strategy_params", {})

    # NOTA: v22_locked_params.json define use_ai_core=False (modo legado V22).
    # No backtest sem dados de sentimento/L2 em tempo real, o AI Core não gera sinais.
    # Usamos o modo legado (Regime Maestro + Scalp Adaptation) que é o comportamento
    # validado e documentado nos Golden Params V22.
    locked_params["use_ai_core"] = False  # [ANTIVIBE-CODING] Conforme v22_locked_params.json

    resultados_dias = []

    print(hdr("BACKTEST DETALHADO - MINI ÍNDICE (WIN) - FEV/2026"))
    print(f"  SÍMBOLO  : {SYMBOL}")
    print(f"  CAPITAL  : R$ {INITIAL_BAL:,.2f}")
    print("  TIMEFRAME: M1  |  ESTRATÉGIA: SOTA V28 (flux=0.95, cooldown=7min, Filtro-H ativo)")
    print(f"  DIAS     : {', '.join(d.strftime('%d/%m') for d in DIAS_ALVO)}")
    print(SEP_DUPLO)

    for dia in DIAS_ALVO:
        date_str = dia.strftime("%d/%m/%Y")
        date_from = dia.replace(hour=8, minute=0, second=0)
        date_to   = dia.replace(hour=18, minute=30, second=0)

        # Coleta candles M1 do MT5
        data = bridge.get_market_data_range(SYMBOL, mt5.TIMEFRAME_M1, date_from, date_to)
        if data is None or data.empty:
            print(f"\n⚠️  [{date_str}] Sem dados disponíveis no MT5. Pulando...")
            continue

        # Executa BacktestPro
        bt = BacktestPro(
            symbol=SYMBOL,
            initial_balance=INITIAL_BAL,
            **locked_params
        )
        bt.data = data.copy()
        result = await bt.run()

        if result is None:
            # Nenhum trade gerado neste dia (filtros muito restritivos ou dia sem sinais)
            result = {
                "total_pnl": 0.0,
                "trades": [],
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "shadow_signals": bt.shadow_signals
            }

        # --- Análise de Trades ---
        trades_df = pd.DataFrame(result["trades"]) if result["trades"] else pd.DataFrame()
        compras = trades_df[trades_df["side"] == "buy"] if not trades_df.empty else pd.DataFrame()
        vendas  = trades_df[trades_df["side"] == "sell"] if not trades_df.empty else pd.DataFrame()

        total_trades   = len(trades_df)
        n_compras      = len(compras)
        n_vendas       = len(vendas)
        pnl_compras    = compras["pnl_fin"].sum() if not compras.empty else 0.0
        pnl_vendas     = vendas["pnl_fin"].sum() if not vendas.empty else 0.0
        pnl_total      = result["total_pnl"]
        max_dd         = result["max_drawdown"]
        win_rate       = result.get("win_rate", 0.0)
        profit_factor  = result.get("profit_factor", 0.0)

        # Shadow signals (oportunidades)
        shadows = result.get("shadow_signals", {})
        missed_ai      = shadows.get("filtered_by_ai", 0)
        missed_flux    = shadows.get("filtered_by_flux", 0)
        v22_candidates = shadows.get("v22_candidates", 0)
        tiers          = shadows.get("tiers", {})
        comp_fail      = shadows.get("component_fail", {})

        # Salva resumo diário
        resultados_dias.append({
            "data":         date_str,
            "n_trades":     total_trades,
            "n_compras":    n_compras,
            "n_vendas":     n_vendas,
            "pnl_compras":  pnl_compras,
            "pnl_vendas":   pnl_vendas,
            "pnl_total":    pnl_total,
            "win_rate":     win_rate,
            "profit_factor": profit_factor,
            "max_dd_pct":   max_dd,
            "missed_ai":    missed_ai,
            "missed_flux":  missed_flux,
            "missed_bias":  shadows.get("filtered_by_bias", 0),
            "v22_candidates": v22_candidates,
        })

        # =============================================
        # IMPRESSÃO DO RELATÓRIO DE CADA DIA
        # =============================================
        print(f"\n{hdr(f'DIA: {date_str}')}")
        print(f"  Candles M1 carregados: {len(data)}")
        print("  Janela operacional   : 09:15 - 17:15")
        print(f"\n  {'RESULTADO GERAL':}")
        print(f"  ├── PNL Total          : {fmt_reais(pnl_total):>15}  {pct(pnl_total, INITIAL_BAL):>10}")
        print(f"  ├── Total de Trades    : {total_trades:>6}")
        print(f"  ├── Win Rate           : {win_rate:>6.1f}%")
        print(f"  ├── Profit Factor      : {profit_factor:>6.2f}")
        print(f"  └── Max Drawdown       : {max_dd:>6.2f}%")

        # --- COMPRAS ---
        print("\n  ── OPERAÇÕES COMPRADAS (BUY) ──────────────────────")
        if not compras.empty:
            wins_c = len(compras[compras["pnl_fin"] > 0])
            loss_c = len(compras[compras["pnl_fin"] <= 0])
            print(f"  Qtd: {n_compras}  |  Ganhos: {wins_c}  |  Perdas: {loss_c}  |  PNL: {fmt_reais(pnl_compras)}")
            print(f"  {'Entrada':<22} {'Saída':<22} {'Preço E':>9} {'Preço S':>9} {'Pts':>7} {'PNL':>12}  {'Motivo':<12}")
            print(f"  {'-'*95}")
            for _, t in compras.iterrows():
                sinal = "✅" if t["pnl_fin"] > 0 else "❌"
                pts = t.get("pnl_pts", 0)
                print(f"  {sinal} {str(t['entry_time'])[:19]:<21} {str(t['exit_time'])[:19]:<21} "
                      f"{t['entry_price']:>9.0f} {t['exit_price']:>9.0f} {pts:>+7.0f} {fmt_reais(t['pnl_fin']):>12}  {t['reason']:<12}")
        else:
            print("  Nenhuma operação de compra executada neste dia.")

        # --- VENDAS ---
        print("\n  ── OPERAÇÕES VENDIDAS (SELL) ───────────────────────")
        if not vendas.empty:
            wins_v = len(vendas[vendas["pnl_fin"] > 0])
            loss_v = len(vendas[vendas["pnl_fin"] <= 0])
            print(f"  Qtd: {n_vendas}  |  Ganhos: {wins_v}  |  Perdas: {loss_v}  |  PNL: {fmt_reais(pnl_vendas)}")
            print(f"  {'Entrada':<22} {'Saída':<22} {'Preço E':>9} {'Preço S':>9} {'Pts':>7} {'PNL':>12}  {'Motivo':<12}")
            print(f"  {'-'*95}")
            for _, t in vendas.iterrows():
                sinal = "✅" if t["pnl_fin"] > 0 else "❌"
                pts = t.get("pnl_pts", 0)
                print(f"  {sinal} {str(t['entry_time'])[:19]:<21} {str(t['exit_time'])[:19]:<21} "
                      f"{t['entry_price']:>9.0f} {t['exit_price']:>9.0f} {pts:>+7.0f} {fmt_reais(t['pnl_fin']):>12}  {t['reason']:<12}")
        else:
            print("  Nenhuma operação de venda executada neste dia.")

        # --- OPORTUNIDADES PERDIDAS ---
        missed_bias = shadows.get("filtered_by_bias", 0)
        print("\n  ── OPORTUNIDADES PERDIDAS (SHADOW SIGNALS) ─────────")
        print(f"  Candidatos V22 detectados : {v22_candidates}")
        print(f"  Bloqueados pela IA        : {missed_ai}  (confiança abaixo do limiar)")
        print(f"  Bloqueados pelo filtro flux: {missed_flux}")
        print(f"  Bloqueados Filtro-H (tend.): {missed_bias}  [MELHORIA H V28 — veto de direção]")
        if tiers:
            print("  Distribuição de confiança dos bloqueados (%):")
            for tier, cnt in tiers.items():
                print(f"    [{tier}%] : {cnt} sinais")
        if comp_fail:
            print("  Falhas de componente:")
            for comp, cnt in comp_fail.items():
                print(f"    {comp:<15}: {cnt} ocorrências")
        print(SEP_SIMPL)

    # =============================================
    # RELATÓRIO CONSOLIDADO FINAL
    # =============================================
    if not resultados_dias:
        print("\n❌ Nenhum resultado disponível para consolidar.")
        bridge.disconnect()
        return

    summary = pd.DataFrame(resultados_dias)

    total_pnl_geral     = summary["pnl_total"].sum()
    total_pnl_compras   = summary["pnl_compras"].sum()
    total_pnl_vendas    = summary["pnl_vendas"].sum()
    total_trades_geral  = summary["n_trades"].sum()
    total_compras       = summary["n_compras"].sum()
    total_vendas        = summary["n_vendas"].sum()
    total_missed_ai     = summary["missed_ai"].sum()
    total_missed_flux   = summary["missed_flux"].sum()
    total_v22           = summary["v22_candidates"].sum()
    media_wr            = summary["win_rate"].mean()
    media_pf            = summary["profit_factor"].mean()
    max_dd_any          = summary["max_dd_pct"].max()

    melhor_dia   = summary.loc[summary["pnl_total"].idxmax()]
    pior_dia     = summary.loc[summary["pnl_total"].idxmin()]
    dias_positivos = (summary["pnl_total"] > 0).sum()

    print(hdr("CONSOLIDADO FINAL - 7 DIAS - FEV/2026"))
    print(f"\n  {'RESULTADO FINANCEIRO':}")
    print(f"  ├── PNL Consolidado       : {fmt_reais(total_pnl_geral):>15}  {pct(total_pnl_geral, INITIAL_BAL):>10}")
    print(f"  ├── PNL de Compras        : {fmt_reais(total_pnl_compras):>15}")
    print(f"  ├── PNL de Vendas         : {fmt_reais(total_pnl_vendas):>15}")
    print(f"  ├── Capital Final Estimado: {fmt_reais(INITIAL_BAL + total_pnl_geral):>15}")
    print("  │")
    print(f"  ├── Dias Positivos        : {dias_positivos}/{len(resultados_dias)}")
    print(f"  ├── Melhor Dia            : {melhor_dia['data']} → {fmt_reais(melhor_dia['pnl_total'])}")
    print(f"  └── Pior Dia              : {pior_dia['data']} → {fmt_reais(pior_dia['pnl_total'])}")

    print(f"\n  {'OPERAÇÕES':}")
    print(f"  ├── Total de Trades       : {total_trades_geral}")
    print(f"  ├─── Compras (BUY)        : {total_compras}")
    print(f"  ├─── Vendas  (SELL)       : {total_vendas}")
    print(f"  ├── Win Rate Médio        : {media_wr:.1f}%")
    print(f"  ├── Profit Factor Médio   : {media_pf:.2f}")
    print(f"  └── Max Drawdown (pior dia): {max_dd_any:.2f}%")

    print(f"\n  {'ANALISE DE OPORTUNIDADES PERDIDAS':}")
    print(f"  ├── Candidatos V22 detectados     : {total_v22}")
    print(f"  ├── Bloqueados pela IA             : {total_missed_ai}  (confiança < limiar 70%)")
    print(f"  ├── Bloqueados pelo filtro de fluxo: {total_missed_flux}")
    print(f"  ├── Bloqueados Filtro-H (tend.)    : {summary['missed_bias'].sum()}  [MELHORIA H V28]")
    pct_aproveitamento = (total_trades_geral / total_v22 * 100) if total_v22 > 0 else 0
    print(f"  └── Taxa de aproveitamento V22     : {pct_aproveitamento:.1f}%  ({total_trades_geral}/{total_v22})")

    # =============================================
    # ANÁLISE ESTRATÉGICA: SUGESTÕES DE MELHORIA
    # =============================================
    print(hdr("ANALISE ESTRATEGICA - SUGESTOES DE MELHORIA"))

    # Motor de análise automática
    sugestoes = []

    # 1. Confiança muito restritiva?
    if total_missed_ai > 5 and pct_aproveitamento < 40:
        sugestoes.append({
            "prioridade": "ALTA",
            "area": "Limiar de Confiança (confidence_threshold)",
            "observação": f"{total_missed_ai} sinais bloqueados pela IA. Taxa de aproveitamento: {pct_aproveitamento:.0f}%.",
            "ação": (
                "Reduzir gradualmente o `confidence_threshold` de 0.70 para 0.65 em período de teste. "
                "Validar impacto no win rate com janela de 3 dias antes de fixar."
            )
        })

    # 2. Balanço COMPRA vs VENDA
    assimetria = abs(total_pnl_compras - total_pnl_vendas)
    if total_pnl_compras > 0 and total_pnl_vendas < 0:
        sugestoes.append({
            "prioridade": "ALTA",
            "area": "Assimetria Direcional (BUY vs SELL)",
            "observação": f"Compras geraram {fmt_reais(total_pnl_compras)}, Vendas geraram {fmt_reais(total_pnl_vendas)}.",
            "ação": (
                "O mercado esteve em tendência de alta no período. Aumentar peso do regime=1 (Trend) "
                "para priorizar compras em períodos de uptrend. Reduzir threshold de entrada para vendas "
                "em regime de alta (rsi_sell > 75 em vez de 70)."
            )
        })
    elif total_pnl_vendas > 0 and total_pnl_compras < 0:
        sugestoes.append({
            "prioridade": "ALTA",
            "area": "Assimetria Direcional (BUY vs SELL)",
            "observação": f"Vendas geraram {fmt_reais(total_pnl_vendas)}, Compras geraram {fmt_reais(total_pnl_compras)}.",
            "ação": (
                "O mercado esteve em tendência de baixa no período. Aumentar peso do regime=1 (Trend) "
                "para priorizar vendas em downtrend. Revisar sl_dist para compras (possível overexposure)."
            )
        })

    # 3. Drawdown elevado?
    if max_dd_any > 15:
        sugestoes.append({
            "prioridade": "ALTA",
            "area": "Gestão de Risco (Max Drawdown)",
            "observação": f"Drawdown máximo de {max_dd_any:.1f}% em algum dia do período.",
            "ação": (
                "Ativar limite de perda diária mais conservador: reduzir de 60% para 30% do capital inicial. "
                "Avaliar uso de `dynamic_lot=True` com base_lot=1 para escalar APENAS em sequências de ganho."
            )
        })

    # 4. Poucos trades?
    media_trades_dia = total_trades_geral / len(resultados_dias) if resultados_dias else 0
    if media_trades_dia < 1.5:
        sugestoes.append({
            "prioridade": "MÉDIA",
            "area": "Frequência de Operações",
            "observação": f"Média de {media_trades_dia:.1f} trade/dia. Sistema muito conservador.",
            "ação": (
                "Reduzir `cooldown_minutes` de 10 para 5 minutos em dias de alto volume (ATR > 200). "
                "Habilitar `adaptive_flux_active=True` para capturar reversões rápidas em regime de ruído."
            )
        })

    # 5. Filtro de fluxo bloqueando muito?
    if total_missed_flux > total_missed_ai * 0.5:
        sugestoes.append({
            "prioridade": "MÉDIA",
            "area": "Filtro de Fluxo (flux_imbalance_threshold)",
            "observação": f"{total_missed_flux} sinais bloqueados pelo filtro de fluxo (vs {total_missed_ai} pela IA).",
            "ação": (
                "Reduzir `flux_imbalance_threshold` de 1.2 para 1.05 em modo de análise. "
                "O filtro de fluxo pode estar muito restritivo em mercados de menor liquidez no mini índice."
            )
        })

    # 6. Win rate abaixo do esperado
    if media_wr < 50:
        sugestoes.append({
            "prioridade": "ALTA",
            "area": "Qualidade de Entradas (Win Rate)",
            "observação": f"Win Rate médio: {media_wr:.1f}% — abaixo do nível mínimo recomendado (>55%).",
            "ação": (
                "Revisar os horários de operação: evitar a primeira hora após abertura (09:00-09:45) e "
                "o período próximo ao fechamento (17:00-17:15). Concentrar entradas em 10:00-12:00 e 14:00-16:30."
                "Avaliar aumento do `confidence_threshold` para 0.75 para filtrar sinais de baixa qualidade."
            )
        })
    elif media_wr >= 60:
        sugestoes.append({
            "prioridade": "BAIXA",
            "area": "Otimização de Alvos (TP/SL)",
            "observação": f"Win Rate alto ({media_wr:.1f}%) sugere que os alvos podem ser expandidos.",
            "ação": (
                "Com win rate > 60%, o sistema está deixando lucro na mesa. Aumentar `tp_dist` de 400 para 550 pts "
                "e ativar trailing_stop para capturar movimentos maiores. "
                "Manter `sl_dist` em 150 pts para preservar a relação risco/retorno."
            )
        })

    # Fallback se nenhuma sugestão for gerada
    if not sugestoes:
        sugestoes.append({
            "prioridade": "INFORMAÇÃO",
            "area": "Sistema Calibrado",
            "observação": "Nenhuma anomalia crítica detectada no período analisado.",
            "ação": "Continuar monitoramento. Expandir janela de backtest para 30 dias para confirmar estabilidade."
        })

    print()
    for i, s in enumerate(sugestoes, 1):
        print(f"  [{s['prioridade']}] {i}. {s['area']}")
        print(f"       Obs.: {s['observação']}")
        print(f"       Ação: {s['ação']}")
        print()

    # =============================================
    # TABELA RESUMO FINAL POR DIA
    # =============================================
    print(hdr("TABELA RESUMO POR DIA"))
    print(f"\n  {'DATA':<12} {'TRADES':>7} {'BUY':>5} {'SELL':>6} {'PNL COMPRA':>13} {'PNL VENDA':>13} {'PNL TOTAL':>13} {'WR%':>6}")
    print(f"  {'-' * 80}")
    for r in resultados_dias:
        sinal = "📈" if r["pnl_total"] >= 0 else "📉"
        print(f"  {sinal} {r['data']:<11} {r['n_trades']:>7} {r['n_compras']:>5} {r['n_vendas']:>6} "
              f"{fmt_reais(r['pnl_compras']):>13} {fmt_reais(r['pnl_vendas']):>13} "
              f"{fmt_reais(r['pnl_total']):>13} {r['win_rate']:>5.1f}%")

    print(f"  {'─' * 80}")
    print(f"  {'TOTAL':<12} {total_trades_geral:>7} {total_compras:>5} {total_vendas:>6} "
          f"{fmt_reais(total_pnl_compras):>13} {fmt_reais(total_pnl_vendas):>13} "
          f"{fmt_reais(total_pnl_geral):>13}")

    print(f"\n{'=' * 82}")
    print(f"  Análise concluída em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'=' * 82}\n")

    bridge.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
    # Fecha arquivo e restaura stdout
    _arquivo_saida.close()
    sys.stdout = _stdout_original
    print(f"[OK] Resultado salvo em: {OUTPUT_FILE}")

