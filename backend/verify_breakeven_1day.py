import asyncio
import json
import os
import sys
import pandas as pd
import logging
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

class BreakevenBacktester(BacktestPro):
    async def load_data(self):
        logging.info(f"📥 Coletando 600 candles do DIA ANTERIOR (Loss Day) para {self.symbol}...")
        if not self.bridge.connect():
            return None
            
        import MetaTrader5 as mt5
        # Offset 0 para pegar o dia mais recente
        rates = await asyncio.to_thread(mt5.copy_rates_from_pos, self.symbol, mt5.TIMEFRAME_M1, 0, 600)
        if rates is None or len(rates) == 0:
            logging.error("❌ Falha na coleta de dados históricos.")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df

async def run_breakeven_verification():
    print("📈 Verificando Eficácia do BREAKEVEN (Trigger: 70 pts)")
    
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print("❌ Erro: best_params_WIN.json não encontrado.")
        return

    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # Teste com Breakeven ON (Default agora é 70 pts no BacktestPro)
    print("\n--- TESTE COM BREAKEVEN (70 pts) ---")
    bt_on = BreakevenBacktester(
        symbol="WIN$", 
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True, # Trailing stop ON
        use_flux_filter=True,
        be_trigger=70.0,
        be_lock=0.0,
        **params
    )
    await bt_on.run()
    
    if bt_on.trades:
        for i, trade in enumerate(bt_on.trades):
            print(f"Trade {i+1}: {trade['side'].upper()} | Pts: {trade['pnl_points']} | Motivo: {trade['reason']}")
    else:
        print("Nenhum trade realizado.")

    # Teste com Breakeven OFF (Trigger muito alto para simular OFF)
    print("\n--- TESTE SEM BREAKEVEN (Benchmark) ---")
    bt_off = BreakevenBacktester(
        symbol="WIN$", 
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        be_trigger=9999.0, # Simula OFF
        **params
    )
    await bt_off.run()

    if bt_off.trades:
        for i, trade in enumerate(bt_off.trades):
            print(f"Trade {i+1}: {trade['side'].upper()} | Pts: {trade['pnl_points']} | Motivo: {trade['reason']}")

if __name__ == "__main__":
    # Reduzir verbosidade para ver logs de trade
    logging.getLogger().setLevel(logging.WARNING)
    asyncio.run(run_breakeven_verification())
