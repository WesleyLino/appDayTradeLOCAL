import os
import sys
import asyncio
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def calculate_diagnostics(df, params, initial_balance=3000.0):
    bt = BacktestPro(symbol="WIN", initial_balance=initial_balance, **params)
    bt.balance = initial_balance
    bt.position = None
    trades = []
    
    # Detecção de oportunidades perdidas (Sinais que não entraram por pouco ou filtro)
    missed_opportunities = []
    
    for i in range(len(df)):
        row = df.iloc[i]
        
        # Lógica de Saída
        if bt.position:
            exit_type, exit_price = bt.simulate_oco(row, bt.position)
            if exit_type:
                pnl = (exit_price - bt.position['entry_price']) if bt.position['side'] == 'buy' else (bt.position['entry_price'] - exit_price)
                bt.balance += pnl * 0.20
                trades.append({
                    'status': 'EXECUTED',
                    'time_entry': bt.position['time'],
                    'time_exit': row.name,
                    'side': bt.position['side'],
                    'entry': bt.position['entry_price'],
                    'exit': exit_price,
                    'pnl': pnl * 0.20,
                    'type': exit_type,
                    'max_favorable': bt.position['max_fav'],
                    'max_adverse': bt.position['max_adv']
                })
                bt.position = None
            else:
                # Track max favorable/adverse
                curr_pnl = (row['close'] - bt.position['entry_price']) if bt.position['side'] == 'buy' else (bt.position['entry_price'] - row['close'])
                bt.position['max_fav'] = max(bt.position.get('max_fav', 0), curr_pnl)
                bt.position['max_adv'] = min(bt.position.get('max_adv', 0), curr_pnl)
                
                if i - bt.position['index'] > 20: 
                    pnl = (row['close'] - bt.position['entry_price']) if bt.position['side'] == 'buy' else (bt.position['entry_price'] - row['close'])
                    bt.balance += pnl * 0.20
                    trades.append({
                        'status': 'EXECUTED',
                        'time_entry': bt.position['time'],
                        'time_exit': row.name,
                        'side': bt.position['side'],
                        'entry': bt.position['entry_price'],
                        'exit': row['close'],
                        'pnl': pnl * 0.20,
                        'type': 'TIME',
                        'max_favorable': bt.position['max_fav'],
                        'max_adverse': bt.position['max_adv']
                    })
                    bt.position = None

        # Lógica de Entrada
        rsi = row['rsi']
        vol_mult = row['tick_volume'] / (row['vol_sma'] + 1e-6)
        
        signal_buy = rsi < 30 and row['close'] < row['lower_bb']
        signal_sell = rsi > 70 and row['close'] > row['upper_bb']
        
        if not bt.position:
            if (signal_buy or signal_sell) and vol_mult > params['vol_spike_mult']:
                side = "buy" if signal_buy else "sell"
                sl = row['close'] - params['sl_dist'] if side == "buy" else row['close'] + params['sl_dist']
                tp = row['close'] + params['tp_dist'] if side == "buy" else row['close'] - params['tp_dist']
                bt.position = {
                    'side': side, 'entry_price': row['close'], 'sl': sl, 'tp': tp, 
                    'lots': 1, 'index': i, 'time': row.name,
                    'max_fav': 0, 'max_adv': 0
                }
            elif (signal_buy or signal_sell):
                # Oportunidade perdida por causa do filtro de volume
                missed_opportunities.append({
                    'time': row.name,
                    'reason': 'VOL_FILTER',
                    'side': 'buy' if signal_buy else 'sell',
                    'price': row['close'],
                    'vol_mult': vol_mult
                })
                
    return trades, missed_opportunities, bt.balance

async def diagnose_today():
    data_file = "data/sota_training/training_WIN$_MASTER.csv"
    df = pd.read_csv(data_file)
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Indicadores
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean() / (-(df['close'].diff().where(df['close'].diff() < 0, 0)).rolling(14).mean() + 1e-6))))
    df['sma_20'] = df['close'].rolling(20).mean()
    df['std_20'] = df['close'].rolling(20).std()
    df['upper_bb'] = df['sma_20'] + 2.0 * df['std_20']
    df['lower_bb'] = df['sma_20'] - 2.0 * df['std_20']
    df['vol_sma'] = df['tick_volume'].rolling(20).mean()
    
    df_today = df[df.index.strftime('%Y-%m-%d') == '2026-02-23'].copy()
    
    # 1. Config SOTA
    params_sota = {
        'sl_dist': 200, 'tp_dist': 200, 'vol_spike_mult': 1.2, 
        'use_trailing_stop': True, 'be_trigger': 100, 'be_lock': 20
    }
    
    # 2. Config Recalibrada
    params_recal = {
        'sl_dist': 130, 'tp_dist': 100, 'vol_spike_mult': 1.1, 
        'use_trailing_stop': False, 'be_trigger': 50, 'be_lock': 10
    }
    
    trades_sota, missed_sota, bal_sota = calculate_diagnostics(df_today, params_sota)
    trades_recal, missed_recal, bal_recal = calculate_diagnostics(df_today, params_recal)
    
    report = {
        'sota': {'trades': trades_sota, 'missed': missed_sota, 'final_balance': bal_sota},
        'recal': {'trades': trades_recal, 'missed': missed_recal, 'final_balance': bal_recal}
    }
    
    with open('backend/detailed_diagnostic_report.json', 'w') as f:
        json.dump(report, f, indent=4, default=str)
        
    print("✅ Diagnóstico Completo Gerado.")
    print(f"SOTA: R$ {bal_sota - 3000:.2f} | RECAL: R$ {bal_recal - 3000:.2f}")

if __name__ == "__main__":
    asyncio.run(diagnose_today())
