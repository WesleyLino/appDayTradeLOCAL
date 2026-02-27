import asyncio
import pandas as pd
import logging
import os
from datetime import datetime
from backend.backtest_pro import BacktestPro

async def run_diagnostic():
    symbol = "WIN$"
    # Configuração idêntica ao v22_locked_params.json
    base_cfg = {
        'rsi_period': 9,
        'bb_dev': 2.0,
        'vol_spike_mult': 1.0,
        'use_flux_filter': True,
        'flux_imbalance_threshold': 1.2,
        'confidence_threshold': 0.70,
        'sl_dist': 150.0,
        'tp_dist': 400.0,
        'use_ai_core': False # Começar testando Legacy
    }

    print("--- DIAGNÓSTICO DE ASSERTIVIDADE (24/02) ---")
    
    # 1. TESTE LEGACY (O que provavelmente rodou ontem)
    print("\n>>> TESTE 1: MODO LEGACY (RSI/BB/VOL)")
    tester_legacy = BacktestPro(
        symbol=symbol,
        n_candles=1500, # Focado no dia 24
        **base_cfg
    )
    # Filtra 24/02 no load_data
    all_data = await tester_legacy.load_data()
    day_24 = all_data[all_data.index.date == datetime(2026, 2, 24).date()]
    tester_legacy.data = day_24
    res_legacy = await tester_legacy.run()
    
    # 2. TESTE AI (O que o modelo atual vê)
    print("\n>>> TESTE 2: MODO SOTA (AI CORE ATIVO)")
    ai_cfg = base_cfg.copy()
    ai_cfg['use_ai_core'] = True
    tester_ai = BacktestPro(
        symbol=symbol,
        n_candles=1500,
        **ai_cfg
    )
    tester_ai.data = day_24
    res_ai = await tester_ai.run()

    print("\n--- RESUMO COMPARATIVO ---")
    print(f"Legacy Trades: {len(res_legacy['trades']) if res_legacy else 0}")
    print(f"AI Trades:     {len(res_ai['trades']) if res_ai else 0}")
    
    if res_legacy:
        print(f"Legacy PnL: R$ {res_legacy['total_pnl']:.2f}")
    if res_ai:
        print(f"AI PnL:     R$ {res_ai['total_pnl']:.2f}")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())
