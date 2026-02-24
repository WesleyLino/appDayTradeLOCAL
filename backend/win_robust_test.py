import os
import pandas as pd
import numpy as np
import logging
import json
import asyncio
try:
    from backend.optimizer import run_single_backtest
except ImportError:
    from optimizer import run_single_backtest
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor
import itertools

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def perform_wfa(symbol="WIN$", n_folds=3):
    """
    Perform Walk-Forward Analysis on WIN$ historical data.
    """
    data_file = f"data/sota_training/training_{symbol}_MASTER.csv"
    if not os.path.exists(data_file):
        logging.error(f"❌ '{data_file}' not found.")
        return

    df_full = pd.read_csv(data_file)
    total_len = len(df_full)
    fold_size = total_len // n_folds
    
    logging.info(f"🧬 Starting WFA for {symbol} | {n_folds} Folds | Total: {total_len} rows")

    grid = {
        'rsi_period': [9, 11, 14],
        'bb_dev': [2.0, 2.2],
        'sl_dist': [130.0, 150.0],
        'tp_dist': [260.0, 400.0],
        'vol_spike_mult': [1.5],
        'confidence_threshold': [0.4, 0.5]
    }
    
    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    final_results = []

    for fold in range(n_folds):
        start_idx = fold * fold_size
        end_idx = start_idx + fold_size if fold < n_folds - 1 else total_len
        
        logging.info(f"📂 Processing Fold {fold+1}/{n_folds} (Rows {start_idx} to {end_idx})")
        
        # In actual WFA, we use Fold N as In-Sample and Fold N+1 as Out-of-Sample.
        # Here we perform a simplified version: check parameter stability across all folds.
        
        temp_fold_file = f"temp_fold_{fold}.csv"
        df_full.iloc[start_idx:end_idx].to_csv(temp_fold_file, index=False)
        
        fold_results = []
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = {executor.submit(run_single_backtest, params, temp_fold_file): params for params in combinations}
            for future in concurrent.futures.as_completed(futures):
                fold_results.append(future.result())
        
        os.remove(temp_fold_file)
        final_results.append(fold_results)

    # Calculate Average Profit Factor per configuration across folds
    stability_metrics = {}
    for fold_id, results in enumerate(final_results):
        for res in results:
            if "error" in res: continue
            params_key = json.dumps(res['params'], sort_keys=True)
            if params_key not in stability_metrics:
                stability_metrics[params_key] = {"pf_sum": 0, "folds": 0, "net_profit": 0, "max_dd": 0}
            
            stability_metrics[params_key]["pf_sum"] += res['profit_factor']
            stability_metrics[params_key]["net_profit"] += res['net_profit']
            stability_metrics[params_key]["max_dd"] = max(stability_metrics[params_key]["max_dd"], res['max_dd'])
            stability_metrics[params_key]["folds"] += 1

    # Filter only those that appeared in all folds
    champions = []
    for p_key, stats in stability_metrics.items():
        if stats["folds"] == n_folds:
            avg_pf = stats["pf_sum"] / n_folds
            champions.append({
                "params": json.loads(p_key),
                "avg_profit_factor": avg_pf,
                "total_net_profit": stats["net_profit"],
                "max_drawdown": stats["max_dd"]
            })

    champions = sorted(champions, key=lambda x: x['avg_profit_factor'], reverse=True)[:5]
    
    print("\n" + "="*50)
    print(f"🏆 WFA CHAMPIONS - {symbol}")
    print("="*50)
    for i, champ in enumerate(champions):
        print(f"#{i+1} | Avg PF: {champ['avg_profit_factor']:.2f} | Total PnL: R${champ['total_net_profit']:.2f} | Max DD: {champ['max_drawdown']:.2%}")
        print(f"Params: {champ['params']}\n")
    print("="*50)

    if champions:
        out_file = 'best_params_WIN_SOTA.json'
        with open(out_file, 'w') as f:
            json.dump(champions[0], f, indent=4)
        logging.info(f"💾 BEST CONFIG SAVED TO {out_file}")

if __name__ == "__main__":
    perform_wfa(symbol="WIN$", n_folds=3)
