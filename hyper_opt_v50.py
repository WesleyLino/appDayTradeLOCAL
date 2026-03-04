
import asyncio
import pandas as pd
import numpy as np
import logging
import os
import sys
import itertools
import multiprocessing
import json
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, as_completed

# Adiciona diretório raiz
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro

# Configuração de Logs
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

def run_single_backtest(params, data_files):
    total_pnl = 0
    total_trades = 0
    total_wins = 0
    max_dd = 0
    
    for df_path in data_files:
        tester = BacktestPro(
            symbol="WIN$",
            data_file=df_path,
            initial_balance=3000.0,
            use_ai_core=True,
            **params
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(tester.run())
        
        trades = tester.trades
        if trades:
            total_pnl += sum(t['pnl_fin'] for t in trades)
            total_trades += len(trades)
            total_wins += len([t for t in trades if t['pnl_fin'] > 0])
            max_dd = max(max_dd, tester.max_drawdown)
        loop.close()

    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    # Score ponderado: Valoriza PNL, desvaloriza Drawdown e Trades Insuficientes
    # Exigimos pelo menos 8 trades em 8 dias (1 por dia média)
    if total_trades < 8:
        score = -1000 + total_trades
    else:
        score = total_pnl / (max_dd * 100 + 1)
        
    return {
        'params': params,
        'pnl': total_pnl,
        'trades': total_trades,
        'wr': win_rate,
        'max_dd': max_dd,
        'score': score
    }

async def hyper_optimize():
    symbol = "WIN$"
    dias = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026", "02/03/2026"]
    data_files = []
    
    for dia in dias:
        safe_date = dia.replace('/', '_')
        path = f"backend/data_{safe_date}.csv"
        if os.path.exists(path):
            data_files.append(path)
            
    if not data_files: return

    # Grid V2 (Focada em gerar trades de qualidade)
    grid = {
        'confidence_threshold': [0.45, 0.55],
        'vwap_dist_threshold': [300, 450],
        'vol_spike_mult': [1.0, 1.2, 1.4], # Reduzido de 1.5 para gerar trades
        'rsi_buy_level': [33, 38], # Expandido de 30 para gerar trades
        'rsi_sell_level': [62, 67], # Expandido de 70 
        'tp_dist': [400, 550],
        'sl_dist': [200, 250]
    }

    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    print(f"🧬 Iniciando Hyper-Otimização v2 | {len(combinations)} combinações...")
    
    results = []
    workers = min(multiprocessing.cpu_count(), 8)
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_to_params = {executor.submit(run_single_backtest, c, data_files): c for c in combinations}
        
        completed = 0
        for future in as_completed(future_to_params):
            res = future.result()
            results.append(res)
            completed += 1
            if completed % 20 == 0:
                print(f"⏳ Progresso: {completed}/{len(combinations)}...")

    champions = sorted(results, key=lambda x: x['score'], reverse=True)[:10]
    
    print("\n" + "="*80)
    print("🏆 TOP 10 CONFIGURAÇÕES LUCRATIVAS v5.1 V2 (8 DIAS ACUMULADOS)")
    print("="*80)
    
    for i, champ in enumerate(champions):
        p = champ['params']
        print(f"#{i+1} | PnL Total: R$ {champ['pnl']:.2f} | Trades: {champ['trades']} | WR: {champ['wr']:.1f}% | DD: {champ['max_dd']:.1%}")
        print(f"     Conf: {p['confidence_threshold']} | VWAP: {p['vwap_dist_threshold']} | V-Spike: {p['vol_spike_mult']} | RSI: {p['rsi_buy_level']}/{p['rsi_sell_level']}\n")

    if champions:
        with open("backend/v50_1_hyper_champions_v2.json", "w") as f:
            json.dump(champions, f, indent=4)
        print("💾 Top 10 salvos em backend/v50_1_hyper_champions_v2.json")

if __name__ == "__main__":
    asyncio.run(hyper_optimize())
