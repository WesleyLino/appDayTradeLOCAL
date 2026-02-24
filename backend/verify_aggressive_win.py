import asyncio
import json
import os
import sys
import pandas as pd
import logging

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_scenario(name, params, initial_capital=1000.0):
    print(f"\n--- 🧪 CENÁRIO: {name} ---")
    
    # 1 dia de M1 ~ 600 candles
    n_candles = 600
    
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=n_candles, 
        timeframe="M1", 
        initial_balance=initial_capital,
        **params
    )

    await bt.run()
    
    # Extrair métricas
    df_trades = pd.DataFrame(bt.trades)
    if df_trades.empty:
        return {
            "name": name,
            "profit": 0,
            "drawdown": 0,
            "trades": 0,
            "win_rate": 0
        }
    
    profit = df_trades['pnl_fin'].sum()
    win_rate = (len(df_trades[df_trades['pnl_fin'] > 0]) / len(df_trades)) * 100
    
    return {
        "name": name,
        "profit": profit,
        "drawdown": bt.max_drawdown * 100,
        "trades": len(df_trades),
        "win_rate": win_rate
    }

async def main():
    # Carregar parâmetros base
    params_path = "best_params_WIN.json"
    with open(params_path, 'r') as f:
        base_config = json.load(f)['params']
    
    scenarios = [
        ("Baseline (Safety First)", base_config.copy()),
        ("Aggressive Mode (High Freq)", {**base_config, "aggressive_mode": True}),
        ("Trailing Stop (Trend Rider)", {**base_config, "use_trailing_stop": True}),
        ("Dynamic Lot (Anti-Martingale)", {**base_config, "dynamic_lot": True}),
        ("Full Aggressive Combo", {**base_config, "aggressive_mode": True, "use_trailing_stop": True, "dynamic_lot": True})
    ]
    
    results = []
    for name, params in scenarios:
        res = await run_scenario(name, params)
        results.append(res)
    
    # Comparar resultados
    print("\n" + "="*70)
    print(f"{'CENÁRIO':<30} | {'LUCRO':<10} | {'DD':<8} | {'TRADES':<6} | {'WR':<6}")
    print("-" * 70)
    for r in results:
        print(f"{r['name']:<30} | R$ {r['profit']:>8.2f} | {r['drawdown']:>6.2f}% | {r['trades']:>6} | {r['win_rate']:>5.1f}%")
    print("="*70)

if __name__ == "__main__":
    # Silenciar logs para focar na tabela
    logging.getLogger().setLevel(logging.ERROR)
    asyncio.run(main())
