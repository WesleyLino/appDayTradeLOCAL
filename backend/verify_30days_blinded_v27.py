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

async def run_blinded_30day_test():
    # Configuração de Logs (Reduzir verbosidade para monitorar progresso)
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # --- CONFIGURAÇÃO BLINDADA (FASE 27/28) ---
    initial_capital_per_day = 3000.0
    params['use_trailing_stop'] = True
    params['use_ai_core'] = True        # Ativa calculate_decision()
    params['force_lots'] = None         # Deixa o Meta-Learner escalar (1, 2 ou 3)
    params['base_lot'] = 1
    
    # Parâmetros de Trailing/BE validados
    params['trailing_trigger'] = 70.0  
    params['be_trigger'] = 50.0       
    params['aggressive_mode'] = True  
    
    print("\n" + "="*85)
    print("🚀 TESTE DE ESTRESSE 30 DIAS: SISTEMA BLINDADO (AIA-27)")
    print("Motor: AICore.calculate_decision | Meta-Learner: XGBoost | Lote: Dinâmico")
    print("="*85 + "\n")

    # 2. Carregar dados do MT5
    # n_candles para 30 dias (aprox 12k candles M1)
    temp_bt = BacktestPro(symbol="WIN$", n_candles=18000, timeframe="M1")
    print("⏳ Coletando dados históricos do MT5 (WIN$)...")
    full_df = await temp_bt.load_data()
    
    if full_df is None or full_df.empty:
        print("❌ Erro: Falha ao carregar dados do MT5. Certifique-se que o MT5 está aberto.")
        return

    full_df['date'] = full_df.index.date
    unique_days = sorted(full_df['date'].unique())
    target_days = unique_days[-30:] # Últimos 30 pregões
    
    print(f"📊 Histórico carregado: {len(full_df)} candles")
    print(f"📅 Dias identificados para teste: {len(target_days)}")
    
    if not target_days:
        print("❌ Erro: Não há histórico suficiente para 30 dias. Verifique se o MT5 tem dados de M1 disponíveis.")
        return
        
    results = []
    
    print(f"{'DATA':<12} | {'LUCRO':<10} | {'TRADES':<6} | {'WR':<6} | {'DD':<8} | {'STATUS'}")
    print("-" * 85)

    for i, day in enumerate(target_days):
        day_data = full_df[full_df['date'] == day]
        if day_data.empty: continue
        
        day_start_idx = full_df.index.get_loc(day_data.index[0])
        # Padding de 100 velas para indicadores (RSI/SMA) estabilizarem
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
        
        # Injeta o DataFrame manipulado
        bt.df = data_chunk
        async def mock_load_data_internal(): return data_chunk
        bt.load_data = mock_load_data_internal
        
        # Executa a simulação do dia
        report = await bt.run()
        
        if report is None: 
            print(f"{day.strftime('%d/%m/%Y'):<12} | ERR_SIM    | ---    | ---    | ---      | ❌")
            continue
            
        trades_today = [t for t in report.get('trades', []) if pd.to_datetime(t['entry_time']).date() == day]
        day_pnl = sum(t['pnl_fin'] for t in trades_today)
        day_count = len(trades_today)
        day_wr = (len([t for t in trades_today if t['pnl_fin'] > 0]) / day_count) * 100 if day_count > 0 else 0
        
        status = "✅ GANHO" if day_pnl > 0 else ("🛑 LOSS" if day_pnl < 0 else "⚪ NEUTRO")
        
        results.append({
            "date": day,
            "pnl": day_pnl,
            "trades": day_count,
            "win_rate": day_wr,
            "drawdown": report.get('max_drawdown', 0)
        })
        
        print(f"{day.strftime('%d/%m/%Y'):<12} | R$ {day_pnl:>7.2f} | {day_count:>6} | {day_wr:>5.1f}% | {report.get('max_drawdown', 0):>6.2f}% | {status}")

    # 4. Resumo Consolidado
    total_net = sum(r['pnl'] for r in results)
    profitable_days = len([r for r in results if r['pnl'] > 0])
    total_trades = sum(r['trades'] for r in results)
    avg_wr = sum(r['win_rate'] for r in results) / len(results) if results else 0
    max_dd_day = max([r['drawdown'] for r in results]) if results else 0
    
    print("-" * 85)
    print("📊 RESULTADO FINAL - SISTEMA BLINDADO (30 DIAS)")
    print(f"LUCRO LÍQUIDO TOTAL:........ R$ {total_net:.2f}")
    print(f"DIAS POSITIVOS:............. {profitable_days} / {len(results)} ({(profitable_days/len(results)*100) if len(results) > 0 else 0:.1f}%)")
    print(f"TOTAL DE OPERAÇÕES:......... {total_trades}")
    print(f"WIN RATE MÉDIO:............. {avg_wr:.1f}%")
    print(f"MAX DRAWDOWN DIÁRIO:........ {max_dd_day:.2f}%")
    print("CAPITAL SUGERIDO:........... R$ 3.000,00")
    print("="*85 + "\n")

if __name__ == "__main__":
    asyncio.run(run_blinded_30day_test())
