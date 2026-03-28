import asyncio
import logging
from datetime import datetime, date
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro

async def debug_0503():
    # Set logging to INFO to see trade details
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    symbol = "WIN$"
    capital = 500.0
    target_date = date(2026, 3, 5)

    param_path = os.path.join(os.path.dirname(__file__), "backend", "v24_locked_params.json")
    with open(param_path, "r", encoding="utf-8") as f:
        v24_params = json.load(f)

    tester = BacktestPro(
        symbol=symbol,
        n_candles=10000, # Suficiente para ~18 dias
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=False,
        use_ai_core=True,
    )
    
    # Sync params
    for k, v in v24_params.items():
        if k != "account_config":
            tester.opt_params[k] = v

    # Download data for specifically this window
    all_data = await tester.load_data()
    day_data = all_data[all_data.index.date == target_date].copy()
    
    if day_data.empty:
        print("❌ Dados para 05/03 não encontrados.")
        return

    tester.data = day_data
    print(f"\n🔬 ANALISANDO DETALHADAMENTE O DIA {target_date.strftime('%d/%m/%Y')}...")
    await tester.run()

    print("\n" + "="*50)
    print(f"RESULTADO FINAL 05/03: R$ {tester.balance - capital:.2f}")
    print("="*50)
    
    for t in tester.trades:
        print(f"TRADE: {t['side']} @ {t['entry_price']} | EXIT: {t['exit_price']} | MOTIVO: {t['reason']} | PnL: {t['pnl_fin']}")

if __name__ == "__main__":
    asyncio.run(debug_0503())
