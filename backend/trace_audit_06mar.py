import asyncio
import pandas as pd
import numpy as np
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro

async def trace_all_candidates():
    params_path = "backend/v22_locked_params.json"
    with open(params_path, "r") as f:
        config = json.load(f)
        strategy_params = config.get("strategy_params", {})
    
    target_date = "2026-03-06"
    capital = 3000.0
    
    bt = BacktestPro(symbol="WIN$", n_candles=3000, initial_balance=capital, **strategy_params)
    df_full = await bt.load_data()
    df = df_full[df_full.index.strftime('%Y-%m-%d') == target_date].copy()
    
    # Rodar os indicadores
    rsi_p = strategy_params['rsi_period']
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    bb_d = strategy_params['bb_dev']
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['std_20'] = df['close'].rolling(window=20).std()
    df['upper_bb'] = df['sma_20'] + bb_d * df['std_20']
    df['lower_bb'] = df['sma_20'] - bb_d * df['std_20']
    df['vol_sma'] = df['tick_volume'].rolling(window=20).mean()
    
    candidates = []
    v_mult = strategy_params.get('vol_spike_mult', 0.8)
    
    for i in range(20, len(df)):
        row = df.iloc[i]
        
        # Technical Logic RSI + BB + Vol Spike
        is_buy_signal = (row['rsi'] < 30 and row['close'] < row['lower_bb']) and (row['tick_volume'] > row['vol_sma'] * v_mult)
        is_sell_signal = (row['rsi'] > 70 and row['close'] > row['upper_bb']) and (row['tick_volume'] > row['vol_sma'] * v_mult)
        
        if is_buy_signal or is_sell_signal:
            side = 'buy' if is_buy_signal else 'sell'
            entry = row['close']
            sl = entry - 150 if side == 'buy' else entry + 150
            tp = entry + 450 if side == 'buy' else entry - 450
            
            # Trace outcome (Forward look)
            outcome = 'STILL_OPEN'
            pnl = 0
            for j in range(i+1, min(i+120, len(df))):
                f_row = df.iloc[j]
                if side == 'buy':
                    if f_row['low'] <= sl:
                        outcome = 'STOP'
                        pnl = -30.0
                        break
                    if f_row['high'] >= tp:
                        outcome = 'TAKE'
                        pnl = 90.0
                        break
                else:
                    if f_row['high'] >= sl:
                        outcome = 'STOP'
                        pnl = -30.0
                        break
                    if f_row['low'] <= tp:
                        outcome = 'TAKE'
                        pnl = 90.0
                        break
            
            candidates.append({
                "time": row.name.strftime("%H:%M"),
                "side": side,
                "rsi": round(row['rsi'], 2),
                "outcome": outcome,
                "potential_pnl": pnl
            })
            
    # Agrupar resultados
    summary = {
        "buy": {"trades": 0, "gain": 0, "loss": 0, "net": 0},
        "sell": {"trades": 0, "gain": 0, "loss": 0, "net": 0}
    }
    
    # Salvar em arquivo
    results = {"summary": summary, "signals": candidates}
    with open("backend/trace_audit_final.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ Resultados salvos em backend/trace_audit_final.json")

if __name__ == "__main__":
    asyncio.run(trace_all_candidates())
