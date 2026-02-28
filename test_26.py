import asyncio
import sys
import os
import logging
from datetime import datetime

sys.path.append(os.path.abspath('.'))
from backend.backtest_pro import BacktestPro

async def run():
    logging.basicConfig(level=logging.WARNING)
    t = BacktestPro('WIN$', n_candles=2000, timeframe='M1', initial_balance=3000.0, use_ai_core=True)
    t.opt_params['confidence_threshold'] = 0.81
    t.opt_params['use_flux_filter'] = True
    t.opt_params['flux_imbalance_threshold'] = 1.05
    
    t.data = await t.load_data()
    mask = t.data.index.date <= datetime(2026,2,26).date()
    t.data = t.data[mask].tail(1500)
    
    await t.run()
    
    buys = len([tr for tr in t.trades if tr['side']=='buy'])
    sells = len([tr for tr in t.trades if tr['side']=='sell'])
    print(f'Trades: {len(t.trades)}')
    print(f'Buys: {buys}, Sells: {sells}')
    print(f'Lucro Liq: R$ {t.balance - t.initial_balance:.2f}')
    
asyncio.run(run())
