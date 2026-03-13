import sys
import os
import asyncio
import logging
import pandas as pd
import numpy as np

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.bot_sniper_win import SniperBotWIN
from backend.risk_manager import RiskManager
from backend.ai_core import AICore

async def test_execution_logic():
    print("🚀 Iniciando Teste de Fluxo de Execução Sniper (SOTA v5)")
    
    # Mock Bridge
    class MockBridge:
        def __init__(self):
            import MetaTrader5 as mt5
            self.mt5 = mt5
        def check_connection(self): return True
        def get_current_symbol(self, base): return "WINJ24"
        def place_limit_order(self, *args, **kwargs):
            print(f"📦 ORDEM ENVIADA NO MOCK: {args} {kwargs}")
            class Result:
                def __init__(self): 
                    self.retcode = 10009 # DONE
                    self.order = 999999
                    self.comment = "MOCK_DONE"
            return Result()

    bot = SniperBotWIN()
    bot.bridge = MockBridge()
    bot.risk.dry_run = True # Segurança
    
    # Cenário 1: Regime de Tendência (Regime 1) + ATR Alto
    print("\n--- Cenário 1: Tendência de Alta + ATR 200 ---")
    current_price = 120000.0
    atr = 200.0
    regime = 1 # Tendência
    
    # Mock de tick para o bot
    class MockTick:
        def __init__(self, p): 
            self.bid = p - 5
            self.ask = p + 5
            self.last = p
    
    # Teste direto no Risk Manager primeiro
    params = bot.risk.get_order_params(
        "WINJ24", 
        bot.bridge.mt5.ORDER_TYPE_BUY_LIMIT, 
        current_price - 10, # Entrada um pouco abaixo (Limit)
        1, 
        current_atr=atr, 
        regime=regime
    )
    
    print(f"Preço Entrada: {params['price']}")
    print(f"SL: {params['sl']} (Esperado ~{current_price - 10 - 260} - mult 1.3)")
    print(f"TP: {params['tp']} (Esperado ~{current_price - 10 + 300} - mult 1.5 tendencia)")
    
    # Validação de Anti-Violinada (Price % 100 == 0)
    if params['sl'] % 100 == 0:
        print("❌ FALHA: SL caiu em número redondo!")
    else:
        print("✅ SUCESSO: SL evitou número redondo (Anti-Violinada)")

    # Cenário 2: Regime Lateral (Regime 0) + ATR 100
    print("\n--- Cenário 2: Lateralização + ATR 100 ---")
    regime = 0 # Lateral
    atr = 100.0
    
    params_lat = bot.risk.get_order_params(
        "WINJ24", 
        bot.bridge.mt5.ORDER_TYPE_SELL_LIMIT, 
        current_price + 10, 
        1, 
        current_atr=atr, 
        regime=regime
    )
    
    print(f"Preço Entrada: {params_lat['price']}")
    print(f"SL: {params_lat['sl']} (Esperado ~{current_price + 10 + 130} - mult 1.3)")
    print(f"TP: {params_lat['tp']} (Esperado ~{current_price + 10 - 80} - mult 0.8 lateral)")

    # Cenário 4: Momentum Bypass (IA Autoritária)
    print("\n--- Cenário 4: MOMENTUM BYPASS (IA x8 TP / x3 SL) ---")
    regime = 1
    atr = 150.0 # ATR base WIN
    tp_mult_institucional = 8.0
    sl_mult_institucional = 3.0
    
    params_momentum = bot.risk.get_order_params(
        "WINJ24", 
        bot.bridge.mt5.ORDER_TYPE_BUY_LIMIT, 
        current_price, 
        1, 
        current_atr=atr, 
        regime=regime,
        tp_multiplier=tp_mult_institucional,
        sl_multiplier=sl_mult_institucional
    )
    
    print(f"Preço Entrada: {params_momentum['price']}")
    # No SOTA, se houver ATR, o cálculo é ATR * RegimeMult * MomentumMult
    expected_tp_dist = (atr * 1.5) * tp_mult_institucional # Regime 1 TP Mult = 1.5
    expected_sl_dist = (atr * 1.3) * sl_mult_institucional # Regime 1 SL Mult = 1.3
    
    print(f"SL: {params_momentum['sl']} (Distância: {abs(params_momentum['sl'] - current_price):.0f} pts | Esperado: ~{expected_sl_dist})")
    print(f"TP: {params_momentum['tp']} (Distância: {abs(params_momentum['tp'] - current_price):.0f} pts | Esperado: ~{expected_tp_dist})")

    if abs(params_momentum['tp'] - current_price) >= expected_tp_dist:
        print("✅ SUCESSO: TP Institucional expandido corretamente.")
    else:
        print("❌ FALHA: TP não atingiu a escala institucional.")
        
    if abs(params_momentum['sl'] - current_price) >= (expected_sl_dist - 20):
        print("✅ SUCESSO: SL Institucional expandido corretamente (com tolerância Anti-Violinada).")
    else:
        print("❌ FALHA: SL não atingiu a escala institucional.")

    print("\n✅ Teste de Lógica de Execução Concluído!")

if __name__ == "__main__":
    asyncio.run(test_execution_logic())
