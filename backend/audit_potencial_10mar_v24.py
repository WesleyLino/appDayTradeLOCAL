import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import date
from backend.backtest_pro import BacktestPro

logging.basicConfig(level=logging.WARNING)

async def audit_potential_10mar():
    df = pd.read_csv("backend/historico_WIN_10mar_warmup.csv")
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    bt = BacktestPro(symbol="WIN$", capital=3000.0)
    bt.data = df
    
    # [HACK TEMPORÁRIO PARA TESTE] Relaxamos o filtro de VWAP para ver o potencial
    bt.risk.vwap_dist_threshold = 5000.0 
    
    print("🚀 Iniciando Simulação de POTENCIAL (VWAP Aberto) - 10/03")
    await bt.run()
    
    trades_10mar = [t for t in bt.trades if t['entry_time'].date() == date(2026, 3, 10)]
    pnl_10mar = sum([t['pnl_fin'] for t in trades_10mar])
    
    print("\n" + "="*50)
    print("RESULTADOS POTENCIAL (VWAP OPEN) - 10/03")
    print("="*50)
    print(f"Lucro Líquido: R$ {pnl_10mar:.2f}")
    print(f"Trades Executados: {len(trades_10mar)}")
    
    if trades_10mar:
        wins = len([t for t in trades_10mar if t['pnl_fin'] > 0])
        print(f"Win Rate: {(wins/len(trades_10mar))*100:.1f}%")
        for i, t in enumerate(trades_10mar):
            print(f"- Trade {i+1}: {t['side']} @ {t['entry_price']} -> PnL: R$ {t['pnl_fin']:.2f} ({t['reason']})")
    
    print("\nVETOS RESTANTES:")
    print(bt.shadow_signals.get('veto_reasons', {}))
    print("="*50)

if __name__ == "__main__":
    asyncio.run(audit_potential_10mar())
