import asyncio
import pandas as pd
import logging
from datetime import datetime
import os
import glob
import sys
from backend.backtest_pro import BacktestPro

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_audit_18_02():
    target_date = "2026-02-18"
    logger.info(f"Iniciando Auditoria de Performance para {target_date}...")

    # 1. Localizar arquivo MASTER CSV
    csv_files = glob.glob("data/sota_training/training_WIN*_MASTER.csv")
    if not csv_files:
        logger.error("Arquivo MASTER CSV não encontrado!")
        return
    
    master_csv = csv_files[0]
    logger.info(f"Usando arquivo: {master_csv}")

    # 2. Carregar dados e filtrar pelo dia alvo
    try:
        df_full = pd.read_csv(master_csv)
        df_full['time'] = pd.to_datetime(df_full['time'])
        
        # Filtro expandido para garantir contexto
        mask = (df_full['time'] >= f"{target_date} 09:00:00") & (df_full['time'] <= f"{target_date} 18:30:00")
        df_day = df_full[mask].copy()
        
        if df_day.empty:
            logger.error(f"Sem dados para {target_date} no CSV!")
            return
        
        # O BacktestPro espera que 'time' seja o index ou esteja formatado corretamente
        df_day.set_index('time', inplace=True)
    except Exception as e:
        logger.error(f"Erro ao processar dados: {e}")
        return

    logger.info(f"Processando {len(df_day)} velas para {target_date}")

    # 3. Configurações de Backtest
    # Config para LEGACY (Sem AI Core)
    params_legacy = {
        "use_ai_core": False,
        "symbol": "WIN$",
        "lot_size": 1,
        "risk_reward": 2.0
    }

    # Config para SOTA v3.1 (Com AI Core e Calibragem Nova)
    params_sota = {
        "use_ai_core": True,
        "symbol": "WIN$",
        "lot_size": 1,
        "risk_reward": 2.0,
        "confidence_threshold": 0.7,
        "uncertainty_threshold": 0.25 # Calibragem v3.1
    }

    # 4. Executar Backtests
    logger.info("Executando backtest LEGACY...")
    bt_legacy = BacktestPro(**params_legacy)
    bt_legacy.data = df_day.copy()
    results_legacy = await bt_legacy.run()

    logger.info("Executando backtest SOTA v3.1...")
    bt_sota = BacktestPro(**params_sota)
    bt_sota.data = df_day.copy()
    results_sota = await bt_sota.run()

    # 5. Comparação de Métricas
    metrics = {
        "Date": target_date,
        "Legacy_PnL": results_legacy.get('total_pnl', 0),
        "Legacy_Trades": len(results_legacy.get('trades', [])),
        "SOTA_PnL": results_sota.get('total_pnl', 0),
        "SOTA_Trades": len(results_sota.get('trades', [])),
        "SOTA_WinRate": results_sota.get('win_rate', 0),
        "SOTA_Drawdown": results_sota.get('max_drawdown', 0),
        "Shadow_Signals": results_sota.get('shadow_signals', {}).get('filtered_by_ai', 0)
    }

    print("\n" + "="*50)
    print(f"RESULTADOS AUDITORIA {target_date}")
    print("="*50)
    print(f"PnL LEGACY:    R$ {metrics['Legacy_PnL']:.2f} ({metrics['Legacy_Trades']} trades)")
    print(f"PnL SOTA v3.1: R$ {metrics['SOTA_PnL']:.2f} ({metrics['SOTA_Trades']} trades)")
    print(f"Win Rate SOTA: {metrics['SOTA_WinRate']:.1f}%")
    print(f"Drawdown SOTA: R$ {metrics['SOTA_Drawdown']:.2f}")
    print(f"Sinais Vetados pela IA: {metrics['Shadow_Signals']}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_audit_18_02())
