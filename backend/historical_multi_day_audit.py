import os
import sys
import pandas as pd
import asyncio
import json
import logging
from datetime import datetime

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore, InferenceEngine

# Silencia logs excessivos para o relatório limpo
logging.basicConfig(level=logging.INFO, format='%(message)s')
logging.getLogger().setLevel(logging.INFO)

# Inicializa IA Centralizada
ai = AICore()
engine = InferenceEngine() # Detecta ONNX/DirectML automaticamente
ai.inference_engine = engine

async def run_multi_day_audit():
    dates = ["2026-02-26", "2026-02-25", "2026-02-24", "2026-02-23", "2026-02-20", "2026-02-19"]
    data_file = "data/sota_training/training_WIN$_MASTER.csv"
    
    if not os.path.exists(data_file):
        print(f"❌ Erro: Arquivo {data_file} não encontrado.")
        return

    print(f"📂 Carregando base de dados maestra (WIN$)...")
    try:
        df_all = pd.read_csv(data_file)
        df_all['time'] = pd.to_datetime(df_all['time'])
        df_all.set_index('time', inplace=True)
    except Exception as e:
        print(f"❌ Erro ao ler CSV: {e}")
        return
    
    consolidated_results = {}
    
    print("\n" + "="*60)
    print(f"{'DIA':<12} | {'SALDO':<10} | {'PNL':<10} | {'TRADES':<8} | {'WIN%':<8}")
    print("-" * 60)

    for date_str in dates:
        df_day = df_all[df_all.index.strftime('%Y-%m-%d') == date_str].copy()
        
        if df_day.empty:
            print(f"{date_str:<12} | {'SEM DADOS':<45}")
            continue
            
        # Capital de 3000 conforme solicitado
        # Injetamos o AICore v25 diretamente para ignorar a trava de 'use_ai_core: false' do JSON
        bt = BacktestPro(symbol="WIN$", initial_balance=3000.0, ai_core=ai)
        bt.data = df_day 
        
        # Ativamos o filtro de fluxo e adaptabilidade explicitamente
        bt.opt_params['use_ai_core'] = True
        bt.opt_params['confidence_threshold'] = 0.88 # SWEET SPOT
        bt.opt_params['adaptive_flux_active'] = True
        bt.opt_params['spread'] = 1.0 
        bt.opt_params['trailing_trigger'] = 40.0 # Trava lucro mais cedo
        bt.opt_params['trailing_lock'] = 20.0
        bt.opt_params['trailing_step'] = 10.0        
        report = await bt.run()
        
        if report:
            pnl = report['total_pnl']
            balance = report['final_balance']
            n_trades = len(report['trades'])
            win_rate = report['win_rate']
            
            print(f"{date_str:<12} | R$ {balance:<7.2f} | R$ {pnl:<7.2f} | {n_trades:<8} | {win_rate:<7.1f}%")
            
            # Separar BUY e SELL para o relatório detalhado do usuário
            buys = [t for t in report['trades'] if t['side'] == 'buy']
            sells = [t for t in report['trades'] if t['side'] == 'sell']
            
            consolidated_results[date_str] = {
                'metrics': {
                    'pnl': pnl,
                    'balance': balance,
                    'win_rate': win_rate,
                    'trades_count': n_trades,
                    'buys_count': len(buys),
                    'sells_count': len(sells),
                    'pnl_buys': sum(t['pnl_fin'] for t in buys),
                    'pnl_sells': sum(t['pnl_fin'] for t in sells),
                    'max_drawdown': report['max_drawdown']
                },
                'missed': report['shadow_signals']
            }
        else:
            print(f"{date_str:<12} | {'SEM TRADES':<45}")
            consolidated_results[date_str] = "No trades"

    print("="*60)

    # Salva o relatório consolidado para análise final
    with open('backend/historical_multi_day_report.json', 'w') as f:
        json.dump(consolidated_results, f, indent=4, default=str)
        
    print(f"\n✅ Auditoria Multi-Dia Concluída. Relatório salvo em backend/historical_multi_day_report.json")

if __name__ == "__main__":
    asyncio.run(run_multi_day_audit())
