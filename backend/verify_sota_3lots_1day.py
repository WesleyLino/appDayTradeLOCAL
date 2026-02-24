import asyncio
import json
import os
import sys
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

class LeveragedBacktester(BacktestPro):
    # Override pnl calculation to use 3 lots if dynamic_lot is False
    def _close_trade(self, price, reason, time):
        pos = self.position
        # Force 3 lots as requested by user
        pos['lots'] = 3
        
        pnl_points = (price - pos['entry_price']) if pos['side'] == 'buy' else (pos['entry_price'] - price)
        mult = 0.20 # WIN 
        pnl_fin = pnl_points * pos['lots'] * mult
        
        if pnl_fin > 0:
            self.consecutive_wins += 1
        else:
            self.consecutive_wins = 0

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

async def run_leveraged_verification():
    print("📈 Iniciando Verificação Alavancada: 3 Contratos / Cap R$ 1000")
    
    params_path = "best_params_WIN.json"
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # Configurar Backtester com 3 contratos (via classe estendida)
    backtester = LeveragedBacktester(
        symbol="WIN$", 
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        **params
    )
    
    await backtester.run()
    
    print("\n✅ Verificação Alavancada Concluída.")

if __name__ == "__main__":
    asyncio.run(run_leveraged_verification())
