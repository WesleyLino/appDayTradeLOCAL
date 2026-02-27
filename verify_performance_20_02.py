import asyncio
import logging
import pandas as pd
from datetime import datetime
import os
import glob
import sys

# Adicionar o diretório raiz ao path
sys.path.append(os.getcwd())

from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def run_audit_20_02():
    bridge = MT5Bridge()
    
    # Data de Interesse: 20/02/2026
    target_date = datetime(2026, 2, 20)
    symbol = "WIN$N"
    date_from = target_date.replace(hour=9, minute=0, second=0)
    date_to = target_date.replace(hour=18, minute=30, second=0)

    print("\n" + "="*70)
    print("📊 AUDITORIA DE PERFORMANCE SOTA v3.1: 20/02/2026 | CAPITAL: R$ 3.000,00")
    print("="*70)
    
    # Coleta de dados via CSV MASTER
    print(f"📥 Carregando histórico do CSV MASTER para {symbol}...")
    try:
        master_file = glob.glob('data/sota_training/training_WIN*_MASTER.csv')[0]
        full_df = pd.read_csv(master_file)
        full_df['time'] = pd.to_datetime(full_df['time'])
        
        # Filtrar para 20/02
        mask = (full_df['time'] >= date_from) & (full_df['time'] <= date_to)
        data = full_df.loc[mask].copy()
        data.set_index('time', inplace=True)
    except Exception as e:
        print(f"❌ ERRO ao carregar CSV: {e}")
        return
    
    if data is None or data.empty:
        print("❌ ERRO: Não há dados para 20/02 no arquivo MASTER.")
        return

    print(f"✅ {len(data)} velas carregadas para o pregão de 20/02.")

    # 1. Backtest SOTA v3.1
    print("\n🚀 Executando Backtest Oficial SOTA v3.1...")
    back_sota = BacktestPro(
        symbol=symbol,
        initial_balance=3000.0,
        use_ai_core=True
    )
    back_sota.data = data.copy()
    results_sota = await back_sota.run()

    # 2. Backtest LEGACY
    print("\n🤖 Executando Backtest Legado V22 (No AI)...")
    back_legacy = BacktestPro(
        symbol=symbol,
        initial_balance=3000.0,
        use_ai_core=False
    )
    back_legacy.data = data.copy()
    results_legacy = await back_legacy.run()

    # COMPARATIVO E INSIGHTS
    print("\n" + "="*70)
    print("🏆 RESULTADO COMPARATIVO: 20/02 (WIN$)")
    print("-" * 70)
    
    pnl_sota = results_sota.get('total_pnl', 0)
    pnl_legacy = results_legacy.get('total_pnl', 0)
    
    trades_sota = len(results_sota.get('trades', []))
    trades_legacy = len(results_legacy.get('trades', []))
    
    # Cálculo de Win Rate aproximado
    def get_wr(res):
        trades = res.get('trades', [])
        if not trades: return 0
        wins = len([t for t in trades if t.get('pnl', 0) > 0])
        return (wins / len(trades)) * 100

    wr_sota = get_wr(results_sota)
    wr_legacy = get_wr(results_legacy)
    
    missed = results_sota.get('shadow_signals', {}).get('filtered_by_ai', 0)
    v22_candidates = results_sota.get('shadow_signals', {}).get('v22_candidates', 0)
    
    print(f"PNL SOTA v3.1:  R$ {pnl_sota:>10.2f} ({trades_sota} trades, WR: {wr_sota:.1f}%)")
    print(f"PNL LEGACY V22: R$ {pnl_legacy:>10.2f} ({trades_legacy} trades, WR: {wr_legacy:.1f}%)")
    print(f"MELHORIA AI:    R$ {pnl_sota - pnl_legacy:>10.2f}")
    print("-" * 70)
    print(f"Sinais V22 Totais:     {v22_candidates}")
    print(f"Sinais Vetados pela IA: {missed}")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(run_audit_20_02())
