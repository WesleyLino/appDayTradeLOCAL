import asyncio
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import sys
import os

# Caminho para backend
sys.path.append(os.path.abspath('backend'))
from mt5_bridge import MT5Bridge
from backtest_pro import BacktestPro

async def diagnose():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("Falha na conexão")
        return

    dia = datetime(2026, 2, 25)
    date_from = dia.replace(hour=7, minute=0)
    date_to = dia.replace(hour=17, minute=0)
    
    data = bridge.get_market_data_range("WIN$", mt5.TIMEFRAME_M1, date_from, date_to)
    if data is None or data.empty:
        print("Dados vazios para WIN$ em 25/02")
        return
        
    print(f"Dados coletados: {len(data)} candles")
    
    bt = BacktestPro(symbol="WIN$", initial_balance=3000, use_ai_core=True)
    bt.data = data
    await bt.run()
    
    # Inspeciona os indicadores nas janelas de oportunidade
    df = bt.data
    # Procura por momentos onde RSI < 40 ou RSI > 60
    potential = df[(df['rsi'] < 35) | (df['rsi'] > 65)]
    print(f"Candles com RSI extremo: {len(potential)}")
    if not potential.empty:
        print("Amostra de potenciais sinais:")
        print(potential[['close', 'rsi', 'upper_bb', 'lower_bb', 'tick_volume', 'vol_sma']].head(20))
    
    print("\nVerificando por que v22_buy/sell_raw falharam:")
    for idx, row in potential.head(10).iterrows():
        rsi_ok = row['rsi'] < 30 or row['rsi'] > 70
        bb_ok = row['close'] < row['lower_bb'] or row['close'] > row['upper_bb']
        vol_ok = row['tick_volume'] > (row['vol_sma'] * 1.0)
        print(f"Horário: {idx} | RSI OK: {rsi_ok} ({row['rsi']:.1f}) | BB OK: {bb_ok} | Vol OK: {vol_ok} (V: {row['tick_volume']} vs SMA: {row['vol_sma']:.1f})")

    bridge.disconnect()

if __name__ == "__main__":
    asyncio.run(diagnose())
