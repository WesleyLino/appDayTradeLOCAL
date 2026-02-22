import asyncio
import json
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_optimized_validation():
    # Configuração de Logs
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # --- APLICAÇÃO DAS MELHORIAS (FASE 13) ---
    initial_capital_per_day = 3000.0
    params['dynamic_lot'] = False 
    params['use_trailing_stop'] = True
    params['force_lots'] = 3
    
    # 1. Melhora: Trailing Stop mais curto para travar lucro cedo
    params['trailing_trigger'] = 70.0  # Era 100
    # 2. Melhora: Breakeven mais rápido
    params['be_trigger'] = 50.0       # Era 70
    # 3. Melhora: Fluxo mais agressivo em tendência (1.2x)
    params['aggressive_mode'] = True  # Ativa v_mult_eff = v_mult * 0.8 (1.5 * 0.8 = 1.2)
    
    print("\n" + "="*85)
    print(f"🚀 VALIDAÇÃO DE OTIMIZAÇÃO SOTA: 30 DIAS INDIVIDUAIS (MT5)")
    print(f"Config: Trailing 70pts | BE 50pts | Flux 1.2x | Lotes: 3.0")
    print("="*85 + "\n")

    # 2. Carregar dados do MT5
    temp_bt = BacktestPro(symbol="WIN$", n_candles=18000, timeframe="M1")
    print("⏳ Coletando dados históricos do MT5...")
    full_df = await temp_bt.load_data()
    
    if full_df is None or full_df.empty:
        print("❌ Erro: Falha ao carregar dados do MT5.")
        return

    full_df['date'] = full_df.index.date
    unique_days = sorted(full_df['date'].unique())
    target_days = unique_days[-30:]
    
    results = []
    total_shadow = {'ai': 0, 'flux': 0}
    
    print(f"{'DATA':<12} | {'LUCRO':<10} | {'TRADES':<6} | {'WR':<6} | {'DD':<8} | {'STATUS'}")
    print("-" * 85)

    for day in target_days:
        day_data = full_df[full_df['date'] == day]
        day_start_idx = full_df.index.get_loc(day_data.index[0])
        start_idx_with_padding = max(0, day_start_idx - 100)
        end_idx = full_df.index.get_loc(day_data.index[-1]) + 1
        
        data_chunk = full_df.iloc[start_idx_with_padding:end_idx].copy()
        
        bt = BacktestPro(
            symbol="WIN$", 
            n_candles=len(data_chunk), 
            timeframe="M1", 
            initial_balance=initial_capital_per_day,
            **params
        )
        
        bt.df = data_chunk
        async def mock_load_data_internal(): return data_chunk
        bt.load_data = mock_load_data_internal
        
        report = await bt.run()
        
        if report is None: continue
            
        trades_today = [t for t in report.get('trades', []) if pd.to_datetime(t['entry_time']).date() == day]
        day_pnl = sum(t['pnl_fin'] for t in trades_today)
        day_count = len(trades_today)
        day_wr = (len([t for t in trades_today if t['pnl_fin'] > 0]) / day_count) * 100 if day_count > 0 else 0
        
        # Tracking shadow
        total_shadow['ai'] += report['shadow_signals']['filtered_by_ai']
        total_shadow['flux'] += report['shadow_signals']['filtered_by_flux']
        
        status = "✅ GANHO" if day_pnl > 0 else ("🛑 LOSS" if day_pnl < 0 else "⚪ NEUTRO")
        
        results.append({
            "date": day,
            "pnl": day_pnl,
            "trades": day_count,
            "win_rate": day_wr,
            "drawdown": report.get('max_drawdown', 0)
        })
        
        print(f"{day.strftime('%d/%m/%Y'):<12} | R$ {day_pnl:>7.2f} | {day_count:>6} | {day_wr:>5.1f}% | {report.get('max_drawdown', 0):>6.2f}% | {status}")

    # 4. Resumo Consolidado Otimizado
    total_net = sum(r['pnl'] for r in results)
    avg_day = total_net / 30
    profitable_days = len([r for r in results if r['pnl'] > 0])
    total_trades = sum(r['trades'] for r in results)
    avg_wr = sum(r['win_rate'] for r in results) / len(results) if results else 0
    
    print("-" * 85)
    print(f"📊 RESUMO ESTRATÉGIA OTIMIZADA")
    print(f"LUCRO TOTAL ACUMULADO:...... R$ {total_net:.2f} (Vs R$ 72.00 anterior)")
    print(f"MÉDIA POR DIA:.............. R$ {avg_day:.2f}")
    print(f"DIAS POSITIVOS:............. {profitable_days} / 30 ({(profitable_days/30)*100:.1f}%)")
    print(f"TOTAL DE TRADES:............ {total_trades}")
    print(f"WIN RATE MÉDIO:............. {avg_wr:.1f}%")
    print(f"SINAIS BLOQUEADOS (AI):..... {total_shadow['ai']}")
    print(f"SINAIS BLOQUEADOS (FLUX):... {total_shadow['flux']} (Otimizado)")
    print("="*85 + "\n")

if __name__ == "__main__":
    asyncio.run(run_optimized_validation())
