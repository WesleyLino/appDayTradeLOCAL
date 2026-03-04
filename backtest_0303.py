"""
Backtest Alta Performance — 03/03/2026
======================================================
Analisa o potencial máximo de COMPRA e VENDA no dia de hoje,
identificando oportunidades perdidas e calibragem ótima.
Não altera ajustes mais lucrativos das versões anteriores.
"""
import asyncio
import sys
import os
import warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, '.')

TARGET_DATE   = '2026-03-03'
LABEL         = '03/03'
SALDO_INICIAL = 3000.0

# =====================================================================
# MODOS DE CALIBRAGEM — Comparados em paralelo para encontrar o melhor
# =====================================================================
MODOS = {
    "v52.4 ATUAL (A-H)": {
        'confidence_threshold': 0.70,
        'start_time': "09:00",
        'rsi_buy_level': 32,
        'rsi_sell_level': 68,
    },
    "AGRESSIVO (max trades)": {
        'confidence_threshold': 0.60,
        'start_time': "09:00",
        'rsi_buy_level': 35,
        'rsi_sell_level': 65,
    },
    "SNIPER (max assertividade)": {
        'confidence_threshold': 0.75,
        'start_time': "09:00",
        'rsi_buy_level': 30,
        'rsi_sell_level': 70,
    },
}


async def rodar_backtest(label_modo, modo_params, df):
    """Roda o backtest com os parâmetros do modo especificado."""
    from backend.backtest_pro import BacktestPro

    bt = BacktestPro(symbol='WIN$', initial_balance=SALDO_INICIAL, **modo_params)
    bt.data = df.copy()
    await bt.run()

    trades = bt.trades
    total  = len(trades)
    # Campo correto: 'pnl_fin' conforme BacktestPro._close_trade (linha 894)
    wins   = sum(1 for t in trades if t.get('pnl_fin', 0) > 0)
    sells  = sum(1 for t in trades if t.get('side') == 'sell')
    buys   = sum(1 for t in trades if t.get('side') == 'buy')
    pnl    = bt.balance - bt.initial_balance
    wr     = (wins / total * 100) if total > 0 else 0.0

    # Análise de saída por tipo (campo 'reason')
    tps    = sum(1 for t in trades if t.get('reason', '') in ('TP', 'TP_DECAY'))
    sls    = sum(1 for t in trades if t.get('reason', '') == 'SL')
    forced = sum(1 for t in trades if t.get('reason', '') in ('ALPHA_DECAY', 'FORCE_CLOSE'))

    # Análise de shadow signals (oportunidades perdidas)
    vetos      = bt.shadow_signals.get('veto_reasons', {})
    candidatos = bt.shadow_signals.get('v22_candidates', 0)
    vetos_top  = sorted(vetos.items(), key=lambda x: x[1], reverse=True)[:5]

    # PnL por direção
    pnl_buy  = sum(t.get('pnl_fin', 0) for t in trades if t.get('side') == 'buy')
    pnl_sell = sum(t.get('pnl_fin', 0) for t in trades if t.get('side') == 'sell')

    # Extremos
    pnls_list = [t.get('pnl_fin', 0) for t in trades]
    melhor = max(pnls_list) if pnls_list else 0
    pior   = min(pnls_list) if pnls_list else 0

    print(f"\n{'─'*60}")
    print(f"  🔬 MODO: {label_modo}")
    print(f"{'─'*60}")
    print(f"  PnL Total    : R${pnl:+.2f}  (C: R${pnl_buy:+.2f} | V: R${pnl_sell:+.2f})")
    print(f"  Trades       : {total:2d}  (Compras: {buys} | Vendas: {sells})")
    print(f"  Win Rate     : {wr:.1f}%")
    print(f"  Saídas       : TPs={tps} | SLs={sls} | Forçados={forced}")
    print(f"  Melhor Trade : R${melhor:+.2f} | Pior Trade: R${pior:+.2f}")

    print(f"\n  📍 SHADOW SIGNALS (Oportunidades Perdidas):")
    print(f"     Candidatos v22   : {candidatos}")
    if vetos_top:
        for k, v in vetos_top:
            print(f"     {k:<30}: {v}")
    else:
        print("     Nenhum veto registrado")

    if trades:
        print(f"\n  📋 TRADES EXECUTADOS ({total}):")
        for i, t in enumerate(trades, 1):
            lado   = "🟢 C" if t.get('side') == 'buy' else "🔴 V"
            hora_e = str(t.get('entry_time', '?'))[-8:-3]
            hora_s = str(t.get('exit_time',  '?'))[-8:-3]
            entry  = t.get('entry_price', 0)
            exit_p = t.get('exit_price',  0)
            reason = t.get('reason', '?')
            pnl_t  = t.get('pnl_fin', 0)
            pnl_p  = t.get('pnl_pts', 0)
            lots   = t.get('lots', '?')
            modo_e = t.get('execution_mode', 'V22')
            print(f"    [{i:02d}] {lado} {hora_e}→{hora_s} | {entry:.0f}→{exit_p:.0f} ({pnl_p:+.0f}pts) | {reason:12} | {lots}x | R${pnl_t:+.2f} | [{modo_e}]")

    return {
        'modo':       label_modo,
        'pnl':        pnl,
        'pnl_buy':    pnl_buy,
        'pnl_sell':   pnl_sell,
        'trades':     total,
        'buys':       buys,
        'sells':      sells,
        'wr':         wr,
        'tps':        tps,
        'sls':        sls,
        'candidatos': candidatos,
    }


async def main():
    try:
        import MetaTrader5 as mt5
        import pandas as pd
        from datetime import datetime

        print("=" * 62)
        print(f"  BACKTEST ALTA PERFORMANCE — 03/03/2026 (v52.4+)")
        print(f"  Saldo Inicial: R${SALDO_INICIAL:.2f}")
        print("=" * 62)

        if not mt5.initialize():
            print("❌ ERRO: MT5 não inicializou. Terminal deve estar aberto.")
            return

        date      = datetime.strptime(TARGET_DATE, '%Y-%m-%d')
        date_from = datetime(date.year, date.month, date.day, 9, 0, 0)
        date_to   = datetime(date.year, date.month, date.day, 17, 30, 0)

        print(f"\n📡 Coletando dados: {LABEL} ({date_from} → {date_to})")
        rates = mt5.copy_rates_range('WIN$', mt5.TIMEFRAME_M1, date_from, date_to)
        mt5.shutdown()

        if rates is None or len(rates) == 0:
            print(f"❌ SKIP: sem dados MT5 para {TARGET_DATE}")
            print("   → Mercado pode ter estado fechado (feriado/sábado/domingo).")
            return

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        print(f"✅ MT5: {len(df)} candles M1 carregados")
        print(f"   Abertura: {df.index[0]} | Fechamento: {df.index[-1]}")
        print(f"   Mín: {df['low'].min():.0f} | Máx: {df['high'].max():.0f} | Δ: {df['high'].max() - df['low'].min():.0f}pts")
        print(f"   Variação (%): {((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100):+.2f}%")

        # Roda todos os modos
        resultados = []
        for nome, params in MODOS.items():
            r = await rodar_backtest(nome, params, df)
            resultados.append(r)

        # Tabela comparativa
        print(f"\n{'='*62}")
        print(f"  📊 COMPARATIVO DE CALIBRAGEM — {LABEL}")
        print(f"{'='*62}")
        print(f"  {'Modo':<30} {'PnL':>9} {'T':>4} {'WR':>6} {'C':>3} {'V':>3} {'TP':>3} {'SL':>3}")
        print(f"  {'─'*60}")
        for r in resultados:
            destaque = "✅" if r['pnl'] == max(x['pnl'] for x in resultados) else "  "
            print(f"  {destaque} {r['modo']:<28} R${r['pnl']:>+.2f} {r['trades']:>4} {r['wr']:>5.1f}% {r['buys']:>3} {r['sells']:>3} {r['tps']:>3} {r['sls']:>3}")

        melhor = max(resultados, key=lambda x: x['pnl'])
        pior_r  = min(resultados, key=lambda x: x['pnl'])

        print(f"\n  🏆 Configuração MAIS LUCRATIVA: {melhor['modo']}")
        print(f"     PnL: R${melhor['pnl']:+.2f} | Trades: {melhor['trades']} | WR: {melhor['wr']:.1f}%")
        print(f"     Compras: R${melhor['pnl_buy']:+.2f} | Vendas: R${melhor['pnl_sell']:+.2f}")

        print(f"\n  📈 ACUMULADO HISTÓRICO:")
        print(f"     19/02–27/02 (6 dias): R$+540,40")
        print(f"     03/03 melhor modo   : R${melhor['pnl']:+.2f}")
        print(f"     TOTAL 7 DIAS        : R${540.40 + melhor['pnl']:+.2f}")
        print(f"     Média/Dia (7 dias)  : R${(540.40 + melhor['pnl']) / 7:+.2f}")
        print(f"{'='*62}\n")

    except Exception as e:
        import traceback
        print(f"❌ ERRO GERAL: {e}\n{traceback.format_exc()}")


if __name__ == '__main__':
    asyncio.run(main())
