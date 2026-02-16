
import unittest
import sys
import os

# Adiciona o diretório raiz ao path para importar modulos do backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.ai_core import AICore

class TestAIDecision(unittest.TestCase):
    def setUp(self):
        self.ai = AICore()

    def test_strong_buy_signal(self):
        """Testa um cenário de compra forte onde todos indicadores são positivos."""
        obi = 0.9          # Compra forte no book
        sentiment = 0.8    # Notícias otimistas
        patchtst = 0.9     # Previsão de alta (Norm: (0.9-0.5)*2 = 0.8)
        
        # Norm PatchTST = 0.8
        # Composite = (0.9 * 0.4) + (0.8 * 0.4) + (0.8 * 0.2)
        # Composite = 0.36 + 0.32 + 0.16 = 0.84
        # Score = 84.
        
        decision = self.ai.calculate_decision(obi, sentiment, patchtst)
        
        print(f"\nStrong Buy Case: {decision}")
        self.assertEqual(decision['direction'], "BUY")
        self.assertAlmostEqual(decision['score'], 84.0, delta=1.0)

    def test_super_strong_sell_signal(self):
        """Testa um cenário de venda extrema para atingir > 85."""
        obi = -0.9         # Venda forte
        sentiment = -0.9   # Pânico
        patchtst = 0.05    # Previsão de queda forte (Norm: (0.05-0.5)*2 = -0.9)
        
        # Norm PatchTST = -0.9
        # Composite = (-0.9 * 0.4) + (-0.9 * 0.4) + (-0.9 * 0.2) = -0.9
        # Score = 90.0
        
        decision = self.ai.calculate_decision(obi, sentiment, patchtst)
        
        print(f"\nSuper Sell Case: {decision}")
        self.assertEqual(decision['direction'], "SELL")
        self.assertGreaterEqual(decision['score'], 85.0)

    def test_neutral_signal(self):
        """Testa cenário neutro."""
        obi = 0.1
        sentiment = 0.0
        patchtst = 0.5 # Norm 0.0
        
        # Composite = (0.1 * 0.4) + 0 + 0 = 0.04
        # Score = 4.0
        
        decision = self.ai.calculate_decision(obi, sentiment, patchtst)
        print(f"\nNeutral Case: {decision}")
        self.assertEqual(decision['direction'], "NEUTRAL") # Score < 10
        self.assertLess(decision['score'], 10.0)

    def test_conflicting_signal(self):
        """Testa conflito: Book Venda vs Previsão Alta."""
        obi = -0.8         # Venda
        sentiment = 0.0    # Neutro
        patchtst = 0.9     # Alta (Norm 0.8)
        
        # Composite = (-0.8 * 0.4) + (0.8 * 0.4) + 0 
        #           = -0.32 + 0.32 + 0 = 0.0
        
        decision = self.ai.calculate_decision(obi, sentiment, patchtst)
        print(f"\nConflicting Case: {decision}")
        self.assertTrue(decision['score'] < 10)

if __name__ == '__main__':
    unittest.main()
