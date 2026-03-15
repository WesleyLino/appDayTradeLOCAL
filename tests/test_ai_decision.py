import unittest
import sys
import os

# Adiciona o diretório raiz ao path para importar modulos do backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.ai_core import AICore


class TestAIDecision(unittest.TestCase):
    def setUp(self):
        self.ai = AICore()
        # Mock Meta-Learner to avoid dependency on local model file during unit tests
        # Setting model to None triggers the fallback: final_score = ai_score_raw
        from unittest.mock import MagicMock

        self.ai.meta_learner = MagicMock()
        self.ai.meta_learner.model = None

    def test_strong_buy_signal(self):
        """Testa um cenário de compra forte onde todos indicadores são positivos."""
        obi = 1.0  # Compra extrema no book (v30/v40)
        sentiment = 0.9  # Notícias muito otimistas
        patchtst = 0.95  # Previsão de alta agressiva

        # Norm PatchTST = 0.8
        # Composite = (0.9 * 0.3) + (0.8 * 0.5) + (0.8 * 0.2)
        # Weights (regime 0): obi 0.3, patch 0.5, sent 0.2?
        # Wait, strictly following ai_core logic:
        # regime default is 0? No, check ai.calculate_decision default.

        decision = self.ai.calculate_decision(obi, sentiment, patchtst)

        print(f"\nStrong Buy Case: {decision}")
        self.assertEqual(decision["direction"], "BUY")
        # Logic: (Composite + 1) * 50.
        # If High, Score > 50.
        self.assertGreater(decision["score"], 55.0)

    def test_super_strong_sell_signal(self):
        """Testa um cenário de venda extrema."""
        obi = -0.9  # Venda forte
        sentiment = -0.9  # Pânico
        patchtst = 0.05  # Previsão de queda forte

        decision = self.ai.calculate_decision(obi, sentiment, patchtst)

        print(f"\nSuper Sell Case: {decision}")
        self.assertEqual(decision["direction"], "SELL")
        # Logic: (Composite + 1) * 50.
        # If Low (negative composite), Score < 50.
        self.assertLess(decision["score"], 45.0)

    def test_neutral_signal(self):
        """Testa cenário neutro."""
        obi = 0.1
        sentiment = 0.0
        patchtst = 0.5  # Norm 0.0

        decision = self.ai.calculate_decision(obi, sentiment, patchtst)
        print(f"\nNeutral Case: {decision}")
        self.assertEqual(decision["direction"], "NEUTRAL")
        self.assertTrue(45.0 <= decision["score"] <= 55.0)

    def test_conflicting_signal(self):
        """Testa conflito: Book Venda vs Previsão Alta."""
        obi = -0.8  # Venda
        sentiment = 0.0  # Neutro
        patchtst = 0.9  # Alta (Norm 0.8)

        decision = self.ai.calculate_decision(obi, sentiment, patchtst)
        print(f"\nConflicting Case: {decision}")
        # Expected: Neutral or weak signal due to conflict
        # Should not be extreme
        self.assertTrue(
            40.0 < decision["score"] < 60.0 or decision["direction"] == "NEUTRAL"
        )


if __name__ == "__main__":
    unittest.main()
