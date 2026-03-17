"""
Debug: verificar estrutura exata retornada pelo MT5 para uma data específica.
"""
import MetaTrader5 as mt5
import numpy as np
from datetime import datetime

mt5.initialize()

# Testar com uma data que sabemos que funciona (27/02)
d_from = datetime(2026, 2, 26, 9, 0)
d_to   = datetime(2026, 2, 26, 10, 0)
rates = mt5.copy_rates_range("WIN$", mt5.TIMEFRAME_M1, d_from, d_to)

print(f"Tipo retornado: {type(rates)}")
if rates is not None:
    print(f"Len: {len(rates)}")
    print(f"dtype: {rates.dtype}")
    print(f"dtype.names: {rates.dtype.names}")
    print(f"Primeiro registro: {rates[0]}")

# Testar uma data de feriado (exemplo)
d_from2 = datetime(2025, 12, 25, 9, 0)
d_to2   = datetime(2025, 12, 25, 10, 0)
rates2 = mt5.copy_rates_range("WIN$", mt5.TIMEFRAME_M1, d_from2, d_to2)
print(f"\nDia 25/12 (feriado): rates={rates2}")

# Testar copy_rates_from_pos como alternativa
print("\nTestando copy_rates_from_pos (mais robusto):")
rates3 = mt5.copy_rates_from_pos("WIN$", mt5.TIMEFRAME_M1, 0, 500)
print(f"Tipo: {type(rates3)}, Len: {len(rates3) if rates3 is not None else 'None'}")
if rates3 is not None:
    print(f"dtype.names: {rates3.dtype.names}")

mt5.shutdown()
