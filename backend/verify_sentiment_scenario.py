import asyncio
import pandas as pd
import os
import sys
import datetime as dt_mod
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_sentiment_scenario():
    print("\n" + "="*50)
    print("🚀 SCENARIO: 5-DAY TEST + TOXIC SENTIMENT SHOCK")
    print("OBJETIVO: Validar o 'Veto' de segurança em R$ 1000")
    print("="*50)

    # 1. Configuração (Sniper Champion)
    config = {
        'rsi_period': 14,
        'bb_dev': 2.2,
        'sl_dist': 150.0,
        'tp_dist': 400.0,
        'vol_spike_mult': 1.5,
        'confidence_threshold': 0.4,
        'initial_balance': 1000.0
    }

    # 2. Inicializar Backtester
    bt = BacktestPro(symbol="WIN$", n_candles=1500, **config)
    df = await bt.load_data()
    
    if df is None: return

    # 3. Rodar uma vez para pegar os tempos dos trades
    print("⏳ Coletando timestamps de trades técnicos...")
    await bt.run()
    
    trade_times = []
    if hasattr(bt, 'trades') and bt.trades:
        trade_times = [t['entry_time'] for t in bt.trades]
        print(f"✅ Encontrados {len(trade_times)} trades técnicos.")
    else:
        print("❌ Nenhum trade encontrado para injetar sentimento.")
        return

    # 4. Injetar sentimento negativo NO PRIMEIRO TRADE
    target_time = trade_times[0]
    sentiment_data = {}
    print(f"⚠️ Injetando 'Relatório Bombástico' (Score -0.9) em: {target_time}")
    
    # Injeta sentimento negativo por 30 minutos em volta do trade
    for i in range(-15, 15):
        t = target_time + timedelta(minutes=i)
        sentiment_data[t] = -0.9
    
    bt.sentiment_stream = sentiment_data
    bt.balance = 1000.0 # Reset balance
    bt.trades = []      # Reset trades
    bt.equity_curve = []

    # 5. Rodar Simulação Final
    print("⏳ Executando simulação Final (com Veto)...")
    await bt.run()

    print("\n✅ CENÁRIO FINALIZADO.")
    print("Verifique os logs acima para ver se o trade foi 'VETADO POR SENTIMENTO'.")

if __name__ == "__main__":
    asyncio.run(run_sentiment_scenario())
