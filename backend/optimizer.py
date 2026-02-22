import os
import sys
import itertools
import multiprocessing
import pandas as pd
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
import concurrent.futures

# Adiciona o diretório raiz ao path para resolver imports de 'backend.*'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_single_backtest(params, data_file):
    """
    Roda uma única simulação com um set específico de parâmetros
    """
    try:
        # Suprimir logs INFO para não poluir console no multiprocessing
        logging.getLogger().setLevel(logging.WARNING)
        
        backtest = BacktestPro(
            data_file=data_file,
            symbol="WIN",
            initial_balance=10000.0,
            **params
        )
        
        # Como o backtest.run é assíncrono, e estamos num ProcessPoolExecutor, precisamos rodar ele sincrono aqui
        import asyncio
        asyncio.run(backtest.run())
        
        # Calcula Profit Factor simplificado
        total_profit = sum(t['pnl_fin'] for t in backtest.trades if t['pnl_fin'] > 0)
        total_loss = abs(sum(t['pnl_fin'] for t in backtest.trades if t['pnl_fin'] < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else 999.0
        
        net_profit = sum(t['pnl_fin'] for t in backtest.trades)
        
        return {
            "params": params,
            "net_profit": net_profit,
            "max_dd": backtest.max_drawdown,
            "profit_factor": profit_factor,
            "trades": len(backtest.trades)
        }
    except Exception as e:
        import traceback
        logging.error(f"Erro na simulação: {e}")
        traceback.print_exc()
        return {"params": params, "error": str(e), "profit_factor": 0}

def optimize():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, default="WIN$")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=multiprocessing.cpu_count())
    parser.add_argument("--start_time", type=str, default="09:15")
    parser.add_argument("--end_time", type=str, default="17:15")
    args = parser.parse_args()

    symbol_clean = args.symbol.replace("$", "")
    data_file = f"data/sota_training/training_{args.symbol}_MASTER.csv"
    
    if not os.path.exists(data_file):
        logging.error(f"❌ '{data_file}' não encontrado.")
        return

    # Matriz de Variáveis Expandida (Deep Grid WIN$)
    if "WIN" in args.symbol:
        grid = {
            'rsi_period': [7, 9, 11, 14],
            'bb_dev': [1.8, 2.0, 2.2, 2.5],
            'sl_dist': [100.0, 130.0, 150.0, 200.0],
            'tp_dist': [200.0, 300.0, 400.0, 500.0],
            'vol_spike_mult': [1.2, 1.5, 1.8],
            'confidence_threshold': [0.4, 0.5, 0.6] # [SOTA] Filtro de Confiança
        }
    else: # Dólar (WDO)
        grid = {
            'rsi_period': [7, 10, 14],
            'bb_dev': [1.0, 1.5, 2.0],
            'sl_dist': [3.5, 5.0, 7.5],
            'tp_dist': [7.0, 15.0, 25.0],
            'vol_spike_mult': [1.0, 1.2]
        }
    
    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    # Injetar filtros de tempo em todas as combinações
    for c in combinations:
        c['start_time'] = args.start_time
        c['end_time'] = args.end_time
    
    logging.info(f"🧬 Iniciando Otimização AlphaV22 Pro [{args.symbol}] | {len(combinations)} combinações | {args.workers} workers.")
    
    results = []
    import time
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_single_backtest, params, data_file): params for params in combinations}
        
        for idx, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            logging.getLogger().setLevel(logging.INFO)
            
            if "error" not in result:
                 logging.info(f"✅ [{args.symbol}] {idx+1}/{len(combinations)}: PF {result['profit_factor']:.2f} | PnL R${result['net_profit']:.2f} | DD {result['max_dd']:.2%}")
            results.append(result)
            
    elapsed = time.time() - start_time
    logging.info(f"⏱ Tempo total: {elapsed:.2f}s")

    valid_results = [r for r in results if "error" not in r]
    if not valid_results: return
        
    champions = sorted(valid_results, key=lambda x: x['profit_factor'], reverse=True)[:5]
    
    print("\n" + "="*50)
    print(f"🏆 CAMPEÕES DO GRID SEARCH - {args.symbol}")
    print("="*50)
    for i, champ in enumerate(champions):
        print(f"#{i+1} | PF: {champ['profit_factor']:.2f} | Lucro: R${champ['net_profit']:.2f} | DD: {champ['max_dd']:.2%}")
        print(f"Params: {champ['params']}\n")
    print("="*50)
    
    out_file = f'best_params_{symbol_clean}.json'
    with open(out_file, 'w') as f:
        json.dump(champions[0], f, indent=4)
    logging.info(f"💾 Melhor parâmetro salvo em {out_file}")
        
if __name__ == "__main__":
    optimize()
