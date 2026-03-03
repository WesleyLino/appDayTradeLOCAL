import asyncio
import pandas as pd
import numpy as np
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def debug_triggers():
    # Carrega dados
    bt = BacktestPro(symbol='WIN$', n_candles=15000)
    data = await bt.load_data()
    
    # Cálculos manuais (Copiados do BacktestPro.run para debug)
    rsi_p = bt.opt_params['rsi_period']
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    rs = gain / loss
    data['rsi'] = 100 - (100 / (1 + rs))
    
    data['sma_20'] = data['close'].rolling(window=20).mean()
    data['std_20'] = data['close'].rolling(window=20).std()
    data['upper_bb'] = data['sma_20'] + (bt.opt_params['bb_dev'] * data['std_20'])
    data['lower_bb'] = data['sma_20'] - (bt.opt_params['bb_dev'] * data['std_20'])
    data['vol_sma'] = data['tick_volume'].rolling(window=20).mean()
    
    print(f"Dataset total: {len(data)} velas")
    
    # Procura condições de COMPRA
    buy_cond = data[(data['rsi'] < 30) & (data['close'] < data['lower_bb'])]
    # Procura condições de VENDA
    sell_cond = data[(data['rsi'] > 70) & (data['close'] > data['upper_bb'])]
    
    print(f"Potenciais de COMPRA (Matematicos): {len(buy_cond)}")
    print(f"Potenciais de VENDA (Matematicos): {len(sell_cond)}")
    
    if not buy_cond.empty:
        print("\nExemplo de Sinal de COMPRA:")
        print(buy_cond[['close', 'rsi', 'lower_bb', 'tick_volume']].head(5))
        
    if not sell_cond.empty:
        print("\nExemplo de Sinal de VENDA:")
        print(sell_cond[['close', 'rsi', 'upper_bb', 'tick_volume']].head(5))

    # Verifica o volume
    vol_sma_avg = data['vol_sma'].mean()
    print(f"\nMedia de Volume SMA: {vol_sma_avg:.2f}")
    print(f"Max Tick Volume: {data['tick_volume'].max()}")

if __name__ == "__main__":
    asyncio.run(debug_triggers())
