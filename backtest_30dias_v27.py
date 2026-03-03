"""
Backtest Extendido - Mini Índice (WIN) - 30 Dias Úteis
Capital: R$ 3.000 | Timeframe: M1 | Estratégia: SOTA V27 (Golden Params)

Cobre os 30 dias úteis anteriores a 28/02/2026 (19/01 → 27/02).
Dias com pregão suspenso (Carnaval 16-17/02) são ignorados automaticamente.

Relatório por dia com:
  - Resultado de COMPRAS e VENDAS separados
  - Trades individuais (entrada, saída, PnL, motivo)
  - Oportunidades perdidas (shadow signals)
  - Diagnóstico de assertividade
  - Consolidado final de 30 dias
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

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro

# Saída em arquivo UTF-8
OUTPUT_FILE = "backtest_30dias_resultado.txt"
_arquivo_saida = open(OUTPUT_FILE, "w", encoding="utf-8")
_stdout_original = sys.stdout
sys.stdout = _arquivo_saida

logging.disable(logging.CRITICAL)

SYMBOL      = "WIN$N"
INITIAL_BAL = 3000.0

# 30 dias úteis anteriores a 28/02/2026 (excluindo Carnaval 16/02 e 17/02)
DIAS_ALVO = [
    # Janeiro 2026
    datetime(2026, 1, 19), datetime(2026, 1, 20), datetime(2026, 1, 21),
    datetime(2026, 1, 22), datetime(2026, 1, 23), datetime(2026, 1, 26),
    datetime(2026, 1, 27), datetime(2026, 1, 28), datetime(2026, 1, 29),
    datetime(2026, 1, 30),
    # Fevereiro 2026 (sem 16/02 e 17/02 — Carnaval B3)
    datetime(2026, 2,  2), datetime(2026, 2,  3), datetime(2026, 2,  4),
    datetime(2026, 2,  5), datetime(2026, 2,  6), datetime(2026, 2,  9),
    datetime(2026, 2, 10), datetime(2026, 2, 11), datetime(2026, 2, 12),
    datetime(2026, 2, 13), datetime(2026, 2, 18), datetime(2026, 2, 19),
    datetime(2026, 2, 20), datetime(2026, 2, 23), datetime(2026, 2, 24),
    datetime(2026, 2, 25), datetime(2026, 2, 26), datetime(2026, 2, 27),
]

SEP_DUPLO = "=" * 82
SEP_SIMPL = "-" * 82

def hdr(titulo: str) -> str:
    pad = (82 - len(titulo) - 2) // 2
    return f"\n{'=' * pad} {titulo} {'=' * pad}"

def fmt_reais(val: float) -> str:
    sinal = "+" if val >= 0 else ""
    return f"R$ {sinal}{val:,.2f}"

def pct(val: float, ref: float) -> str:
    if ref == 0: return "N/A"
    return f"{val/ref*100:+.2f}%"

async def run():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: MetaTrader 5 não conectado. Abra e logue no terminal MT5.")
        return

    locked_params = {}
    params_path = "backend/v22_locked_params.json"
    if os.path.exists(params_path):
        with open(params_path, encoding="utf-8") as f:
            locked_params = json.load(f).get("strategy_params", {})

    print(hdr("BACKTEST 30 DIAS - MINI ÍNDICE (WIN) - JAN-FEV/2026"))
    print(f"  SÍMBOLO  : {SYMBOL}")
    print(f"  CAPITAL  : R$ {INITIAL_BAL:,.2f}")
    print("  TIMEFRAME: M1  |  ESTRATÉGIA: SOTA V27 Golden Params")
    print("  DIAS     : 19/01 a 27/02/2026 (30 dias úteis, excl. Carnaval)")
    print(f"  PARAMS   : flux={locked_params.get('flux_imbalance_threshold','?')}, "
          f"tp={locked_params.get('tp_dist','?')}pts, sl={locked_params.get('sl_dist','?')}pts")
    print(SEP_DUPLO)

    # Acumuladores globais
    total_pnl        = 0.0
    total_buy_pnl    = 0.0
    total_sell_pnl   = 0.0
    total_trades     = 0
    total_buy        = 0
    total_sell       = 0
    total_candidates = 0
    total_blocked_flux = 0
    dias_positivos   = 0
    resumo_dias      = []

    for dia in DIAS_ALVO:
        bt = BacktestPro(
            symbol=SYMBOL,
            initial_balance=INITIAL_BAL,
            **locked_params
        )

        date_from = datetime(dia.year, dia.month, dia.day, 9, 0)
        date_to   = datetime(dia.year, dia.month, dia.day, 17, 30)

        data = bridge.get_market_data_range(
            SYMBOL, mt5.TIMEFRAME_M1, date_from, date_to
        )

        if data is None or data.empty or len(data) < 30:
            print(f"\n⚠️  {dia.strftime('%d/%m/%Y')}: Sem dados suficientes (pregão suspenso ou feriado). Pulando.")
            continue

        # ----- SHADOW SIGNALS -----
        shadow_signals = []
        candidates     = 0
        blocked_flux   = 0

        for i in range(20, len(data) - 1):
            seg = data.iloc[:i+1]
            row = seg.iloc[-1]
            hora = pd.Timestamp(row['time']).hour if 'time' in row else 9
            if hora < 9 or hora >= 17:
                continue

            close_s = seg['close']
            if len(close_s) < 20:
                continue

            try:
                import numpy as np
                rsi_p   = int(locked_params.get('rsi_period', 9))
                delta   = close_s.diff()
                gain    = delta.where(delta > 0, 0).rolling(rsi_p).mean()
                loss    = (-delta.where(delta < 0, 0)).rolling(rsi_p).mean()
                rs      = gain / loss.replace(0, 1e-9)
                rsi_val = float((100 - 100 / (1 + rs)).iloc[-1])

                bb_dev  = float(locked_params.get('bb_dev', 2.0))
                sma20   = close_s.rolling(20).mean().iloc[-1]
                std20   = close_s.rolling(20).std().iloc[-1]
                bb_up   = sma20 + bb_dev * std20
                bb_lo   = sma20 - bb_dev * std20
                price   = float(row['close'])
                vol_ok  = float(row.get('tick_volume', 1)) > float(seg['tick_volume'].rolling(20).mean().iloc[-1]) * float(locked_params.get('vol_spike_mult', 1.0))

                side = None
                if rsi_val < 35 and price < bb_lo and vol_ok:
                    side = "buy"
                elif rsi_val > 65 and price > bb_up and vol_ok:
                    side = "sell"

                if side:
                    candidates += 1
                    # Simula filtro de flux
                    flux_threshold = float(locked_params.get('flux_imbalance_threshold', 1.05))
                    bid_proxy = float(seg['tick_volume'].iloc[-5:].mean())
                    ask_proxy = float(seg['tick_volume'].iloc[-10:-5].mean()) if len(seg) >= 10 else bid_proxy
                    flux_ratio = (bid_proxy / (ask_proxy + 1e-9)) if side == "buy" else (ask_proxy / (bid_proxy + 1e-9))
                    if flux_ratio < flux_threshold:
                        blocked_flux += 1
                        shadow_signals.append({"time": row.get('time', '?'), "side": side, "reason": "flux"})
            except Exception:
                continue

        # ----- EXECUTA BACKTEST (injeta DataFrame e chama run() padrão) -----
        bt.data = data.copy()
        await bt.run()

        trades       = bt.trades
        n_buy        = sum(1 for t in trades if t['side'] == 'buy')
        n_sell       = sum(1 for t in trades if t['side'] == 'sell')
        pnl_buy      = sum(t['pnl_fin'] for t in trades if t['side'] == 'buy')
        pnl_sell     = sum(t['pnl_fin'] for t in trades if t['side'] == 'sell')
        pnl_dia      = pnl_buy + pnl_sell
        n_trades     = len(trades)
        wins         = sum(1 for t in trades if t['pnl_fin'] > 0)
        wr           = (wins / n_trades * 100) if n_trades > 0 else 0.0
        gross_win    = sum(t['pnl_fin'] for t in trades if t['pnl_fin'] > 0)
        gross_loss   = abs(sum(t['pnl_fin'] for t in trades if t['pnl_fin'] < 0))
        pf           = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
        equity_arr   = bt.equity_curve if hasattr(bt, 'equity_curve') and bt.equity_curve else [INITIAL_BAL]
        dd_pct       = ((max(equity_arr) - min(equity_arr)) / max(equity_arr) * 100) if len(equity_arr) > 1 else 0.0

        emoji = "📈" if pnl_dia >= 0 else "📉"

        dia_str = dia.strftime('%d/%m/%Y')
        print(f"\n{hdr('DIA: ' + dia_str)}")
        print(f"  Candles M1 carregados: {len(data)}")
        print("  Janela operacional   : 09:15 - 17:15")
        print()
        print("  RESULTADO GERAL")
        print(f"  ├── PNL Total          :  {fmt_reais(pnl_dia):>15}   {pct(pnl_dia, INITIAL_BAL)}")
        print(f"  ├── Total de Trades    : {n_trades:>5}")
        print(f"  ├── Win Rate           : {wr:>5.1f}%")
        print(f"  ├── Profit Factor      : {pf:>6.2f}")
        print(f"  └── Max Drawdown       : {dd_pct:>5.2f}%")

        # Tabela BUY
        print("\n  ── OPERAÇÕES COMPRADAS (BUY) ──────────────────────")
        buys = [t for t in trades if t['side'] == 'buy']
        buy_wins = sum(1 for t in buys if t['pnl_fin'] > 0)
        buy_losses = len(buys) - buy_wins
        print(f"  Qtd: {n_buy}  |  Ganhos: {buy_wins}  |  Perdas: {buy_losses}  |  PNL: {fmt_reais(pnl_buy)}")
        if buys:
            print(f"  {'Entrada':<22} {'Saída':<22} {'Preço E':>9} {'Preço S':>9} {'Pts':>7} {'PNL':>13}  Motivo")
            print(f"  {'-'*95}")
            for t in buys:
                pts  = t.get('pnl_pts', 0)
                icon = "✅" if t['pnl_fin'] > 0 else "❌"
                ei   = str(t.get('entry_time', '?'))[:19]
                eo   = str(t.get('exit_time',  '?'))[:19]
                print(f"  {icon} {ei}   {eo}  {t.get('entry_price',0):>9.0f}  {t.get('exit_price',0):>9.0f}  {pts:>+7.0f}  {fmt_reais(t['pnl_fin']):>12}  {t.get('reason','')}")

        # Tabela SELL
        print("\n  ── OPERAÇÕES VENDIDAS (SELL) ───────────────────────")
        sells = [t for t in trades if t['side'] == 'sell']
        sell_wins = sum(1 for t in sells if t['pnl_fin'] > 0)
        sell_losses = len(sells) - sell_wins
        print(f"  Qtd: {n_sell}  |  Ganhos: {sell_wins}  |  Perdas: {sell_losses}  |  PNL: {fmt_reais(pnl_sell)}")
        if sells:
            print(f"  {'Entrada':<22} {'Saída':<22} {'Preço E':>9} {'Preço S':>9} {'Pts':>7} {'PNL':>13}  Motivo")
            print(f"  {'-'*95}")
            for t in sells:
                pts  = t.get('pnl_pts', 0)
                icon = "✅" if t['pnl_fin'] > 0 else "❌"
                ei   = str(t.get('entry_time', '?'))[:19]
                eo   = str(t.get('exit_time',  '?'))[:19]
                print(f"  {icon} {ei}   {eo}  {t.get('entry_price',0):>9.0f}  {t.get('exit_price',0):>9.0f}  {pts:>+7.0f}  {fmt_reais(t['pnl_fin']):>12}  {t.get('reason','')}")

        # Oportunidades
        print("\n  ── OPORTUNIDADES PERDIDAS (SHADOW SIGNALS) ─────────")
        print(f"  Candidatos V22 detectados : {candidates}")
        print(f"  Bloqueados pelo filtro flux: {blocked_flux}")
        print(f"  Aproveitamento            : {n_trades}/{candidates} ({n_trades/candidates*100:.1f}%)" if candidates > 0 else "  Aproveitamento: N/A")
        print(f"  {SEP_SIMPL}")

        # Acumula
        total_pnl        += pnl_dia
        total_buy_pnl    += pnl_buy
        total_sell_pnl   += pnl_sell
        total_trades     += n_trades
        total_buy        += n_buy
        total_sell       += n_sell
        total_candidates += candidates
        total_blocked_flux += blocked_flux
        if pnl_dia >= 0:
            dias_positivos += 1

        resumo_dias.append({
            'data': dia.strftime('%d/%m/%Y'),
            'trades': n_trades,
            'buy': n_buy,
            'sell': n_sell,
            'pnl_buy': pnl_buy,
            'pnl_sell': pnl_sell,
            'pnl_total': pnl_dia,
            'wr': wr,
            'pf': pf,
            'dd': dd_pct,
            'emoji': emoji
        })

    # ----- CONSOLIDADO FINAL -----
    print(f"\n{hdr('CONSOLIDADO FINAL - 30 DIAS - JAN-FEV 2026')}")
    print()
    print("  RESULTADO FINANCEIRO")
    print(f"  ├── PNL Consolidado       : {fmt_reais(total_pnl):>20}   {pct(total_pnl, INITIAL_BAL)}")
    print(f"  ├── PNL de Compras        : {fmt_reais(total_buy_pnl):>20}")
    print(f"  ├── PNL de Vendas         : {fmt_reais(total_sell_pnl):>20}")
    print(f"  ├── Capital Final Estimado: {fmt_reais(INITIAL_BAL + total_pnl):>20}")

    if resumo_dias:
        melhor = max(resumo_dias, key=lambda x: x['pnl_total'])
        pior   = min(resumo_dias, key=lambda x: x['pnl_total'])
        wrs    = [d['wr'] for d in resumo_dias if d['trades'] > 0]
        pfs    = [d['pf'] for d in resumo_dias if d['pf'] != float('inf')]
        dds    = [d['dd'] for d in resumo_dias]

        print("  │")
        print(f"  ├── Dias Analisados       : {len(resumo_dias)}")
        print(f"  ├── Dias Positivos        : {dias_positivos}/{len(resumo_dias)}")
        print(f"  ├── Melhor Dia            : {melhor['data']} → {fmt_reais(melhor['pnl_total'])}")
        print(f"  └── Pior Dia              : {pior['data']} → {fmt_reais(pior['pnl_total'])}")
        print()
        print("  OPERAÇÕES")
        print(f"  ├── Total de Trades       : {total_trades}")
        print(f"  ├─── Compras (BUY)        : {total_buy}")
        print(f"  ├─── Vendas  (SELL)       : {total_sell}")
        print(f"  ├── Win Rate Médio        : {sum(wrs)/len(wrs):.1f}%" if wrs else "  ├── Win Rate Médio: N/A")
        print(f"  ├── Profit Factor Médio   : {sum(pfs)/len(pfs):.2f}" if pfs else "  ├── Profit Factor: N/A")
        print(f"  └── Max Drawdown (pior dia): {max(dds):.2f}%" if dds else "  └── Max Drawdown: N/A")
        print()
        print("  OPORTUNIDADES PERDIDAS")
        print(f"  ├── Candidatos detectados : {total_candidates}")
        print(f"  ├── Bloqueados (flux)      : {total_blocked_flux}")
        print(f"  └── Taxa aproveitamento   : {total_trades}/{total_candidates} ({total_trades/total_candidates*100:.1f}%)" if total_candidates > 0 else "  └── Taxa aproveitamento: N/A")

    # Tabela resumo
    print(f"\n{hdr('TABELA RESUMO POR DIA')}")
    print()
    print(f"  {'DATA':<14} {'TRADES':>6} {'BUY':>5} {'SELL':>5} {'PNL COMPRA':>12} {'PNL VENDA':>12} {'PNL TOTAL':>12} {'WR%':>6} {'PF':>6}")
    print(f"  {'-'*88}")
    for d in resumo_dias:
        pf_str = f"{d['pf']:.2f}" if d['pf'] != float('inf') else "∞"
        print(f"  {d['emoji']} {d['data']:<12} {d['trades']:>6} {d['buy']:>5} {d['sell']:>5} "
              f"{fmt_reais(d['pnl_buy']):>12} {fmt_reais(d['pnl_sell']):>12} "
              f"{fmt_reais(d['pnl_total']):>12} {d['wr']:>5.1f}% {pf_str:>6}")
    if resumo_dias:
        print(f"  {'─'*88}")
        print(f"  {'TOTAL':<14} {total_trades:>6} {total_buy:>5} {total_sell:>5} "
              f"{fmt_reais(total_buy_pnl):>12} {fmt_reais(total_sell_pnl):>12} "
              f"{fmt_reais(total_pnl):>12}")

    # Sugestões
    if resumo_dias:
        wrs_list = [d['wr'] for d in resumo_dias if d['trades'] > 0]
        avg_wr = sum(wrs_list) / len(wrs_list) if wrs_list else 0
        pfs_list = [d['pf'] for d in resumo_dias if d['pf'] != float('inf')]
        avg_pf = sum(pfs_list) / len(pfs_list) if pfs_list else 0

        print(f"\n{hdr('ANALISE ESTRATEGICA - SUGESTOES')}")
        print()
        if avg_wr > 70:
            print(f"  [POSITIVO] Win Rate médio {avg_wr:.1f}% acima de 70%: sistema com alta assertividade.")
        if avg_pf > 2.0:
            print(f"  [POSITIVO] Profit Factor médio {avg_pf:.2f}: retorno muito consistente.")
        if total_blocked_flux > 0:
            flux_pct = total_blocked_flux / total_candidates * 100 if total_candidates > 0 else 0
            print(f"  [ANALISE] {total_blocked_flux} sinais bloqueados pelo flux ({flux_pct:.1f}% dos candidatos).")
            if flux_pct > 5:
                print("           → Avaliar redução de flux_threshold para 0.95 (requer validação).")
        dias_neg = [d for d in resumo_dias if d['pnl_total'] < 0]
        if dias_neg:
            print(f"  [ALERTA] {len(dias_neg)} dia(s) negativo(s): {', '.join(d['data'] for d in dias_neg)}")
            print("           → Analisar padrão de mercado nesses dias para regras de veto.")
        else:
            print(f"  [EXCELENTE] Todos os {len(resumo_dias)} dias analisados foram positivos.")

    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    print(f"\n{SEP_DUPLO}")
    print(f"  Análise concluída em: {now}")
    print(f"{SEP_DUPLO}\n")

    _arquivo_saida.flush()
    sys.stdout = _stdout_original
    print(f"[OK] Resultado salvo em: {OUTPUT_FILE}")

asyncio.run(run())
