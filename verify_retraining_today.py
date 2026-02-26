import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os
import MetaTrader5 as mt5

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from backend.backtest_pro import BacktestPro

async def run_mt5_analysis():
    # Configuracao de Logs
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("INICIANDO ANALISE HISTORICA MT5 (25/02/2026)")
    
    symbol = "WIN$"
    capital = 3000.0
    
    # 1. Configurar Backtest
    tester = BacktestPro(
        symbol=symbol,
        n_candles=1000, 
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=True # Ativado para testar os novos pesos
    )
    
    # Parametros otimizados conforme V22
    tester.opt_params['vol_spike_mult'] = 1.0
    tester.opt_params['use_flux_filter'] = True
    tester.opt_params['confidence_threshold'] = 0.70
    
    # 2. Carregar dados do MT5
    logging.info("Solicitando dados historicos do terminal MT5...")
    data = await tester.load_data()
    
    if data is None or data.empty:
        logging.error("Falha ao carregar dados do MT5.")
        return

    # Filtrar apenas para o dia de hoje (25/02/2026)
    today = datetime(2026, 2, 25).date()
    data = data[data.index.date == today]
    
    if data.empty:
        logging.error("Nenhum dado encontrado para o dia de hoje (25/02/2026).")
        return

    logging.info(f"Dados carregados: {len(data)} candles para analise.")

    # 3. Executar Simulacao
    await tester.run()
    
    # 4. Relatorio de Performance
    trades = tester.trades
    
    print("\n" + "="*50)
    print("RELATORIO DE PERFORMANCE POS-REITREINO (25/02/2026)")
    print("="*50)
    print(f"Saldo Inicial:   RS {capital:.2f}")
    print(f"Saldo Final:     RS {tester.balance:.2f}")
    print(f"PnL Total:       RS {tester.balance - capital:.2f}")
    print(f"Numero de Trades: {len(trades)}")
    
    if len(trades) > 0:
        win_rate = (len([t for t in trades if t['pnl_fin'] > 0]) / len(trades)) * 100
        print(f"Assertividade:   {win_rate:.2f}%")
    
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(run_mt5_analysis())
