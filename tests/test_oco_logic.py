
import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.risk_manager import RiskManager
import MetaTrader5 as mt5

class TestOCOLogic(unittest.TestCase):
    def setUp(self):
        self.risk = RiskManager()

    def test_win_buy_oco(self):
        # WIN Buy at 120000
        # Expected: SL 150 pts (119850), TP 300 pts (120300)
        params = self.risk.get_order_params("WINJ24", mt5.ORDER_TYPE_BUY_LIMIT, 120000.0, 1)
        
        self.assertEqual(params['sl'], 119850.0)
        self.assertEqual(params['tp'], 120300.0)
        self.assertEqual(params['type'], mt5.ORDER_TYPE_BUY_LIMIT)

    def test_wdo_sell_oco(self):
        # WDO Sell at 5000
        # Expected: SL 5 pts (5005), TP 10 pts (4990)
        params = self.risk.get_order_params("WDOJ24", mt5.ORDER_TYPE_SELL_LIMIT, 5000.0, 1)
        
        self.assertEqual(params['sl'], 5005.0)
        self.assertEqual(params['tp'], 4990.0)
        self.assertEqual(params['type'], mt5.ORDER_TYPE_SELL_LIMIT)

    def test_unknown_asset(self):
        # Unknown asset (e.g. PETR4) -> SL/TP 0
        params = self.risk.get_order_params("PETR4", mt5.ORDER_TYPE_BUY, 30.00, 100)
        self.assertEqual(params['sl'], 0.0)
        self.assertEqual(params['tp'], 0.0)

if __name__ == '__main__':
    unittest.main()
