import asyncio
import pandas as pd
import numpy as np
import logging
from backend.backtest_pro import BacktestPro
from datetime import datetime

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def validate_sota_v5():
    logging.info("🚀 INICIANDO VALIDAÇÃO SOTA v5 (The Precision Era)")
    
    # Teste 1: Janela de Abertura (09:00 - 10:00) 
    # n=120 para focar nas primeiras 2 horas
    bt_v5 = BacktestPro(
        symbol="WIN$",
        n_candles=200, 
        use_ai_core=True,
        initial_balance=3000.0,
        dynamic_lot=True
    )
    
    report = await bt_v5.run()
    
    print("\n" + "="*50)
    print("RESULTADOS SOTA v5 - AUDITORIA DE PRECISÃO")
    print("="*50)
    print(f"Saldo Final:   R$ {report['final_balance']:.2f}")
    print(f"Lucro Líquido: R$ {report['total_pnl']:.2f}")
    print(f"Win Rate:      {report['win_rate']:.1f}%")
    print(f"Trades Totais: {len(report['trades'])}")
    
    # Verificar vetos específicos do v5
    vetos = [t.get('veto_reason') for t in report.get('trades_shadow', [])]
    opening_vetos = vetos.count("HIGH_UNCERTAINTY_FAILSAFE") # Na abertura o rigor é maior, cai aqui
    spread_vetos = vetos.count("HIGH_SPREAD_VETO")
    
    print(f"Vetos por Rigor de Abertura (Est): {opening_vetos}")
    print(f"Vetos por Spread Alto:           {spread_vetos}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(validate_sota_v5())
