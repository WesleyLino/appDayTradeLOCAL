import asyncio
import json
import os
import sys
import pandas as pd
import logging

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_scenario(name, params, initial_capital=1000.0, n_candles=12000):
    print(f"\n--- 🧪 TESTE DE ESTRESSE (30 DIAS): {name} ---")
    
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
            "win_rate": 0,
            "equity": initial_capital
        }
    
    profit = df_trades['pnl_fin'].sum()
    win_rate = (len(df_trades[df_trades['pnl_fin'] > 0]) / len(df_trades)) * 100
    
    return {
        "name": name,
        "profit": profit,
        "drawdown": bt.max_drawdown * 100,
        "trades": len(df_trades),
        "win_rate": win_rate,
        "equity": bt.balance
    }

async def main():
    # Carregar parâmetros base
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print("❌ Erro: best_params_WIN.json não encontrado.")
        return

    with open(params_path, 'r') as f:
        base_config = json.load(f)['params']
    
    # Apenas o cenário solicitado: WIN Agressivo
    scenarios = [
        ("Aggressive Mode (Full Day)", {**base_config, "aggressive_mode": True, "use_trailing_stop": False}),
        ("Aggressive + Sniper (10h-12h)", {**base_config, "aggressive_mode": True, "use_trailing_stop": True, "start_time": "10:00", "end_time": "12:00"})
    ]
    
    results = []
    # Usando janela de 30 dias (~12000 candles M1)
    for name, params in scenarios:
        res = await run_scenario(name, params, n_candles=12000)
        results.append(res)
    
    # Comparar resultados
    print("\n" + "="*80)
    print(f"{'CENÁRIO (30 DIAS)':<30} | {'LUCRO':<10} | {'DD':<8} | {'TRADES':<6} | {'WR':<6}")
    print("-" * 80)
    for r in results:
        print(f"{r['name']:<30} | R$ {r['profit']:>8.2f} | {r['drawdown']:>6.2f}% | {r['trades']:>6} | {r['win_rate']:>5.1f}%")
    print("="*80)

if __name__ == "__main__":
    # Silenciar logs para focar na tabela
    logging.getLogger().setLevel(logging.ERROR)
    asyncio.run(main())
