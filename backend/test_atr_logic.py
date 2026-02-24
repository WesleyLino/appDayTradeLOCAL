import sys
import os
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.risk_manager import RiskManager
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO)

def test_dynamic_atr():
    risk = RiskManager()
    
    # Simulação de ATR baixo (Mercado Calmo)
    atr_low = 80.0
    params_low = risk.get_order_params("WIN$", mt5.ORDER_TYPE_BUY, 120000, 1, current_atr=atr_low)
    print(f"\n--- ATR BAIXO ({atr_low}) ---")
    print(f"SL: {params_low['sl']} ({120000 - params_low['sl']} pts)")
    print(f"TP: {params_low['tp']} ({params_low['tp'] - 120000} pts)")
    
    # Simulação de ATR normal/alto (Pregão 23/02)
    atr_norm = 120.0
    params_norm = risk.get_order_params("WIN$", mt5.ORDER_TYPE_BUY, 120000, 1, current_atr=atr_norm)
    print(f"\n--- ATR NORMAL ({atr_norm}) ---")
    print(f"SL: {params_norm['sl']} ({120000 - params_norm['sl']} pts)")
    print(f"TP: {params_norm['tp']} ({params_norm['tp'] - 120000} pts)")

    # Simulação de ATR Extremo (Sanity Check)
    atr_high = 400.0
    params_high = risk.get_order_params("WIN$", mt5.ORDER_TYPE_BUY, 120000, 1, current_atr=atr_high)
    print(f"\n--- ATR EXTREMO WIN ({atr_high}) ---")
    print(f"SL: {params_high['sl']} ({120000 - params_high['sl']} pts)")
    print(f"TP: {params_high['tp']} ({params_high['tp'] - 120000} pts)")

    # Simulação WDO (Dólar)
    atr_wdo = 5.0
    params_wdo = risk.get_order_params("WDO$", mt5.ORDER_TYPE_BUY, 5400, 1, current_atr=atr_wdo)
    print(f"\n--- ATR WDO ({atr_wdo}) ---")
    print(f"SL: {params_wdo['sl']} ({5400 - params_wdo['sl']} pts)")
    print(f"TP: {params_wdo['tp']} ({params_wdo['tp'] - 5400} pts)")

    # Simulação WDO Extremo
    atr_wdo_high = 20.0
    params_wdo_h = risk.get_order_params("WDO$", mt5.ORDER_TYPE_BUY, 5400, 1, current_atr=atr_wdo_high)
    print(f"\n--- ATR WDO EXTREMO ({atr_wdo_high}) ---")
    print(f"SL: {params_wdo_h['sl']} ({5400 - params_wdo_h['sl']} pts)")
    print(f"TP: {params_wdo_h['tp']} ({params_wdo_h['tp'] - 5400} pts)")

if __name__ == "__main__":
    test_dynamic_atr()
