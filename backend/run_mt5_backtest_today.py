import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os
import MetaTrader5 as mt5

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_mt5_analysis():
    # Configuracao de Logs
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("INICIANDO ANALISE HISTORICA MT5 (27/02/2026) - SOTA PRO")
    
    symbol = "WIN$"
    capital = 3000.0
    
    # 1. Configurar Backtest
    tester = BacktestPro(
        symbol=symbol,
        n_candles=1000, # Aumentado para garantir o dia todo
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=True
    )
    
    # Parametros otimizados
    tester.opt_params['vol_spike_mult'] = 1.0
    tester.opt_params['use_flux_filter'] = True
    tester.opt_params['confidence_threshold'] = 0.70
    
    # 2. Carregar dados do MT5
    logging.info("Solicitando dados historicos do terminal MT5...")
    data = await tester.load_data()
    
    if data is None or data.empty:
        logging.error("Falha ao carregar dados do MT5.")
        return

    # Filtrar apenas para o dia de hoje (27/02/2026)
    today = datetime(2026, 2, 27).date()
    data = data[data.index.date == today]
    
    if data.empty:
        logging.error("Nenhum dado encontrado para o dia de hoje.")
        return

    logging.info(f"Dados carregados: {len(data)} candles para analise.")

    # 3. Executar Simulacao
    await tester.run()
    
    # 4. Relatorio de Performance e Oportunidades
    shadow = tester.shadow_signals
    trades = tester.trades
    
    print("\n" + "="*50)
    print("RELATORIO DE PERFORMANCE (MT5 REAL-DATA) - SOTA PRO - 27/02/2026")
    print("="*50)
    print(f"Saldo Inicial:   RS {capital:.2f}")
    print(f"Saldo Final:     RS {tester.balance:.2f}")
    print(f"PnL Total:       RS {tester.balance - capital:.2f}")
    print(f"Numero de Trades: {len(trades)}")
    
    if len(trades) > 0:
        win_rate = (len([t for t in trades if t['pnl_fin'] > 0]) / len(trades)) * 100
        print(f"Assertividade Geral: {win_rate:.2f}%")
        
        # Analise Comprada vs Vendida
        buy_trades = [t for t in trades if t['side'] == 'buy']
        sell_trades = [t for t in trades if t['side'] == 'sell']
        
        buy_pnl = sum([t['pnl_fin'] for t in buy_trades])
        sell_pnl = sum([t['pnl_fin'] for t in sell_trades])
        
        buy_wr = (len([t for t in buy_trades if t['pnl_fin'] > 0]) / len(buy_trades) * 100) if buy_trades else 0
        sell_wr = (len([t for t in sell_trades if t['pnl_fin'] > 0]) / len(sell_trades) * 100) if sell_trades else 0
        
        print("\n--- ANÁLISE POR DIREÇÃO ---")
        print(f"COMPRAS (BUY):  {len(buy_trades)} trades | PnL: RS {buy_pnl:.2f} | Assertividade: {buy_wr:.2f}%")
        print(f"VENDAS (SELL): {len(sell_trades)} trades | PnL: RS {sell_pnl:.2f} | Assertividade: {sell_wr:.2f}%")
        
    print("\nANALISE DE OPORTUNIDADES (SHADOW):")
    print(f"- Sinais V22 Detectados:      {shadow.get('v22_candidates', 0)}")
    print(f"- Sinais Enviados p/ Filtro:  {shadow.get('total_missed', 0) + len(trades)}")
    print(f"- Negados pela IA:            {shadow.get('filtered_by_ai', 0)}")
    print(f"- Negados pelo Fluxo:         {shadow.get('filtered_by_flux', 0)}")
    print(f"- Falhas Componentes:         {shadow.get('component_fail', {})}")
    
    print("\nSUGESTOES DE MELHORIA:")
    if shadow.get('filtered_by_flux', 0) > 3:
        print("-> O Filtro de Fluxo esta retendo sinais. Tente 'flux_imbalance_threshold' -1 para desativar.")
    if shadow.get('component_fail', {}).get('volume', 0) > 3:
        print("-> Volatilidade alta esta bloqueando entradas. Ajuste 'vol_spike_mult' para 0.8 se desejar mais risco.")
    if shadow.get('filtered_by_ai', 0) > 3:
        print("-> A IA está muito restritiva. Verifique o 'confidence_threshold' (atualmente 0.70).")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    asyncio.run(run_mt5_analysis())
