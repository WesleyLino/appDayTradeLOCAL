
import asyncio
import logging
import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# Adiciona diretório raiz ao path para importações locais
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

# [REGRA-PTBR] Configuração de Logging em Português
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TesteFocado27Fev")

async def test_focused_27feb():
    logger.info("🤖 [SOTA-v24] Iniciando Teste Focado de 1 Dia: 27/02/2026")
    
    # 1. Inicializar MetaTrader 5
    if not mt5.initialize():
        logger.error("❌ Falha crítica ao inicializar o terminal MT5.")
        return

    symbol = "WIN$"
    timeframe = mt5.TIMEFRAME_M1
    
    # Datas: 27/02 e o dia útil anterior (26/02) para Warm-up necessário para médias e indicadores
    date_from = datetime(2026, 2, 26, 9, 0) 
    date_to = datetime(2026, 2, 27, 18, 0)
    
    logger.info(f"📊 Coletando dados focado: {date_from} até {date_to}...")
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    
    if rates is None or len(rates) == 0:
        logger.error("❌ Falha ao coletar dados do MT5.")
        mt5.shutdown()
        return

    df_rates = pd.DataFrame(rates)
    df_rates['time'] = pd.to_datetime(df_rates['time'], unit='s')
    df_rates.set_index('time', inplace=True)
    
    # [v24.4] Adicionando colunas de Microestrutura (Injeção necessária para modelo ONNX de 8 canais)
    # Calculamos valores aproximados baseados no candle para o backtest histórico simplificado
    df_rates['cvd_normal'] = (df_rates['close'] - df_rates['open']) / (df_rates['high'] - df_rates['low']).replace(0, 1)
    df_rates['ofi_normal'] = df_rates['tick_volume'] * df_rates['cvd_normal']
    df_rates['trap_index'] = 0.0 # Valor neutro para backtest
    
    logger.info(f"✅ {len(df_rates)} candles para simulação (8 canais preparados).")

    # 2. Configurar BacktestPro com Injeção de Dados
    bt = BacktestPro(symbol=symbol, n_candles=len(df_rates))
    bt.data = df_rates
    
    async def dummy_load():
        return bt.data
    bt.load_data = dummy_load

    # Carregar SOTA v24 Locked Params
    params_path = 'backend/v24_locked_params.json'
    if not os.path.exists(params_path):
        params_path = 'backend/v22_locked_params.json'
        
    try:
        with open(params_path, 'r') as f:
            config = json.load(f)
        sota_params = config.get("strategy_params", config)
    except:
        sota_params = {}

    # Aplicar configurações SOTA protegidas
    bt.opt_params.update(sota_params)
    bt.opt_params['confidence_level'] = sota_params.get('confidence_threshold', 0.60)
    bt.opt_params['enable_news_filter'] = False # Desativado para teste histórico puro

    # 3. Executar Simulação
    logger.info("🚀 Executando simulação focado no dia 27/02...")
    await bt.run()
    
    # 4. Resultados Específicos do Dia
    target_date = datetime(2026, 2, 27).date()
    trades_day = [t for t in bt.trades if t['entry_time'].date() == target_date]
    pnl_day = sum(t.get('pnl_fin', 0) for t in trades_day)
    
    logger.info("\n" + "="*60)
    logger.info(f"🏆 RESULTADO FOCADO - 27/02/2026")
    logger.info(f"💰 PnL do Dia: R$ {pnl_day:.2f} | Total Trades: {len(trades_day)}")
    logger.info("="*60)

    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(test_focused_27feb())
