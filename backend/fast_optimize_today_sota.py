import os
import sys
import asyncio
import pandas as pd
import numpy as np
import json
import logging
import itertools
from datetime import datetime

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

async def run_test_sota(params, df_today, ai_core):
    bt = BacktestPro(symbol="WIN", initial_balance=3000.0, **params)
    bt.ai = ai_core
    bt.use_ai_core = True
    
    # Simulação simplificada para otimização rápida
    bt.balance = 3000.0
    bt.position = None
    bt.trades = []
    
    for i in range(len(df_today)):
        row = df_today.iloc[i]
        
        # Gestão de Posição
        if bt.position:
            exit_type, exit_price = bt.simulate_oco(row, bt.position)
            if exit_type:
                pnl = (exit_price - bt.position['entry_price']) if bt.position['side'] == 'buy' else (bt.position['entry_price'] - exit_price)
                bt.balance += pnl * bt.position['lots'] * 0.20
                bt.trades.append(pnl)
                bt.position = None
            elif i - bt.position['index'] > 30: # Max 30 mins
                pnl = (row['close'] - bt.position['entry_price']) if bt.position['side'] == 'buy' else (bt.position['entry_price'] - row['close'])
                bt.balance += pnl * bt.position['lots'] * 0.20
                bt.trades.append(pnl)
                bt.position = None
        
        # Filtro de Sinais
        if not bt.position:
            # Pegar decisão da IA
            # (Aqui simplificamos a passagem de dados para o AICore)
            # Para otimizar, o ideal é que o AICore já tenha os resultados pré-calculados 
            # ou rodar em lote. Para 1 dia (500 bars), rodar direto é OK.
            
            # Precisamos de 60 candles de contexto
            if i < 60: continue
            
            window = df_today.iloc[i-60:i]
            # Formatar para o AICore (SOTA espera DF ou array 60x8)
            # Como df_today tem as colunas [close, WDO$, VALE3, PETR4, ITUB4, cvd, ofi, volume_ratio]
            # que é exatamente o que o model espera.
            
            try:
                # O calculate_decision_sota espera um numpy array 60x8
                decision = ai_core.calculate_decision_sota(window.values)
                
                direction = "NEUTRAL"
                if decision['score'] > params.get('confidence_threshold', 0.85):
                    direction = "BUY"
                elif decision['score'] < (1 - params.get('confidence_threshold', 0.85)):
                    direction = "SELL"
                
                if direction != "NEUTRAL":
                    side = direction.lower()
                    sl = row['close'] - params['sl_dist'] if side == "buy" else row['close'] + params['sl_dist']
                    tp = row['close'] + params['tp_dist'] if side == "buy" else row['close'] - params['tp_dist']
                    bt.position = {
                        'side': side, 'entry_price': row['close'], 'sl': sl, 'tp': tp, 
                        'lots': 1, 'index': i, 'time': row.name
                    }
            except Exception as e:
                pass
                
    return bt.balance - 3000.0, len(bt.trades)

async def perfect_calibration():
    print("🎯 Iniciando Calibragem Perfeita SOTA - 27/02")
    
    # Carregar dados
    data_file = "data/sota_training/training_WIN$_MASTER.csv"
    df = pd.read_csv(data_file)
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Garantir as 8 colunas SOTA
    cols = ['WIN$', 'WDO$', 'VALE3', 'PETR4', 'ITUB4', 'cvd', 'ofi', 'volume_ratio']
    # Se faltar alguma, preenche com 0
    for c in cols:
        if c not in df.columns:
            if c == 'WIN$': df[c] = df['close']
            else: df[c] = 0.0
            
    df = df[cols]
    
    # Filtra apenas Hoje
    df_today = df[df.index.date == datetime(2026, 2, 27).date()].copy()
    
    if len(df_today) < 100:
        print(f"⚠️ Dados insuficientes de hoje ({len(df_today)} linhas). Saindo.")
        return

    # Inicializa IA com os pesos recém-treinados (assumindo que já terminou)
    ai_core = AICore()
    
    grid = {
        'sl_dist': [120, 150, 200],
        'tp_dist': [200, 300, 400],
        'confidence_threshold': [0.75, 0.82, 0.88],
        'vol_spike_mult': [1.0, 1.2]
    }
    
    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    print(f"🔎 Testando {len(combinations)} combinações...")
    
    best_pnl = -9999
    best_params = None
    
    for p in combinations:
        pnl, trades = await run_test_sota(p, df_today, ai_core)
        if trades > 0:
            if pnl > best_pnl:
                best_pnl = pnl
                best_params = p
                print(f"✨ Novo Melhor: R$ {pnl:.2f} ({trades} trades) | Params: {p}")

    if best_params:
        result = {
            "date": "2026-02-27",
            "best_pnl": best_pnl,
            "best_params": best_params,
            "optimized_at": datetime.now().isoformat()
        }
        with open('backend/calibration_27_02.json', 'w') as f:
            json.dump(result, f, indent=4)
        print(f"✅ Calibragem finalizada! Resultado salvo.")
    else:
        print("❌ Nenhuma combinação lucrativa encontrada para hoje.")

if __name__ == "__main__":
    asyncio.run(perfect_calibration())
