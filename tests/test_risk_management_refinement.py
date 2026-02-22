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
        symbol = "WINJ24"
        avg_atr = 100.0
        
        result = self.risk.validate_market_condition(symbol, regime, volatility, avg_atr)
        
        self.assertFalse(result["allowed"])
        self.assertIn("NOISE/VOLATILE (2)", result["reason"])

    def test_validate_market_condition_extreme_volatility(self):
        """Teste: Rejeita se Volatilidade > Limite (Pânico)"""
        regime = 1 # Tendência (OK)
        volatility = 2000.0 # Acima do threshold de 500.0 (WIN)
        symbol = "WINJ24"
        avg_atr = 100.0
        
        result = self.risk.validate_market_condition(symbol, regime, volatility, avg_atr)
        
        self.assertFalse(result["allowed"])
        # Pode falhar por Circuit Breaker (>3x) ou Panic Threshold (>500)
        # O código verifica Circuit Breaker primeiro, depois Panic.
        # 2000 > 3*100 (300) -> Circuit Breaker fail.
        # Mensagem esperada: "Circuit Breaker" ou "Extreme Volatility"
        # O código atual usa "Extreme Volatility" para Panic Threshold.
        # Vamos verificar se falha por um dos dois.
        self.assertTrue("Circuit Breaker" in result["reason"] or "Extreme Volatility" in result["reason"])

    def test_validate_market_condition_success(self):
        """Teste: Aceita se Regime OK e Volatilidade OK"""
        regime = 1 # Tendência
        volatility = 100.0 # Normal
        symbol = "WINJ24"
        avg_atr = 100.0
        
        result = self.risk.validate_market_condition(symbol, regime, volatility, avg_atr)
        
        self.assertTrue(result["allowed"])
        self.assertIn("Market Condition OK", result["reason"])

    def test_validate_market_condition_undefined_regime(self):
        """Teste: Aceita Regime 0 (Indefinido) se volatilidade ok"""
        regime = 0
        volatility = 50.0
        symbol = "WINJ24"
        avg_atr = 50.0
        
        result = self.risk.validate_market_condition(symbol, regime, volatility, avg_atr)
        
        self.assertTrue(result["allowed"])

if __name__ == '__main__':
    unittest.main()
