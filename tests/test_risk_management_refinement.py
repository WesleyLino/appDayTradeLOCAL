import unittest
import sys
import os

# Adiciona o diretório raiz do projeto ao PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.risk_manager import RiskManager

class TestRiskManagementRefinement(unittest.TestCase):
    def setUp(self):
        self.risk = RiskManager()

    def test_validate_market_condition_regime_noise(self):
        """Teste: Rejeita se Regime = 2 (Ruído/Consolidação Caótica)"""
        regime = 2
        volatility = 100.0 # Volatilidade normal
        
        result = self.risk.validate_market_condition(regime, volatility)
        
        self.assertFalse(result["allowed"])
        self.assertIn("NOISE/VOLATILE (2)", result["reason"])

    def test_validate_market_condition_extreme_volatility(self):
        """Teste: Rejeita se Volatilidade > Limite (Pânico)"""
        regime = 1 # Tendência (OK)
        volatility = 2000.0 # Acima do threshold de 1000.0
        
        result = self.risk.validate_market_condition(regime, volatility)
        
        self.assertFalse(result["allowed"])
        self.assertIn("Extreme Volatility", result["reason"])

    def test_validate_market_condition_success(self):
        """Teste: Aceita se Regime OK e Volatilidade OK"""
        regime = 1 # Tendência
        volatility = 100.0 # Normal
        
        result = self.risk.validate_market_condition(regime, volatility)
        
        self.assertTrue(result["allowed"])
        self.assertIn("Market Condition OK", result["reason"])

    def test_validate_market_condition_undefined_regime(self):
        """Teste: Aceita Regime 0 (Indefinido) se volatilidade ok"""
        regime = 0
        volatility = 50.0
        
        result = self.risk.validate_market_condition(regime, volatility)
        
        self.assertTrue(result["allowed"])

if __name__ == '__main__':
    unittest.main()
