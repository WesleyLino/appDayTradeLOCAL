import sys
import os
import asyncio
import logging
import numpy as np

# Adicionar diretório atual ao path
sys.path.append(os.getcwd())

from backend.ai_core import AICore
from backend.rl_agent import PPOAgent

# Configurar Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_dynamic_weights():
    logging.info("--- Testando Pesos Dinâmicos (Regime Adaptativo) ---")
    ai = AICore()
    
    # Mock inputs
    obi = 0.8       # Compra Forte
    patchtst = 0.2  # Venda Forte (0.2 -> -0.6 normalizado)
    sentiment = 0.0 # Neutro
    
    # Caso 1: Regime 0 (Consolidação) -> Peso OBI 60%, PatchTST 20%
    # Score esperado: (0.8 * 0.6) + (-0.6 * 0.2) + (0 * 0.2) = 0.48 - 0.12 = 0.36 -> 36.0
    decision_0 = ai.calculate_decision(obi, sentiment, patchtst, regime=0)
    logging.info(f"Regime 0 Score: {decision_0['score']:.2f} (Esperado ~36.0)")
    
    # Caso 2: Regime 1 (Tendência) -> Peso OBI 20%, PatchTST 60%
    # Score esperado: (0.8 * 0.2) + (-0.6 * 0.6) + (0 * 0.2) = 0.16 - 0.36 = -0.20 -> 20.0
    decision_1 = ai.calculate_decision(obi, sentiment, patchtst, regime=1)
    logging.info(f"Regime 1 Score: {decision_1['score']:.2f} (Esperado ~20.0)")
    
    if abs(decision_0['score'] - 36.0) < 1.0 and abs(decision_1['score'] - 20.0) < 1.0:
        logging.info("✅ Lógica de Pesos Dinâmicos VALIDADA!")
    else:
        logging.error("❌ Erro na lógica de pesos!")
        exit(1)

def test_rl_agent():
    logging.info("\n--- Testando PPO Agent (Shadow Mode) ---")
    try:
        agent = PPOAgent(input_dim=5, n_actions=3)
        state = [10.5, 0.5, 0.2, 0.8, 1.2] # Exemplo de estado
        action, log_prob = agent.select_action(state)
        logging.info(f"Action selecionada: {action} (0=Hold, 1=Buy, 2=Sell)")
        logging.info("✅ PPO Agent inicializado e respondendo!")
    except Exception as e:
        logging.error(f"❌ Erro no PPO Agent: {e}")
        exit(1)

if __name__ == "__main__":
    test_dynamic_weights()
    test_rl_agent()
