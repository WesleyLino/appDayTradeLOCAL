import sys
import os
import pandas as pd
import numpy as np
import logging

# Adicionar diretório atual ao path
sys.path.append(os.getcwd())

# Mock Logic for MT5 constants if module is missing or fails
# We try to import, if fail, we define constants manually for testing
try:
    import MetaTrader5 as mt5
    TICK_FLAG_BUY = mt5.TICK_FLAG_BUY
    TICK_FLAG_SELL = mt5.TICK_FLAG_SELL
except:
    print("⚠️ Módulo MetaTrader5 não encontrado ou erro. Usando constantes Mock.")
    TICK_FLAG_BUY = 32  # Standard MT5 constant
    TICK_FLAG_SELL = 64 # Standard MT5 constant
    
    # Mock class to allow import of microstructure
    class MockMT5:
        TICK_FLAG_BUY = 32
        TICK_FLAG_SELL = 64
    sys.modules['MetaTrader5'] = MockMT5()

from backend.microstructure import MicrostructureAnalyzer

def test_cvd_calculation():
    print("\n--- Testando MicrostructureAnalyzer (CVD) ---")
    analyzer = MicrostructureAnalyzer()
    
    # Criar DataFrame Mock de Ticks
    # Flags combinados (ex: TICK_FLAG_BUY | TICK_FLAG_ASK)
    data = {
        'time': pd.to_datetime(['2024-01-01 10:00:01', '2024-01-01 10:00:02', '2024-01-01 10:00:03']),
        'flags': [
            TICK_FLAG_BUY,       # Compra Agressiva
            TICK_FLAG_SELL,      # Venda Agressiva
            TICK_FLAG_BUY | 2    # Compra Agressiva + Outra flag (ex: BID)
        ],
        'volume_real': [100.0, 50.0, 200.0]
    }
    df = pd.DataFrame(data)
    
    # Cálculo Esperado:
    # Buy Vol = 100 + 200 = 300
    # Sell Vol = 50
    # CVD = 300 - 50 = 250
    
    print("Dados Mock:")
    print(df)
    
    cvd = analyzer.calculate_cvd(df)
    print(f"\nCVD Calculado: {cvd}")
    print(f"CVD Esperado: 250.0")
    
    if cvd == 250.0:
        print("✅ Cálculo de CVD CORRETO!")
    else:
        print("❌ ERRO no cálculo de CVD!")

    # Teste Vazio
    cvd_empty = analyzer.calculate_cvd(pd.DataFrame())
    print(f"CVD Empty: {cvd_empty} (Esperado 0.0) -> {'OK' if cvd_empty == 0.0 else 'FAIL'}")

if __name__ == "__main__":
    test_cvd_calculation()
