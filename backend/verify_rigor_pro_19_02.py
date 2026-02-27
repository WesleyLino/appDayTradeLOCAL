import asyncio
import os
import sys
import pandas as pd
import logging
from datetime import datetime, timedelta

# Adiciona diretório raiz para importar módulos do backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_audit():
    print("🚀 VALIDANDO RIGOR PRO SOTA v3.1 - 19/02/2026")
    print("="*60)
    
    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=10000, 
        initial_balance=3000.0,
        use_ai_core=True,
        aggressive_mode=True,
        base_lot=1,
        dynamic_lot=False
    )
    
    # Ajustar para 19/02
    data = await backtester.load_data()
    if data is not None:
        target_date = "2026-02-19"
        data_filtered = data[data.index.strftime('%Y-%m-%d') == target_date]
        if not data_filtered.empty:
            backtester.data = data_filtered
        else:
            print(f"❌ Dados para {target_date} não encontrados.")
            return

    # Executar Backtest
    results = await backtester.run()

    if results:
        print("\n" + "="*60)
        print("📈 RESULTADO RIGOR PRO (19/02/2026)")
        print("="*60)
        print(f"PnL Total:        R$ {results['total_pnl']:.2f}")
        print(f"Win Rate:         {results['win_rate']:.1f}%")
        print(f"Total de Trades:  {len(results['trades'])}")
        shadow = results['shadow_signals']
        print(f"Vetos de Fluxo:   {shadow['filtered_by_flux']}")
        print("="*60)

if __name__ == "__main__":
    asyncio.run(run_audit())
