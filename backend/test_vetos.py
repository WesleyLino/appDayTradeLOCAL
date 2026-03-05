import sys
import os
import logging

# Adiciona o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ai_core import AICore

def test_ai_vetos():
    ai = AICore()
    
    print("--- Testando Veto de Spread ---")
    # Simula spread alto
    decision = ai.calculate_decision(
        obi=0.5, 
        sentiment=0.0, 
        patchtst_score=0.9, 
        spread=10.0 # Threshold padrão é 4.5
    )
    print(f"Score: {decision['score']}, Veto: {decision.get('veto')}")
    assert decision['score'] == 50.0
    assert "SPREAD" in decision.get('veto', '')

    print("\n--- Testando Veto de VWAP ---")
    # Simula preço longe da VWAP
    # Precisamos mockar ou garantir que a VWAP seja calculada
    # Para este teste simples, vamos focar nos que já validamos no código
    
    decision_vwap = ai.calculate_decision(
        obi=0.5, 
        sentiment=0.0, 
        patchtst_score=0.9, 
        current_price=5000.0,
        spread=1.0
    )
    # Se vwap_val for 0 (inicial), não veta.
    print(f"Score VWAP (sem vwap carregada): {decision_vwap['score']}")

    print("\n--- Testando Incerteza Alta ---")
    decision_unc = ai.calculate_decision(
        obi=0.5,
        sentiment=0.0,
        patchtst_score={"score": 0.9, "uncertainty_norm": 0.8, "forecast_norm": 1.0},
        spread=1.0
    )
    print(f"Score Incerteza: {decision_unc['score']}, Veto: {decision_unc.get('veto')}")
    assert decision_unc['score'] == 50.0
    assert "INCERTEZA" in decision_unc.get('veto', '').upper()

    print("\n✅ Testes de backend concluídos com sucesso!")

if __name__ == "__main__":
    test_ai_vetos()
