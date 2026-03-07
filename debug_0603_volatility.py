import asyncio
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from backend.backtest_pro import BacktestPro

async def debug_0603():
    print("======= DIAGNÓSTICO VOLATILIDADE 06/03 =======")
    
    data_file = "data/sota_training/training_WIN$_MASTER.csv"
    df_master = pd.read_csv(data_file)
    df_master['time'] = pd.to_datetime(df_master['time'])
    
    dia = "2026-03-06"
    t_start_day = pd.to_datetime(f"{dia} 09:00:00")
    t_end_day = pd.to_datetime(f"{dia} 18:00:00")
    
    # Pegamos dados com warm-up
    day_df = df_master[(df_master['time'] >= (t_start_day - timedelta(hours=2))) & 
                       (df_master['time'] <= t_end_day)].copy()
    
    # 1. Verificar H-L médio dos primeiros 10 min
    opening_10 = day_df[(day_df['time'] >= "2026-03-06 09:00:00") & (day_df['time'] <= "2026-03-06 09:10:00")]
    hl_mean = (opening_10['high'] - opening_10['low']).mean()
    print(f"H-L Médio (09:00-09:10): {hl_mean:.2f} pts")
    
    # 2. Rodar o backtest e ver logs de veto
    temp_csv = "data/sota_training/debug_temp_0603.csv"
    day_df.to_csv(temp_csv, index=False)
    
    params_path = "backend/v22_locked_params.json"
    with open(params_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    bt = BacktestPro(
        symbol="WIN$",
        data_file=temp_csv,
        **config['strategy_params']
    )
    
    await bt.run()
    
    print(f"\nResultado Final Debug: R$ {bt.balance - 500.0:.2f}")
    print(f"Trades Realizados: {len(bt.trades)}")
    print("\nVetos de IA ou Filtros:")
    print(json.dumps(bt.shadow_signals, indent=4))
    
    if os.path.exists(temp_csv):
        os.remove(temp_csv)

if __name__ == "__main__":
    asyncio.run(debug_0603())
