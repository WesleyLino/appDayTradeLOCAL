import sys
import os

sys.path.append(os.getcwd())
from backend.ai_core import AICore
import logging

# Configura log para console
logging.basicConfig(level=logging.INFO)


def test_buy_bias():
    ai = AICore()

    # Simula cenário IDEAL de COMPRA
    # Score IA: 90 (Forte Compra)
    # OBI: 1.5 (Forte Pressão de Compra no Book)
    # Sentiment: 0.8 (Notícias Altistas)
    # Regime: 1 (Tendência)
    # ATR: 50 (Volatilidade Normal)

    patchtst_score = {"score": 0.90, "uncertainty_norm": 0.1, "forecast_norm": 1.1}

    print("\n--- TESTE 1: CENÁRIO IDEAL DE COMPRA ---")
    decision = ai.calculate_decision(
        obi=1.5,
        sentiment=0.8,
        patchtst_score=patchtst_score,
        regime=1,
        atr=50.0,
        volatility=50.0,
        hour=11,
        minute=0,
        ofi=1.2,
        current_price=120000.0,
        spread=1.0,
        sma_20=119900.0,
    )

    print(f"Decisão: {decision['direction']}")
    print(f"Score Final: {decision['score']}")
    print(f"Veto: {decision['veto']}")
    print(f"Motivo Breakdown: {decision.get('reason', 'N/A')}")

    # Simula cenário de VETO POR SPOOFING (Toxic Flow)
    print("\n--- TESTE 2: COMPRA COM SPOOFING (FLUXO TÓXICO) ---")
    ai.toxic_flow_score = -0.9  # Simula Spoofing de Compra detectado anteriormente
    decision_spoof = ai.calculate_decision(
        obi=1.5,
        sentiment=0.8,
        patchtst_score=patchtst_score,
        regime=1,
        atr=50.0,
        volatility=50.0,
        hour=11,
        minute=0,
        ofi=1.2,
        current_price=120000.0,
        spread=1.0,
        sma_20=119900.0,
    )
    print(f"Decisão: {decision_spoof['direction']}")
    print(f"Veto: {decision_spoof['veto']}")


if __name__ == "__main__":
    test_buy_bias()
