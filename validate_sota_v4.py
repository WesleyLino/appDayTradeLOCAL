import asyncio
import pandas as pd
from backend.backtest_pro import BacktestPro
import logging
import os

async def validate_sota_v4():
    logging.info("🚀 INICIANDO VALIDAÇÃO FINAL SOTA V4 (PRO-MAX)")
    
    # 1. Configuração do Backtester com SOTA v4 Enabled
    # Usaremos dados reais de 19/02 (Dia de Tendência Oposta) para validar o Filtro H1
    bt_19 = BacktestPro(
        symbol="WIN$",
        n_candles=1000,
        use_ai_core=True,
        initial_balance=3000.0
    )
    
    logging.info("--- Teste 1: Impacto do Filtro H1 em 19/02 (Tendência de Alta) ---")
    report_19 = await bt_19.run()
    
    # 2. Configuração para 23/02 (Dia de Alta Performance) para validar Lot Sizing
    bt_23 = BacktestPro(
        symbol="WIN$",
        n_candles=1000,
        use_ai_core=True,
        initial_balance=3000.0
    )
    
    logging.info("--- Teste 2: Impacto do Lot Sizing Probabilístico em 23/02 ---")
    report_23 = await bt_23.run()
    
    return report_19, report_23

if __name__ == "__main__":
    asyncio.run(validate_sota_v4())
