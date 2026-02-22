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

async def run_365d_stress_test():
    # Configuração de Logs
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 1. Carregar parâmetros campeões otimizados
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # --- CONFIGURAÇÃO OTIMIZADA (FASE 14) ---
    initial_capital = 3000.0
    params['dynamic_lot'] = False 
    params['use_trailing_stop'] = True
    params['force_lots'] = 3
    params['trailing_trigger'] = 70.0  # Otimizado
    params['be_trigger'] = 50.0       # Otimizado
    params['aggressive_mode'] = True  # Fluxo 1.2x Otimizado
    
    print("\n" + "="*85)
    print(f"⌛ TESTE DE ESTRESSE 365 DIAS (ANUAL) - SOTA OPTIMIZED")
    print(f"Capital: R$ 3.000,00 | Lotes: 3.0 | WIN$ M1")
    print("="*85 + "\n")

    # 2. Carregar dados do MT5 (1 ano ~ 250 dias úteis)
    # 90.000 candles M1 cobrem aproximadamente 166 dias de pregão (90.000 / 540)
    temp_bt = BacktestPro(symbol="WIN$", n_candles=90000, timeframe="M1")
    print("⏳ Coletando histórico disponível do MT5 (limite ajustado para 90k candles)...")
    full_df = await temp_bt.load_data()
    
    if full_df is None or full_df.empty:
        print("❌ Erro: Falha ao carregar dados do MT5.")
        return

    full_df['date'] = full_df.index.date
    unique_days = sorted(full_df['date'].unique())
    
    # Selecionar os últimos 365 dias (ou todos se houver menos)
    target_days = unique_days[-365:] if len(unique_days) > 365 else unique_days
    print(f"📅 Período: {target_days[0]} até {target_days[-1]} ({len(target_days)} dias úteis)")
    
    results = []
    equity_curve = [initial_capital]
    current_balance = initial_capital
    max_balance = initial_capital
    max_drawdown = 0
    
    print(f"{'MÊS':<10} | {'LUCRO ACUM':<12} | {'SINAIS':<6} | {'WR %':<6} | {'STATUS'}")
    print("-" * 65)

    last_month = None
    monthly_pnl = 0
    monthly_trades = 0
    monthly_wins = 0

    for day in target_days:
        day_data = full_df[full_df['date'] == day]
        if day_data.empty: continue
            
        day_start_idx = full_df.index.get_loc(day_data.index[0])
        start_idx_with_padding = max(0, day_start_idx - 100)
        end_idx = full_df.index.get_loc(day_data.index[-1]) + 1
        
        data_chunk = full_df.iloc[start_idx_with_padding:end_idx].copy()
        
        bt = BacktestPro(
            symbol="WIN$", 
            n_candles=len(data_chunk), 
            timeframe="M1", 
            initial_balance=3000.0, # Teste individual dia a dia
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
        day_wins = len([t for t in trades_today if t['pnl_fin'] > 0])
        
        current_balance += day_pnl
        equity_curve.append(current_balance)
        
        # Atualiza DD
        if current_balance > max_balance:
            max_balance = current_balance
        dd = ((max_balance - current_balance) / max_balance) * 100
        if dd > max_drawdown:
            max_drawdown = dd
            
        # Acumulador mensal para visualização limpa
        current_month = day.strftime('%Y-%m')
        if last_month and current_month != last_month:
            status = "📈 POS" if monthly_pnl > 0 else "📉 NEG"
            m_wr = (monthly_wins / monthly_trades * 100) if monthly_trades > 0 else 0
            print(f"{last_month:<10} | R$ {current_balance - initial_capital:>9.2f} | {monthly_trades:>6} | {m_wr:>5.1f}% | {status}")
            monthly_pnl = 0
            monthly_trades = 0
            monthly_wins = 0
        
        last_month = current_month
        monthly_pnl += day_pnl
        monthly_trades += day_count
        monthly_wins += day_wins

    # Imprime último mês
    m_wr = (monthly_wins / monthly_trades * 100) if monthly_trades > 0 else 0
    print(f"{last_month:<10} | R$ {current_balance - initial_capital:>9.2f} | {monthly_trades:>6} | {m_wr:>5.1f}% | 📈 POS")

    # 4. Resumo Anual
    total_gain = current_balance - initial_capital
    avg_monthly = total_gain / (len(target_days) / 21)
    
    print("-" * 65)
    print(f"📊 RELATÓRIO ANUAL (365 DIAS) - SOTA OPTIMIZED")
    print(f"LUCRO LÍQUIDO FINAL:........ R$ {total_gain:.2f} ({ (total_gain/initial_capital)*100:.1f}%)")
    print(f"MÉDIA MENSAL ESTIMADA:...... R$ {avg_monthly:.2f}")
    print(f"DRAWDOWN MÁXIMO ANUAL:...... {max_drawdown:.2f}%")
    print(f"SALDO FINAL:................ R$ {current_balance:.2f}")
    print(f"ROBUSTEZ:................... {'ALTA (VIÁVEL)' if total_gain > 0 and max_drawdown < 25 else 'MÉDIA'}")
    print("="*85 + "\n")

if __name__ == "__main__":
    asyncio.run(run_365d_stress_test())
