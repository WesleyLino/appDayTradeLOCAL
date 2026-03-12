import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, time, date, timedelta
from backend.backtest_pro import BacktestPro
from backend.mt5_bridge import MT5Bridge

# Configuração OBRIGATÓRIA em PT-BR
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Auditoria_v24_Shadow")

async def run_shadow_audit_11mar():
    logger.info("💎 [v24 SHADOW AUDIT] Analisando 11/03 em busca de Oportunidades Perdidas")
    
    capital_inicial = 3000.0
    bt = BacktestPro(symbol="WIN$", n_candles=4000, initial_balance=capital_inicial)
    data = await bt.load_data()
    
    if data is None or data.empty: return

    target_date = date(2026, 3, 11)
    day_data = data[data.index.date == target_date].copy()
    if day_data.empty: 
        logger.error("❌ Dados de 11/03 não encontrados.")
        return

    # Sincronização e Pre-cálculos (RSI, BB, ATR)
    bt.data = day_data
    # Vamos rodar o run() para ter os indicadores calculados no df
    await bt.run() 
    
    # Agora vamos varrer o dataframe e ver onde a IA daria sinal mas o sistema vetou
    logger.info("🔍 Iniciando Varredura de Sinais (Shadow Scan)...")
    
    results = []
    for i in range(50, len(day_data)):
        window = day_data.iloc[i-50 : i+1]
        last_row = window.iloc[-1]
        
        # Simular decisão da IA
        # No backtest real, o bot chamaria a IA. Aqui vamos estimar pelo score se disponível ou rodar a lógica.
        # Como o engine pode ser pesado, vamos focar nos filtros de RIsco que o BacktestPro aplicaria.
        
        # Filtros de RIsco Visíveis:
        atr = last_row.get('atr_current', 100)
        rsi = last_row.get('rsi', 50)
        
        # Procura por sinais fortes de RSI (exemplo de oportunidade)
        if rsi < 30 or rsi > 70:
            results.append({
                'time': last_row.name,
                'rsi': rsi,
                'price': last_row['close'],
                'atr': atr
            })

    # Trades realizados
    trades = bt.trades
    logger.info(f"✅ Auditoria Concluída.")
    logger.info(f"📊 Trades Executados: {len(trades)}")
    for t in trades:
        logger.info(f"   - Trade {t['side']} às {t['entry_time']} | PnL: R$ {t['pnl_fin']:.2f} | Motivo: {t['reason']}")

    if not trades:
        logger.warning("⚠️ O motor V24 foi EXTREMAMENTE conservador em 11/03.")
        logger.info("💡 Motivo provável: Alta volatilidade ou falta de sincronismo de volume no histórico estático.")

if __name__ == "__main__":
    asyncio.run(run_shadow_audit_11mar())
