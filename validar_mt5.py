"""
Backtest com dados MT5 históricos por data — v52.2
Usa copy_rates_range para buscar dados em datas específicas (com MT5 ativo).
"""
import asyncio
import sys
import os
import warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, '.')

DIAS = [
    ('19/02', '2026-02-19'),
    ('23/02', '2026-02-23'),
    ('24/02', '2026-02-24'),
    ('25/02', '2026-02-25'),
    ('26/02', '2026-02-26'),
    ('27/02', '2026-02-27'),
]

async def rodar_dia_mt5(label, data_str):
    try:
        import MetaTrader5 as mt5
        import pandas as pd
        from datetime import datetime
        from backend.backtest_pro import BacktestPro

        # Conecta no MT5
        if not mt5.initialize():
            sys.stdout.write(f"[{label}] ERRO: MT5 não inicializou\n\n")
            return None

        date = datetime.strptime(data_str, '%Y-%m-%d')
        date_from = datetime(date.year, date.month, date.day, 9, 0, 0)
        date_to   = datetime(date.year, date.month, date.day, 17, 30, 0)

        rates = mt5.copy_rates_range('WIN$', mt5.TIMEFRAME_M1, date_from, date_to)
        mt5.shutdown()

        if rates is None or len(rates) == 0:
            sys.stdout.write(f"[{label}] SKIP: sem dados MT5 para {data_str}\n\n")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        sys.stdout.write(f"[{label}] MT5: {len(df)} candles carregados\n")
        sys.stdout.flush()

        bt = BacktestPro(symbol='WIN$', initial_balance=3000.0)
        bt.data = df  # Injeta dados diretamente
        await bt.run()

        trades = bt.trades
        total = len(trades)
        wins  = sum(1 for t in trades if t.get('pnl', 0) > 0)
        sells = sum(1 for t in trades if t.get('side') == 'sell')
        buys  = sum(1 for t in trades if t.get('side') == 'buy')
        pnl   = bt.balance - bt.initial_balance
        wr    = (wins / total * 100) if total > 0 else 0.0

        vetos = bt.shadow_signals.get('veto_reasons', {})
        vetos_top = sorted(vetos.items(), key=lambda x: x[1], reverse=True)[:3]
        vetos_str = " | ".join(f"{k}={v}" for k, v in vetos_top) if vetos_top else "nenhum"

        h1_byp = sum(1 for t in trades if 'H1 BYPASS' in str(t.get('reason', '')))

        sys.stdout.write(f"[{label}] PnL: R${pnl:+.2f} | Trades: {total} (C:{buys}/V:{sells}) | WR: {wr:.1f}%\n")
        sys.stdout.write(f"         Top Vetos: {vetos_str}\n")
        sys.stdout.write(f"         TPs: {sum(1 for t in trades if t.get('exit_type','') in ('TP_DECAY','TP'))} | SLs: {sum(1 for t in trades if t.get('exit_type','') in ('SL',))} | H1_Bypass: {h1_byp}\n\n")
        sys.stdout.flush()
        return pnl

    except Exception as e:
        import traceback
        sys.stdout.write(f"[{label}] ERRO: {e}\n{traceback.format_exc()}\n\n")
        sys.stdout.flush()
        return None

async def main():
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("  BACKTEST MT5 v52.2 — DADOS HISTORICOS POR DATA\n")
    sys.stdout.write("=" * 60 + "\n\n")
    sys.stdout.flush()

    total_pnl = 0.0
    dias_rodados = 0

    for label, data in DIAS:
        resultado = await rodar_dia_mt5(label, data)
        if resultado is not None:
            total_pnl += resultado
            dias_rodados += 1

    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write(f"TOTAL PnL: R${total_pnl:+.2f} em {dias_rodados} dias\n")
    if dias_rodados > 0:
        sys.stdout.write(f"Media/Dia: R${total_pnl/dias_rodados:+.2f}\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.flush()

if __name__ == '__main__':
    asyncio.run(main())
