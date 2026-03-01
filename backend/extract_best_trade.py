import pandas as pd
import json
import os
import sys
from datetime import datetime

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def capture_best_trade():
    print("Capturando melhor trade para visualização...")
    
    # Carrega Sentimento Simulado
    sentiment_file = "backend/fev_sentiment_sim.json"
    sentiment_data = {}
    if os.path.exists(sentiment_file):
        with open(sentiment_file, "r") as f:
            raw_data = json.load(f)
            sentiment_data = {pd.to_datetime(k): v for k, v in raw_data.items()}

    backtester = BacktestPro(
        symbol="WIN$", 
        n_candles=15000,
        initial_balance=3000.0,
        use_ai_core=True,
        aggressive_mode=True,
        sentiment_stream=sentiment_data
    )
    
    df = await backtester.load_data()
    if df is None: return
    
    await backtester.run()
    
    if not backtester.trades:
        print("Nenhum trade encontrado.")
        return

    # Filtrar apenas trades de Fevereiro/2026
    feb_trades = [t for t in backtester.trades if t['entry_time'].month == 2 and t['entry_time'].year == 2026]
    
    if not feb_trades:
        print("Nenhum trade de Fevereiro encontrado. Usando o melhor disponível.")
        target_trade = max(backtester.trades, key=lambda x: x['pnl_fin'])
    else:
        target_trade = max(feb_trades, key=lambda x: x['pnl_fin'])
        
    print(f"Melhor Trade de Fevereiro: {target_trade['entry_time']} | Lucro: R$ {target_trade['pnl_fin']:.2f}")
    
    # Salvar detalhes para o relatório
    with open("backend/best_trade_info.json", "w") as f:
        json.dump(target_trade, f, default=str)

if __name__ == "__main__":
    import asyncio
    asyncio.run(capture_best_trade())
