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

class LeveragedBacktester30(BacktestPro):
    async def load_data(self):
        logging.info(f"📥 Coletando dados de 30 DIAS (~12.000-15.000 candles M1) para {self.symbol}...")
        if not self.bridge.connect():
            return None
            
        import MetaTrader5 as mt5
        # 30 dias úteis tem aprox 15.000-18.000 minutos de pregão
        # Vamos pedir 20.000 para garantir
        rates = await asyncio.to_thread(mt5.copy_rates_from_pos, self.symbol, mt5.TIMEFRAME_M1, 0, 20000)
        
        if rates is None or len(rates) == 0:
            logging.error("❌ Falha na coleta de dados históricos.")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        # Filtrar apenas os últimos 30 dias do dataframe carregado
        # Ou simplesmente usar o carregado se for o range desejado
        logging.info(f"✅ {len(df)} candles carregados. Início: {df.index[0]} | Fim: {df.index[-1]}")
        return df

    def _close_trade(self, price, reason, time):
        pos = self.position
        pos['lots'] = 3 # Force 3 lots
        pnl_points = (price - pos['entry_price']) if pos['side'] == 'buy' else (pos['entry_price'] - price)
        mult = 0.20 # WIN 
        pnl_fin = pnl_points * pos['lots'] * mult
        
        self.balance += pnl_fin
        self.daily_pnl += pnl_fin
        
        # Log de trade para console (apenas se for importante ou resumido)
        # logging.info(f"Trade: {pos['side']} | PnL: R$ {pnl_fin:.2f}")

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

async def run_leveraged_30day():
    print("📈 Iniciando Stress Test 30 DIAS: 3 Contratos / Cap R$ 1000")
    
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print("❌ Erro: best_params_WIN.json não encontrado.")
        return

    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    backtester = LeveragedBacktester30(
        symbol="WIN$", 
        n_candles=20000, # Ignorado pelo override do load_data, mas passamos por compatibilidade
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        **params
    )
    
    await backtester.run()
    
    # Detalhamento Final
    print("\n--- PERFORMANCE SUMMARY (30 DAYS / 3 LOTS) ---")
    print("Saldo Inicial: R$ 1000.00")
    print(f"Saldo Final:   R$ {backtester.balance:.2f}")
    print(f"Lucro/Prejuízo: R$ {backtester.balance - 1000.0:.2f}")
    if backtester.trades:
        win_trades = [t for t in backtester.trades if t['pnl_fin'] > 0]
        wr = (len(win_trades) / len(backtester.trades)) * 100
        print(f"Total Trades:  {len(backtester.trades)}")
        print(f"Win Rate:      {wr:.1f}%")
        
        # Drawdown simples
        peaks = pd.Series([1000] + [t['pnl_fin'] for t in backtester.trades]).cumsum().expanding().max()
        current = pd.Series([1000] + [t['pnl_fin'] for t in backtester.trades]).cumsum()
        dd = (peaks - current).max()
        print(f"Max Drawdown Financeiro: R$ {dd:.2f}")
    else:
        print("⚠️ Nenhum trade realizado no período.")

if __name__ == "__main__":
    asyncio.run(run_leveraged_30day())
