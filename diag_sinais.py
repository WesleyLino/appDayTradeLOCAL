import asyncio
import MetaTrader5 as mt5
import pandas as pd
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
    date_from = dia.replace(hour=9, minute=0)
    date_to = dia.replace(hour=17, minute=0)
    
    data = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, date_from, date_to)
    if data is None or data.empty:
        print("❌ Dados não encontrados.")
        return
        
    print(f"✅ Dados carregados: {len(data)} candles.")
    
    # Simula indicadores básicos
    data['rsi'] = 100 - (100 / (1 + (data['close'].diff().where(data['close'].diff() > 0, 0).rolling(9).mean() / data['close'].diff().where(data['close'].diff() < 0, 0).abs().rolling(9).mean())))
    data['sma_20'] = data['close'].rolling(20).mean()
    data['std_20'] = data['close'].rolling(20).std()
    data['lower_bb'] = data['sma_20'] - 2.0 * data['std_20']
    data['upper_bb'] = data['sma_20'] + 2.0 * data['std_20']
    
    # Procura candidatos V22 brutos
    candidates_buy = data[(data['rsi'] < 30) & (data['close'] < data['lower_bb'])]
    candidates_sell = data[(data['rsi'] > 70) & (data['close'] > data['upper_bb'])]
    
    print(f"🔍 Candidatos Brutos COMPRA: {len(candidates_buy)}")
    print(f"🔍 Candidatos Brutos VENDA: {len(candidates_sell)}")
    
    if len(candidates_buy) > 0:
        print("Exemplo Compra:", candidates_buy.index[0], "RSI:", candidates_buy['rsi'].iloc[0])
    if len(candidates_sell) > 0:
        print("Exemplo Venda:", candidates_sell.index[0], "RSI:", candidates_sell['rsi'].iloc[0])

    bridge.disconnect()

if __name__ == "__main__":
    asyncio.run(diag())
