import asyncio
import logging
from datetime import datetime
import sys
import os
import pandas as pd
import pprint

sys.path.append(os.path.abspath(r"c:\Users\Wesley Lino\Documents\ProjetosApp\appDayTradeLOCAL"))
from backend.backtest_pro import BacktestPro

async def run_print():
    tester_data = BacktestPro(symbol="WIN$", n_candles=10000, timeframe="M1")
    full_data = await tester_data.load_data()
    
    target_date = datetime.strptime("30/03/2026", "%d/%m/%Y").date()
    mask_until = full_data.index.date <= target_date
    sliced_data = full_data[mask_until].tail(1500).copy()

    tester = BacktestPro(
        symbol="WIN$",
        n_candles=1500,
        timeframe="M1",
        initial_balance=500.0,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=True,
    )
    tester.data = sliced_data
    tester.opt_params["audit_mode"] = True 
    await tester.run()

    print("SHADOW VETO REASONS:")
    pprint.pprint(tester.shadow_signals.get("veto_reasons", {}))
    print("SHADOW BY DATE (30/03):")
    date_key = "2026-03-30"
    if "shadow_by_date" in tester.shadow_signals and date_key in tester.shadow_signals["shadow_by_date"]:
        pprint.pprint(tester.shadow_signals["shadow_by_date"][date_key])

    print("TRADE DATES:")
    from collections import Counter
    dates = [t["entry_time"].date() for t in tester.trades]
    pprint.pprint(Counter(dates))

asyncio.run(run_print())
