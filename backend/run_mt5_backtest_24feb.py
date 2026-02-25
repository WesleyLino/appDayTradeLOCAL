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

async def run_mt5_analysis_24feb():
    # Configuracao de Logs
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("INICIANDO AUDITORIA DE PERFORMANCE MT5 (24/02/2026)")
    
    symbol = "WIN$"
    capital = 3000.0
    
    # 1. Configurar Backtest (Usando os Golden Params V22 via BacktestPro)
    tester = BacktestPro(
        symbol=symbol,
        n_candles=1000, # Buffer para o dia todo
        timeframe="M1",
        initial_balance=capital,
        base_lot=1
    )
    
    # 2. Carregar dados do MT5
    logging.info("Solicitando dados historicos do terminal MT5 para 24/02...")
    if not mt5.initialize():
        logging.error("Falha ao inicializar MT5")
        return
        
    # Range do dia 24
    utc_from = datetime(2026, 2, 24, 8, 0)
    utc_to = datetime(2026, 2, 24, 18, 30)
    
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        logging.error("Nenhum dado encontrado para o periodo solicitado.")
        mt5.shutdown()
        return
        
    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s')
    data.set_index('time', inplace=True)
    tester.data = data
    
    logging.info(f"Dados carregados: {len(data)} candles para analise.")

    # 3. Executar Simulacao
    await tester.run()
    
    # 4. Relatorio de Performance e Oportunidades
    shadow = tester.shadow_signals
    trades = tester.trades
    pnl = tester.balance - capital
    
    print("\n" + "="*60)
    print(f"RELATORIO DE PERFORMANCE SOTA: {symbol} (24/02/2026)")
    print("="*60)
    print(f"Capital Inicial : R$ {capital:.2f}")
    print(f"Lucro Liquido   : R$ {pnl:.2f} ({ (pnl/capital)*100 :.2f}%)")
    print(f"Saldo Final     : R$ {tester.balance:.2f}")
    print(f"Total de Trades : {len(trades)}")
    
    if len(trades) > 0:
        wins = len([t for t in trades if t['pnl_fin'] > 0])
        win_rate = (wins / len(trades)) * 100
        print(f"Assertividade   : {win_rate:.2f}% ({wins} Win / {len(trades)-wins} Loss)")
        
    print("\nANALISE DE OPORTUNIDADES (SHADOW TRADING):")
    print(f"- Sinais Potenciais Detectados: {shadow.get('v22_candidates', 0)}")
    print(f"- Trades Executados           : {len(trades)}")
    print(f"- Sinais Filtrados (Seguranca): {shadow.get('v22_candidates', 0) - len(trades)}")
    print(f"\nBreakdown de Filtros:")
    print(f"- Bloqueados por Fluxo        : {shadow.get('filtered_by_flux', 0)}")
    print(f"- Bloqueados por IA           : {shadow.get('filtered_by_ai', 0)}")
    print(f"- Falhas por Componentes      : {shadow.get('component_fail', {})}")
    
    print("\nDIAGNOSTICO PARA ASSEATIVIDADE:")
    if len(trades) < 3:
        print("-> Baixa frequencia de trades: Considere reduzir o 'cooldown_minutes' no v22_locked_params.json.")
    if shadow.get('filtered_by_flux', 0) > 2:
        print("-> O Filtro de Fluxo esta barrando entradas validas. Verifique a calibragem de 1.2x.")
    
    print("="*60 + "\n")

    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(run_mt5_analysis_24feb())
