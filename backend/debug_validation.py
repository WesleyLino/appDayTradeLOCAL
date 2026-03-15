
import asyncio
import pandas as pd
import os
import json
import logging
import sys
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# Adiciona diretório raiz ao path
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore
from backend.mt5_bridge import MT5Bridge

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DebugValidation")

async def run_debug():
    if not mt5.initialize():
        return

    bridge = MT5Bridge()
    symbol = "WIN$"
    date_str = "2026-03-13"
    
    # Puxar com folga de 2 horas (07:00) para aquecer indicadores
    start_br = datetime.strptime(f"{date_str} 07:00:00", "%Y-%m-%d %H:%M:%S")
    end_br = datetime.strptime(f"{date_str} 18:00:00", "%Y-%m-%d %H:%M:%S")
    
    logger.info(f"🔍 [DEBUG] Puxando dados de {date_str} desde 07:00 BR...")
    df = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, start_br + timedelta(hours=3), end_br + timedelta(hours=3))
    
    if df.empty:
        logger.error("Sem dados.")
        return

    temp_csv = "debug_13mar.csv"
    df.to_csv(temp_csv)
    
    with open('backend/v22_locked_params.json', 'r') as f:
        params = json.load(f)

    bt = BacktestPro(symbol=symbol, data_file=temp_csv)
    bt.ai = AICore()
    bt.opt_params.update(params)
    
    await bt.run()
    
    print(f"\nTrades realizados: {len(bt.trades)}")
    for t in bt.trades:
        print(f"Trade: {t['side']} @ {t['entry_price']} -> {t['exit_price']} | PnL: {t['pnl_fin']}")

    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(run_debug())
