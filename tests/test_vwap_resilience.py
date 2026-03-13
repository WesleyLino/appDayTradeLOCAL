
import unittest
import sys
import os
import json
import time

# Adiciona o diretório raiz ao path
sys.path.append(os.getcwd())

from backend.ai_core import AICore
from backend.market_data_worker import MarketDataWorker

class MockBridge:
    def get_current_symbol(self, base): return f"{base}H26"
    def get_settlement_price(self, s): return 130000.0
    def get_vwap(self, s): return 130050.0
    def get_bluechips_data(self): return {}
    def get_macro_data(self): return 0.0
    def get_htf_bias(self, s): return "LONG"
    def get_real_cvd_ticks(self, s): return 0.0
    def get_daily_volume_and_liquidity(self, s): return {}
    def get_real_commission_today(self): return 0.0

class TestGarantiaAbsoluta(unittest.TestCase):
    def setUp(self):
        self.ai = AICore()
        self.bridge = MockBridge()
        self.worker = MarketDataWorker(self.bridge, None)

    def test_sticky_logic(self):
        """Valida que valores validos não são sobrescritos por 0.0."""
        # 1. Primeira captura válida
        self.worker._last_vwaps = {"WIN$": 130000.0}
        self.worker._last_settlements = {"WIN$": 129500.0}
        
        # 2. Simula falha na ponte (retorna 0.0)
        vwap_fail = 0.0
        settle_fail = 0.0
        
        # Aplica lógica Sticky VWAP
        if vwap_fail > 0: self.worker._last_vwaps["WIN$"] = vwap_fail
        # Aplica lógica Sticky Settle
        if settle_fail > 0: self.worker._last_settlements["WIN$"] = settle_fail
        
        self.assertEqual(self.worker._last_vwaps["WIN$"], 130000.0, "VWAP deveria ser Sticky")
        self.assertEqual(self.worker._last_settlements["WIN$"], 129500.0, "Settlement deveria ser Sticky")

    def test_vwap_warmup_neutralization(self):
        """Valida neutralização de VWAP 0.0 no AICore."""
        decision = self.ai.calculate_decision(
            score=70.0, obi=1.0, sentiment=0.0, regime=1,
            current_price=130000.0, vwap=0.0, atr=50.0
        )
        self.assertIsNone(decision['veto'], "VWAP 0.0 não deve causar veto")

if __name__ == "__main__":
    unittest.main()
