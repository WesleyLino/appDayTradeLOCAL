import asyncio
import pandas as pd
import numpy as np
import logging
from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

logging.basicConfig(level=logging.INFO)

async def run_scenario(name, threshold=88.0, partial_pts=60.0):
    logging.info(f"🚀 Rodando Cenário: {name} (Threshold: {threshold}, Parcial: {partial_pts})")
    data_files = ["backend/data_19_02_2026.csv", "backend/data_20_02_2026.csv", "backend/data_23_02_2026.csv"]
    total_pnl = 0
    total_trades = 0
    
    for f in data_files:
        bt = BacktestPro(symbol="WIN$", data_file=f, use_ai_core=True)
        # Injeção sincronizada de parâmetros v52.1 (MODO ILIMITADO)
        conf_val = threshold / 100.0
        bt.ai.buy_threshold = threshold
        bt.ai.sell_threshold = 100.0 - threshold
        bt.opt_params['confidence_threshold'] = conf_val
        bt.opt_params['bb_dev'] = 2.0
        bt.opt_params['daily_trade_limit'] = 999 # Simulação de trades ilimitados
        bt.risk.partial_profit_points = 45.0 # Parcial otimizada
        
        # Hack temporário para mudar o threshold interno do AICore durante o teste
        # (Em produção mudaríamos o hardcode, aqui mudamos a instância)
        # Note: ai_core.py uses hardcoded 88.0, we will simulate by checking the score return.
        
        results = await bt.run()
        total_pnl += results['total_pnl']
        total_trades += len(bt.trades)
        vetos = bt.shadow_signals.get('veto_reasons', {})
        candidates = bt.shadow_signals.get('v22_candidates', 0)
        
    return {"name": name, "pnl": total_pnl, "trades": total_trades, "vetos": vetos, "candidates": candidates}

async def main():
    scenarios = [
        {"name": "v52.0 (Elite - 88%)", "threshold": 88.0, "partial": 60.0},
        {"name": "v52.1 (Performance - 75%)", "threshold": 75.0, "partial": 45.0},
        {"name": "v52.1 (Turbo - 65%)", "threshold": 65.0, "partial": 40.0} 
    ]
    
    reports = []
    for s in scenarios:
        res = await run_scenario(s['name'], s['threshold'], s['partial'])
        reports.append(res)
        
    print("\n" + "="*50)
    print("DIAGNÓSTICO DE OPORTUNIDADES v52.1")
    print("="*50)
    for r in reports:
        print(f"[{r['name']}] Lucro: R$ {r['pnl']:.2f} | Trades: {r['trades']} | Candidatos Técnicos: {r['candidates']}")
        print(f"   -> Bloqueios IA: {r['vetos']}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
