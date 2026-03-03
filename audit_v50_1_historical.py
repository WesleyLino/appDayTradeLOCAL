
import asyncio
import pandas as pd
import numpy as np
import logging
import os
import sys
from datetime import datetime, timedelta

# Adiciona diretório raiz
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro
from backend.mt5_bridge import MT5Bridge
import MetaTrader5 as mt5

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_historical_day(symbol, date_str):
    safe_date = date_str.replace('/', '_')
    filename = f"backend/data_{safe_date}.csv"
    if os.path.exists(filename):
        return filename
    return None

async def run_audit():
    symbol = "WIN$"
    dias = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026", "02/03/2026"]
    
    results = []
    
    for dia in dias:
        filepath = await fetch_historical_day(symbol, dia)
        if not filepath: continue
            
        logging.info(f"🧪 [MODO POTENCIAL BRUTO] Analisando {dia}...")
        tester = BacktestPro(
            symbol=symbol,
            data_file=filepath,
            initial_balance=3000.0,
            use_ai_core=False, # Ignora IA para ver o que o V22 puro faria
            confidence_threshold=0.0
        )
        
        report = await tester.run()
        trades = tester.trades
        df_t = pd.DataFrame(trades)
        
        pnl = df_t['pnl_fin'].sum() if not df_t.empty else 0.0
        trades_count = len(df_t)
        wr = (len(df_t[df_t['pnl_fin'] > 0]) / len(df_t)) * 100 if not df_t.empty else 0.0
        
        # Agora rodamos o modo SOTA Original para ver o "Net Real"
        tester_sota = BacktestPro(
            symbol=symbol,
            data_file=filepath,
            initial_balance=3000.0,
            use_ai_core=True
        )
        await tester_sota.run()
        vetos = tester_sota.shadow_signals.get('filtered_by_ai', 0)
        
        results.append({
            'data': dia,
            'pnl_bruto': pnl,
            'trades_brutos': trades_count,
            'wr_bruto': wr,
            'oportunidades_filtradas': vetos
        })
        logging.info(f"✅ {dia} | PnL Bruto: R$ {pnl:.2f} | Trades: {trades_count} | Filtros: {vetos}")

    df_final = pd.DataFrame(results)
    df_final.to_csv("backend/audit_v50_1_potential.csv", index=False)
    
    print("\n" + "="*80)
    print("💎 ANÁLISE DE POTENCIAL DE MERCADO (V22 PURO VS VETOS V50.1)")
    print("="*80)
    print(df_final.to_string())
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_audit())
