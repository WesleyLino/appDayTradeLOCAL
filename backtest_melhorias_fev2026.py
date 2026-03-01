"""
Backtest de Validação das Melhorias — Fev/2026
Compara o baseline (backtest original) com as 3 melhorias implementadas:
  1. Trailing Stop Assimétrico SELL (40/30/15pts em vez de 70/50/20pts)
  2. Scaling Out (saída parcial em +50pts, 1 contrato)
  3. Quarter-Kelly (redução de lote para 0.25 após 2 perdas, sem cooldown de 15min)
"""

import sys
import os
import asyncio

# Redireciona output para UTF-8
sys.stdout = open("backtest_melhorias_fev2026.txt", "w", encoding="utf-8")
sys.stderr = sys.stdout

import logging
logging.disable(logging.CRITICAL)

import warnings
warnings.filterwarnings("ignore")

os.environ.setdefault("RUNNING_BACKTEST", "1")

from dotenv import load_dotenv
load_dotenv()

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── V22 Golden Params ──────────────────────────────────────────────────
V22_PARAMS = {
    "rsi_period": 9,
    "tp_dist": 400,
    "sl_dist": 150,
    "vol_spike_mult": 1.0,
    "flux_imbalance_threshold": 1.2,
    "cooldown_minutes": 10,
    "use_ai_core": False,
}

# ── Parâmetros das Melhorias ───────────────────────────────────────────
# TRAILING BUY (inalterado)
TRAILING_TRIGGER_BUY  = 70.0
TRAILING_LOCK_BUY     = 50.0
TRAILING_STEP_BUY     = 20.0
# TRAILING SELL (assimétrico — mais rápido)
TRAILING_TRIGGER_SELL = 40.0
TRAILING_LOCK_SELL    = 30.0
TRAILING_STEP_SELL    = 15.0
# SCALING OUT
PARTIAL_PROFIT_PTS    = 50.0
PARTIAL_LOTS          = 1.0
# QUARTER-KELLY
KELLY_REDUCTION       = 0.25   # Fator após 2 perdas consecutivas
KELLY_WIN_COUNT       = 2      # Acertos necessários para restaurar

INITIAL_CAPITAL = 3000.0
POINT_VALUE     = 0.20          # R$ por ponto no mini índice
DIAS = [
    datetime(2026, 2, 19),
    datetime(2026, 2, 20),
    datetime(2026, 2, 23),
    datetime(2026, 2, 24),
    datetime(2026, 2, 25),
    datetime(2026, 2, 26),
    datetime(2026, 2, 27),
]


def calculate_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def simular_dia(day: datetime, df: pd.DataFrame, capital: float,
                consecutive_losses: int, wins_kelly: int, kelly_mult: float):
    """
    Simula um dia de trading com as novas regras de melhoria.
    Retorna: (resultado_dict, consecutive_losses_final, wins_kelly_final, kelly_mult_final)
    """
    rsi_period     = V22_PARAMS["rsi_period"]
    tp_dist        = V22_PARAMS["tp_dist"]
    sl_dist        = V22_PARAMS["sl_dist"]
    vol_spike_mult = V22_PARAMS["vol_spike_mult"]
    cooldown_min   = V22_PARAMS["cooldown_minutes"]

    df = df.copy()
    df['rsi']     = calculate_rsi(df['close'], rsi_period)
    df['vol_sma'] = df['tick_volume'].rolling(20).mean()

    # Filtro de janela operacional
    df['hour']   = df.index.hour
    df['minute'] = df.index.minute
    op_start = df.index >= df.index[0].replace(hour=9,  minute=15, second=0)
    op_end   = df.index <= df.index[0].replace(hour=17, minute=15, second=0)
    df = df[op_start & op_end]

    trades         = []
    shadow_signals = {"cooldown": 0, "v22_candidates": 0}
    last_trade_time = None
    position       = None   # {"side", "entry_price", "entry_time", "sl", "tp", "lots", "trailing_sl", "partial_done"}

    rows = list(df.iterrows())
    for idx, (ts, row) in enumerate(rows):
        if idx < max(rsi_period + 5, 20):
            continue

        rsi         = row['rsi']
        curr_vol    = row['tick_volume']
        avg_vol     = row['vol_sma']
        close       = row['close']

        # ── Gerenciar posição aberta ───────────────────────────────────
        if position is not None:
            side        = position['side']
            entry       = position['entry_price']
            lots        = position['lots']
            sl          = position['sl']
            tp          = position['tp']
            trail_sl    = position['trailing_sl']
            partial_done = position.get('partial_done', False)

            if side == 'buy':
                profit_pts = close - entry
            else:
                profit_pts = entry - close

            realized_partial_pnl = position.get('realized_partial_pnl', 0.0)
            remaining_lots       = position.get('remaining_lots', lots)

            # ── Scaling Out — SELL ────────────────────────────────────
            if (side == 'sell' and not partial_done
                    and profit_pts >= PARTIAL_PROFIT_PTS
                    and remaining_lots > PARTIAL_LOTS):
                partial_pnl = PARTIAL_PROFIT_PTS * PARTIAL_LOTS * POINT_VALUE
                position['realized_partial_pnl'] = partial_pnl
                position['remaining_lots']       = remaining_lots - PARTIAL_LOTS
                position['partial_done']         = True

            # ── Trailing Stop Assimétrico (SELL) ──────────────────────
            if side == 'sell' and profit_pts >= TRAILING_TRIGGER_SELL:
                new_trail = close + (TRAILING_TRIGGER_SELL - TRAILING_LOCK_SELL)
                if new_trail < trail_sl - TRAILING_STEP_SELL:
                    position['trailing_sl'] = new_trail
                    trail_sl = new_trail

            # ── Trailing Stop BUY (inalterado) ────────────────────────
            elif side == 'buy' and profit_pts >= TRAILING_TRIGGER_BUY:
                new_trail = close - (TRAILING_TRIGGER_BUY - TRAILING_LOCK_BUY)
                if new_trail > trail_sl + TRAILING_STEP_BUY:
                    position['trailing_sl'] = new_trail
                    trail_sl = new_trail

            # ── Verificar saída (SL/TP/Trail) ─────────────────────────
            closed    = False
            exit_pts  = None
            exit_reason = "TP"

            if side == 'buy':
                if close <= max(sl, trail_sl):
                    exit_pts    = max(sl, trail_sl) - entry
                    exit_reason = "SL/Trail"
                    closed      = True
                elif close >= tp:
                    exit_pts    = tp - entry
                    closed      = True
            else:
                if close >= min(sl, trail_sl):
                    exit_pts    = entry - min(sl, trail_sl)
                    exit_reason = "SL/Trail"
                    closed      = True
                elif close <= tp:
                    exit_pts    = entry - tp
                    closed      = True

            # Time exit: 15 candles máximo
            if not closed:
                elapsed_candles = idx - position.get('entry_candle_idx', idx)
                if elapsed_candles >= 15:
                    exit_pts    = profit_pts
                    exit_reason = "TimeExit"
                    closed      = True

            if closed:
                remaining_lots  = position.get('remaining_lots', lots)
                partial_pnl     = position.get('realized_partial_pnl', 0.0)
                final_pnl       = (exit_pts * remaining_lots * POINT_VALUE) + partial_pnl
                won             = (exit_pts > 0) if exit_pts is not None else False

                trades.append({
                    "side":       side,
                    "entry_time": position['entry_time'],
                    "exit_time":  ts,
                    "entry":      entry,
                    "exit":       close if exit_reason != "SL/Trail" else (max(sl, trail_sl) if side == 'buy' else min(sl, trail_sl)),
                    "pts":        round(exit_pts, 1) if exit_pts else 0,
                    "pnl":        round(final_pnl, 2),
                    "won":        won,
                    "reason":     exit_reason,
                    "had_partial": position.get('partial_done', False),
                })

                # Quarter-Kelly: atualizar estado
                if not won:
                    consecutive_losses += 1
                    wins_kelly          = 0
                    if consecutive_losses >= 2:
                        kelly_mult = KELLY_REDUCTION
                else:
                    consecutive_losses = 0
                    wins_kelly        += 1
                    if wins_kelly >= KELLY_WIN_COUNT and kelly_mult < 1.0:
                        kelly_mult = 1.0

                last_trade_time = ts
                position = None
            continue  # Skip entrada enquanto em posição

        # ── Geração de Sinal (V22) ──────────────────────────────────
        if pd.isna(rsi) or pd.isna(avg_vol) or avg_vol == 0:
            continue

        buy_cond  = rsi < 30 and curr_vol > (avg_vol * vol_spike_mult)
        sell_cond = rsi > 70 and curr_vol > (avg_vol * vol_spike_mult)

        if not (buy_cond or sell_cond):
            continue

        shadow_signals['v22_candidates'] += 1

        # Cooldown: Quarter-Kelly não bloqueia mais — apenas reduz o lote
        if last_trade_time is not None:
            elapsed = (ts - last_trade_time).total_seconds() / 60
            if elapsed < cooldown_min:
                shadow_signals['cooldown'] += 1
                continue  # Cooldown de entrada ainda válido (garante qualidade mínima)

        # Abrir posição
        side  = 'buy'  if buy_cond  else 'sell'
        entry = close

        # Quarter-Kelly: reduz o lote base
        base_lots = 1.0 * kelly_mult
        base_lots = max(0.25, base_lots)  # mínimo de 0.25 lote

        if side == 'buy':
            sl_price   = entry - sl_dist
            tp_price   = entry + tp_dist
            trail_sl   = sl_price  # Trailing initial = SL
        else:
            sl_price   = entry + sl_dist
            tp_price   = entry - tp_dist
            trail_sl   = sl_price

        position = {
            "side":                side,
            "entry_price":         entry,
            "entry_time":          ts,
            "entry_candle_idx":    idx,
            "sl":                  sl_price,
            "tp":                  tp_price,
            "lots":                base_lots,
            "remaining_lots":      base_lots,
            "trailing_sl":         trail_sl,
            "partial_done":        False,
            "realized_partial_pnl": 0.0,
        }

    # Forçar encerramento ao fim do dia
    if position is not None:
        close_price = df.iloc[-1]['close']
        side        = position['side']
        entry       = position['entry_price']
        exit_pts    = (close_price - entry) if side == 'buy' else (entry - close_price)
        remaining   = position.get('remaining_lots', position['lots'])
        partial_pnl = position.get('realized_partial_pnl', 0.0)
        final_pnl   = (exit_pts * remaining * POINT_VALUE) + partial_pnl
        won         = exit_pts > 0
        trades.append({
            "side":       side,
            "entry_time": position['entry_time'],
            "exit_time":  df.index[-1],
            "entry":      entry,
            "exit":       close_price,
            "pts":        round(exit_pts, 1),
            "pnl":        round(final_pnl, 2),
            "won":        won,
            "reason":     "FimDia",
            "had_partial": position.get('partial_done', False),
        })

    # ── Métricas do Dia ─────────────────────────────────────────────
    if not trades:
        return {"day": day, "trades": [], "pnl": 0.0, "buy_pnl": 0.0,
                "sell_pnl": 0.0, "win_rate": 0.0, "shadow": shadow_signals}, \
               consecutive_losses, wins_kelly, kelly_mult

    total_pnl  = sum(t['pnl'] for t in trades)
    buy_pnl    = sum(t['pnl'] for t in trades if t['side'] == 'buy')
    sell_pnl   = sum(t['pnl'] for t in trades if t['side'] == 'sell')
    wins       = sum(1 for t in trades if t['won'])
    win_rate   = wins / len(trades) * 100

    return {"day": day, "trades": trades, "pnl": total_pnl,
            "buy_pnl": buy_pnl, "sell_pnl": sell_pnl,
            "win_rate": win_rate, "shadow": shadow_signals}, \
           consecutive_losses, wins_kelly, kelly_mult


def main():
    print("=" * 80)
    print("  BACKTEST DE VALIDAÇÃO DAS MELHORIAS — MINI ÍNDICE WIN · M1 · FEV/2026")
    print("  Melhorias: Trailing Assimétrico SELL | Scaling Out | Quarter-Kelly")
    print("=" * 80)
    print(f"\n  Capital Inicial : R$ {INITIAL_CAPITAL:,.2f}")
    print(f"  Trailing SELL   : {TRAILING_TRIGGER_SELL}/{TRAILING_LOCK_SELL}/{TRAILING_STEP_SELL} pts (vs 70/50/20 antes)")
    print(f"  Scaling Out     : Parcial em +{PARTIAL_PROFIT_PTS} pts ({PARTIAL_LOTS} contrato)")
    print(f"  Quarter-Kelly   : {int(KELLY_REDUCTION*100)}% do lote após 2 perdas → restaura em {KELLY_WIN_COUNT} acertos")
    print()

    if not mt5.initialize():
        print("ERRO: Falha ao inicializar MT5.")
        return

    symbol = None
    for sym in ["WINJ26", "WINM26", "WING26", "WIN$N"]:
        if mt5.symbol_info(sym):
            symbol = sym
            break

    if not symbol:
        print("ERRO: Nenhum símbolo WIN encontrado.")
        mt5.shutdown()
        return

    print(f"  Símbolo: {symbol}\n")

    resultados       = []
    consecutive_losses = 0
    wins_kelly         = 0
    kelly_mult         = 1.0
    capital            = INITIAL_CAPITAL
    total_pnl          = 0.0
    total_buy_pnl      = 0.0
    total_sell_pnl     = 0.0
    total_trades       = 0
    wr_list            = []
    total_shadow_cool  = 0
    total_v22          = 0
    partial_count      = 0

    for day in DIAS:
        start = day.replace(hour=9, minute=0, second=0)
        end   = day.replace(hour=17, minute=30, second=0)

        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
        if rates is None or len(rates) < 20:
            print(f"\n{'─'*80}")
            print(f"  DIA {day.strftime('%d/%02m/%Y')} — Sem dados disponíveis. Pulando.")
            continue

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        resultado, consecutive_losses, wins_kelly, kelly_mult = simular_dia(
            day, df, capital, consecutive_losses, wins_kelly, kelly_mult
        )

        day_pnl  = resultado['pnl']
        day_tr   = resultado['trades']
        day_wr   = resultado['win_rate']
        day_shad = resultado['shadow']

        capital    += day_pnl
        total_pnl  += day_pnl
        total_buy_pnl  += resultado['buy_pnl']
        total_sell_pnl += resultado['sell_pnl']
        total_trades   += len(day_tr)
        total_shadow_cool += day_shad['cooldown']
        total_v22         += day_shad['v22_candidates']
        if day_wr > 0:
            wr_list.append(day_wr)

        partial_count += sum(1 for t in day_tr if t.get('had_partial', False))
        resultados.append(resultado)

        # ── Relatório diário ──────────────────────────────────────────
        buy_tr   = [t for t in day_tr if t['side'] == 'buy']
        sell_tr  = [t for t in day_tr if t['side'] == 'sell']
        buy_wins = sum(1 for t in buy_tr  if t['won'])
        sel_wins = sum(1 for t in sell_tr if t['won'])
        emoji    = "📈" if day_pnl >= 0 else "📉"

        print(f"\n{'─'*80}")
        print(f"  {emoji} DIA: {day.strftime('%d/%m/%Y')}   Candles: {len(df)}")
        print()
        print(f"  RESULTADO GERAL")
        print(f"  ├── PNL Total       : R$ {day_pnl:+.2f}  ({day_pnl/INITIAL_CAPITAL*100:+.2f}%)")
        print(f"  ├── Total de Trades : {len(day_tr)}")
        print(f"  ├── Win Rate        : {day_wr:.1f}%")
        print(f"  └── Kelly Mult Atual: {kelly_mult*100:.0f}%")
        print()

        print(f"  ── COMPRAS (BUY) ——————————————————————")
        print(f"  Qtd: {len(buy_tr)} | Ganhos: {buy_wins} | Perdas: {len(buy_tr)-buy_wins} | PNL: R$ {resultado['buy_pnl']:+.2f}")
        for t in buy_tr:
            icon = "✅" if t['won'] else "❌"
            p_tag = " [PARCIAL]" if t.get('had_partial') else ""
            print(f"  {icon} {t['entry_time'].strftime('%H:%M')}→{t['exit_time'].strftime('%H:%M')}  "
                  f"E:{t['entry']:.0f}  S:{t['exit']:.0f}  {t['pts']:+.0f}pts  "
                  f"R${t['pnl']:+.2f}  {t['reason']}{p_tag}")
        print()

        print(f"  ── VENDAS (SELL) ——————————————————————")
        print(f"  Qtd: {len(sell_tr)} | Ganhos: {sel_wins} | Perdas: {len(sell_tr)-sel_wins} | PNL: R$ {resultado['sell_pnl']:+.2f}")
        for t in sell_tr:
            icon = "✅" if t['won'] else "❌"
            p_tag = " [PARCIAL]" if t.get('had_partial') else ""
            print(f"  {icon} {t['entry_time'].strftime('%H:%M')}→{t['exit_time'].strftime('%H:%M')}  "
                  f"E:{t['entry']:.0f}  S:{t['exit']:.0f}  {t['pts']:+.0f}pts  "
                  f"R${t['pnl']:+.2f}  {t['reason']}{p_tag}")
        print()

        print(f"  ── OPORTUNIDADES (SHADOW) ——————————————")
        print(f"  Candidatos V22 : {day_shad['v22_candidates']}")
        print(f"  Bloq. Cooldown : {day_shad['cooldown']}  ← Quarter-Kelly não bloqueia, só reduz lote")

    # ── Consolidado ───────────────────────────────────────────────────
    avg_wr = sum(wr_list) / len(wr_list) if wr_list else 0.0
    dias_positivos = sum(1 for r in resultados if r['pnl'] >= 0)
    melhor_dia = max(resultados, key=lambda r: r['pnl']) if resultados else None
    pior_dia   = min(resultados, key=lambda r: r['pnl']) if resultados else None

    print(f"\n{'='*80}")
    print(f"  CONSOLIDADO FINAL — 7 DIAS — FEV/2026 (COM MELHORIAS)")
    print(f"{'='*80}")
    print()
    print(f"  RESULTADO FINANCEIRO")
    print(f"  ├── PNL Consolidado       : R$ {total_pnl:+.2f}  ({total_pnl/INITIAL_CAPITAL*100:+.2f}%)")
    print(f"  ├── PNL de Compras        : R$ {total_buy_pnl:+.2f}")
    print(f"  ├── PNL de Vendas         : R$ {total_sell_pnl:+.2f}")
    print(f"  ├── Capital Final Estimado: R$ {INITIAL_CAPITAL + total_pnl:,.2f}")
    print(f"  ├── Saídas Parciais (SELL): {partial_count} operações com Scaling Out")
    print(f"  ├── Dias Positivos        : {dias_positivos}/{len(resultados)}")
    if melhor_dia:
        print(f"  ├── Melhor Dia            : {melhor_dia['day'].strftime('%d/%m/%Y')} → R$ {melhor_dia['pnl']:+.2f}")
    if pior_dia:
        print(f"  └── Pior Dia              : {pior_dia['day'].strftime('%d/%m/%Y')} → R$ {pior_dia['pnl']:+.2f}")
    print()
    print(f"  OPERAÇÕES")
    print(f"  ├── Total de Trades       : {total_trades}")
    print(f"  ├── Win Rate Médio        : {avg_wr:.1f}%")
    print(f"  ├── Cooldown Bloqueios    : {total_shadow_cool}  (vs ~82 no baseline)")
    print(f"  └── Taxa Aproveit. V22    : {(total_trades/total_v22*100):.1f}%  (vs 36.6% no baseline)" if total_v22 else "")
    print()
    print(f"{'='*80}")
    print(f"  COMPARATIVO COM BASELINE (sem melhorias)")
    print(f"{'='*80}")
    print()
    print(f"  Métrica              | Baseline     | Com Melhorias")
    print(f"  ---------------------|--------------|-------------------")
    print(f"  PNL Total            | R$ +395,70   | R$ {total_pnl:+.2f}")
    print(f"  Win Rate Médio       | 63,9%        | {avg_wr:.1f}%")
    print(f"  PNL Vendas           | R$ +74,55    | R$ {total_sell_pnl:+.2f}")
    print(f"  Dias Positivos       | 6/7          | {dias_positivos}/{len(resultados)}")
    print(f"  Cooldown Bloqueios   | ~82          | {total_shadow_cool}")
    print()
    print(f"  Análise concluída em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*80}")

    mt5.shutdown()

main()
