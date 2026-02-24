import sys
import os
import torch
import numpy as np
import logging

# Adicionar o diretório raiz ao path para importar os módulos do backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_core import AICore

def verify_sota_decision_logic():
    print("=== VERIFICAÇÃO DE PRECISÃO SOTA v3.1 ===")
    
    ai = AICore()
    
    # Caso 1: Confluência Total (Deveria ser BUY)
    # PatchTST sugerindo alta forte (norm_score = 0.95), OBI positivo (0.8), Sentiment positivo (0.8)
    print("\n[TESTE 1] Cenário: Confluência Total (Bullish)")
    res1 = ai.calculate_decision(
        obi=0.8, 
        sentiment=0.8, 
        patchtst_score={"score": 0.95, "uncertainty_norm": 0.01, "forecast_norm": 1.0}, 
        regime=1
    )
    print(f"Score: {res1['score']:.1f} | Direção: {res1['direction']}")
    assert res1['score'] >= 85, "ERRO: O score deveria ser >= 85 para confluência total."
    assert res1['direction'] == "BUY", "ERRO: A direção deveria ser BUY."

    # Caso 2: Falta de Confluência (Deveria ser NEUTRAL)
    # PatchTST sugere alta (0.9), mas OBI é negativo (-0.5)
    print("\n[TESTE 2] Cenário: Divergência (IA Alta / OBI Baixa)")
    res2 = ai.calculate_decision(
        obi=-0.5, 
        sentiment=0.0, 
        patchtst_score={"score": 0.9, "uncertainty_norm": 0.01, "forecast_norm": 1.0}, 
        regime=1
    )
    print(f"Score: {res2['score']:.1f} | Direção: {res2['direction']}")
    assert res2['score'] < 85, "ERRO: O score não deveria atingir 85 com divergência de OBI."
    assert res2['direction'] == "NEUTRAL", "ERRO: A direção deveria ser NEUTRAL."

    # Caso 3: Incerteza Alta (Deveria ser NEUTRAL - Veto)
    print("\n[TESTE 3] Cenário: Incerteza Alta (Veto SOTA)")
    res3 = ai.calculate_decision(
        obi=0.9, 
        sentiment=0.9, 
        patchtst_score={"score": 0.95, "uncertainty_norm": 0.45, "forecast_norm": 1.0}, 
        regime=1
    )
    print(f"Score: {res3['score']:.1f} | Direção: {res3['direction']}")
    assert res3['direction'] == "NEUTRAL", "ERRO: Incerteza alta deveria forçar NEUTRAL."

    # Caso 4: Venda Forte
    print("\n[TESTE 4] Cenário: Venda Forte (Bearish Confluence)")
    res4 = ai.calculate_decision(
        obi=-0.9, 
        sentiment=-0.9, 
        patchtst_score={"score": 0.05, "uncertainty_norm": 0.01, "forecast_norm": 1.0}, 
        regime=1
    )
    print(f"Score: {res4['score']:.1f} | Direção: {res4['direction']}")
    assert res4['score'] <= 15, "ERRO: O score deveria ser <= 15 para venda forte."
    assert res4['direction'] == "SELL", "ERRO: A direção deveria ser SELL."

    print("\n✅ Verificação Concluída: Lógica de Precisão SOTA 85% VALIDADA.")

if __name__ == "__main__":
    try:
        verify_sota_decision_logic()
    except Exception as e:
        print(f"\n❌ FALHA NA VERIFICAÇÃO: {e}")
        sys.exit(1)
