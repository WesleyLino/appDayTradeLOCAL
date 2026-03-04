"""
Script de validação das correções v52.1 BugFix
Testa cada dia histórico disponível no CSV e exibe resultado por dia.
"""
import asyncio
import sys
import os
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, '.')

from backend.backtest_pro import BacktestPro

DIAS = [
    ('19/02', 'backend/data_19_02_2026.csv'),
    ('23/02', 'backend/data_23_02_2026.csv'),
    ('24/02', 'backend/data_24_02_2026.csv'),
    ('25/02', 'backend/data_25_02_2026.csv'),
    ('26/02', 'backend/data_26_02_2026.csv'),
    ('27/02', 'backend/data_27_02_2026.csv'),
]

async def rodar_dia(label, arquivo):
    if not os.path.exists(arquivo):
        print(f"[SKIP] {label} — arquivo não encontrado: {arquivo}")
        return None

    bt = BacktestPro(symbol='WIN$', data_file=arquivo, initial_balance=3000.0)
    await bt.run()

    trades = bt.trades
    total = len(trades)
    wins  = sum(1 for t in trades if t.get('pnl', 0) > 0)
    sells = sum(1 for t in trades if t.get('side') == 'sell')
    buys  = sum(1 for t in trades if t.get('side') == 'buy')
    pnl   = bt.balance - bt.initial_balance
    wr    = (wins / total * 100) if total > 0 else 0.0

    vetos_top = sorted(
        bt.shadow_signals.get('veto_reasons', {}).items(),
        key=lambda x: x[1], reverse=True
    )[:3]
    vetos_str = " | ".join(f"{k}={v}" for k, v in vetos_top) if vetos_top else "nenhum"

    sell_vetos_ia = bt.shadow_signals.get('sell_vetos_ai', 0)
    buy_vetos_ia  = bt.shadow_signals.get('buy_vetos_ai', 0)

    sys.stdout.write(f"[{label}] PnL: R${pnl:+.2f} | Trades: {total} (C:{buys}/V:{sells}) | WR: {wr:.1f}%\n")
    sys.stdout.write(f"         Vetos IA -> Compra: {buy_vetos_ia} | Venda: {sell_vetos_ia}\n")
    sys.stdout.write(f"         Top Vetos: {vetos_str}\n")
    sys.stdout.write(f"         TPs: {sum(1 for t in trades if t.get('exit_type','') in ('TP_DECAY','TP'))} | SLs: {sum(1 for t in trades if t.get('exit_type','') in ('SL',))}\n\n")
    sys.stdout.flush()
    return pnl

async def main():
    print("=" * 60)
    print("  VALIDAÇÃO PÓS-CORREÇÃO v52.1 — BUGFIX AUDITORIA 03/03")
    print("=" * 60)
    print()

    total_pnl = 0.0
    dias_rodados = 0

    for label, arquivo in DIAS:
        resultado = await rodar_dia(label, arquivo)
        if resultado is not None:
            total_pnl += resultado
            dias_rodados += 1

    print("=" * 60)
    print(f"TOTAL PnL: R${total_pnl:+.2f} em {dias_rodados} dias")
    print(f"Média/Dia: R${total_pnl/dias_rodados:+.2f}" if dias_rodados > 0 else "")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
