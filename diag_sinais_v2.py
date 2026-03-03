import asyncio
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys

sys.path.insert(0, os.getcwd())
from backend.mt5_bridge import MT5Bridge

async def diag():
    bridge = MT5Bridge()
    if not bridge.connect(): return
    
    symbol = "WIN$N"
    dia = datetime(2026, 2, 26)
    date_from = dia.replace(hour=7, minute=0)
    date_to = dia.replace(hour=17, minute=0)
    
    data = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, date_from, date_to)
    if data is None or data.empty:
        print("❌ Dados não encontrados.")
        return
        
    print(f"✅ Dados carregados: {len(data)} candles.")
    
    # Indicadores
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=9, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=9, adjust=False).mean()
    data['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    
    data['sma_20'] = data['close'].rolling(20).mean()
    data['std_20'] = data['close'].rolling(20).std()
    data['lower_bb'] = data['sma_20'] - 2.0 * data['std_20']
    data['upper_bb'] = data['sma_20'] + 2.0 * data['std_20']
    
    data['vol_sma'] = data['tick_volume'].rolling(20).mean()
    data['vol_spike'] = data['tick_volume'] > data['vol_sma']
    
    # Procura candidatos V22
    tech_buy = (data['rsi'] < 30) & (data['close'] < data['lower_bb'])
    tech_sell = (data['rsi'] > 70) & (data['close'] > data['upper_bb'])
    
    full_buy = tech_buy & data['vol_spike']
    full_sell = tech_sell & data['vol_spike']
    
    print(f"🔍 Tech COMPRA (No Vol): {tech_buy.sum()}")
    print(f"🔍 Full COMPRA (With Vol): {full_buy.sum()}")
    print(f"🔍 Tech VENDA (No Vol): {tech_sell.sum()}")
    print(f"🔍 Full VENDA (With Vol): {full_sell.sum()}")
    
    bridge.disconnect()

if __name__ == "__main__":
    asyncio.run(diag())
