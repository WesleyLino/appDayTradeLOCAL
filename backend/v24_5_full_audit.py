import unittest
from backend.ai_core import AICore
from backend.risk_manager import RiskManager
import logging
import sys

# Forçar logs de nível INFO para ver os prints do AI Core
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")


class TestV24_5FullAudit(unittest.TestCase):
    def setUp(self):
        self.ai = AICore()
        self.risk = RiskManager()

    def test_golden_window_logic(self):
        """Valida a Janela de Ouro (10:00 - 11:30). PT-BR."""
        print("\n--- Teste Janela de Ouro ---")
        # Teste 10:30 (Dentro)
        decision = self.ai.calculate_decision(
            hour=10, minute=30, score=55, obi=0, rsi=50
        )
        self.assertTrue(
            decision["is_golden_window"], "10:30 deveria ser Janela de Ouro"
        )

        # Teste 11:30 (Dentro - Limite)
        decision = self.ai.calculate_decision(
            hour=11, minute=30, score=55, obi=0, rsi=50
        )
        self.assertTrue(
            decision["is_golden_window"], "11:30 deveria ser Janela de Ouro"
        )

        # Teste 12:00 (Fora)
        decision = self.ai.calculate_decision(
            hour=12, minute=0, score=55, obi=0, rsi=50
        )
        self.assertFalse(
            decision["is_golden_window"], "12:00 NÃO deveria ser Janela de Ouro"
        )

    def test_momentum_bypass_audit(self):
        """Valida o Momentum Bypass Pro (Sweep Institucional). PT-BR."""
        print("\n--- Teste Momentum Bypass ---")
        # Insumos para garantir score_raw >= 82
        # score_raw = (patchtst * 0.7) + (sent * 0.3) [fora da janela de ouro e sem obi]
        # Se patchtst=95 e sent=1.0 (sent_norm=100) -> (95*0.7) + (100*0.3) = 66.5 + 30 = 96.5
        decision = self.ai.calculate_decision(
            score=95,
            obi=0,
            sentiment=1.0,
            hour=14,
            minute=0,
            rsi=85,  # RSI esticado
            cvd_accel=0.15,  # Accel forte
        )
        print(
            f"Bypass Result: {decision['is_momentum_bypass']} | Score Raw: {decision.get('score_raw', 'N/A')}"
        )
        self.assertTrue(
            decision["is_momentum_bypass"],
            "Deveria ativar Momentum Bypass com Score 95 e Accel 0.15",
        )
        self.assertEqual(decision["direction"], "COMPRA", "Direção deveria ser COMPRA")

    def test_obi_rigor_audit(self):
        """Valida o rigor de OBI na Janela de Ouro (Novo threshold 1.8). PT-BR."""
        print("\n--- Teste OBI Janela de Ouro ---")
        # 1. Teste com 1.3 (Deveria ser FALSE agora)
        decision_low = self.ai.calculate_decision(
            hour=10, minute=30, score=50, obi=1.3, rsi=50
        )
        print(
            f"OBI 1.3 Bypass: {decision_low['is_momentum_bypass']} | Golden: {decision_low['is_golden_window']}"
        )
        self.assertFalse(
            decision_low["is_momentum_bypass"],
            "OBI 1.3 não deveria ativar bypass (Threshold 1.8)",
        )

        # 2. Teste com 1.9 (Deveria ser TRUE)
        decision_high = self.ai.calculate_decision(
            hour=10, minute=30, score=50, obi=1.9, rsi=50
        )
        print(
            f"OBI 1.9 Bypass: {decision_high['is_momentum_bypass']} | Golden: {decision_high['is_golden_window']}"
        )
        self.assertTrue(
            decision_high["is_momentum_bypass"],
            "OBI 1.9 deveria ativar bypass na Janela de Ouro",
        )

    def test_scaling_out_audit(self):
        """Valida a saída parcial de 1 contrato aos 70 pontos. PT-BR."""
        print("\n--- Teste Scaling Out ---")
        should_partial, volume = self.risk.check_scaling_out("WIN$", 12345, 75.0, 2.0)
        self.assertTrue(should_partial, "Deveria realizar parcial com 75 pts e 2 lotes")
        self.assertEqual(volume, 1.0, "Deveria reduzir exatamente 1 lote")

    def test_asymmetric_trailing_audit(self):
        """Valida o Trailing Stop Assimétrico (Compra vs Venda). PT-BR."""
        print("\n--- Teste Trailing Assimétrico ---")
        # BUY: 150/100/50
        trigger, lock, step = self.risk.get_dynamic_trailing_params(
            current_atr=100, side="buy"
        )
        self.assertEqual(trigger, 150.0)
        self.assertEqual(lock, 100.0)
        self.assertEqual(step, 50.0)

        # SELL: 80/60/20
        trigger, lock, step = self.risk.get_dynamic_trailing_params(
            current_atr=100, side="sell"
        )
        self.assertEqual(trigger, 80.0)
        self.assertEqual(lock, 60.0)
        self.assertEqual(step, 20.0)


if __name__ == "__main__":
    unittest.main()
