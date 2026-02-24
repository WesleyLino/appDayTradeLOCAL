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

class LeveragedBacktester(BacktestPro):
    async def load_data(self):
        logging.info(f"📥 Coletando 600 candles do DIA ANTERIOR para {self.symbol}...")
        if not self.bridge.connect():
            return None
            
        import MetaTrader5 as mt5
        # Offset de 600 para pular o último dia e pegar o anterior
        rates = await asyncio.to_thread(mt5.copy_rates_from_pos, self.symbol, mt5.TIMEFRAME_M1, 600, 600)
        if rates is None or len(rates) == 0:
            logging.error("❌ Falha na coleta de dados históricos.")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        logging.info(f"✅ {len(df)} candles carregados (Dia anterior).")
        return df

    def _close_trade(self, price, reason, time):
        pos = self.position
        pos['lots'] = 3 # Force 3 lots
        pnl_points = (price - pos['entry_price']) if pos['side'] == 'buy' else (pos['entry_price'] - price)
        mult = 0.20 # WIN
        pnl_fin = pnl_points * pos['lots'] * mult
        self.balance += pnl_fin
        self.daily_pnl += pnl_fin
        self.trades.append({
            'entry_time': pos['time'],
            'exit_time': time,
            'side': pos['side'],
            'entry': pos['entry_price'],
            'exit': price,
            'lots': pos['lots'],
            'pnl_points': pnl_points,
            'pnl_fin': pnl_fin,
            'reason': reason
        })
        self.position = None

async def run_leveraged_prev_day():
    print("📈 Iniciando Verificação DIA ANTERIOR: 3 Contratos / Cap R$ 1000")
    
    params_path = "best_params_WIN.json"
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    backtester = LeveragedBacktester(
        symbol="WIN$", 
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        **params
    )
    
    await backtester.run()
    
    # Detalhamento para análise
    if backtester.trades:
        print("\n--- DETALHAMENTO DE TRADES ---")
        for i, trade in enumerate(backtester.trades):
            print(f"Trade {i+1}: {trade['side'].upper()} em {trade['entry_time']} | Saída: {trade['exit_time']} | Pontos: {trade['pnl_points']:.1f} | R$ {trade['pnl_fin']:.2f} ({trade['reason']})")
    else:
        print("\n⚠️ Nenhum trade realizado com os critérios Sniper neste dia.")

if __name__ == "__main__":
    asyncio.run(run_leveraged_prev_day())
