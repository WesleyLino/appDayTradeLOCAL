import sys
import os
import logging

# Adicionar diretório atual ao path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)


def test_meta_learner_passthrough():
    print("\n--- Testando MetaLearner (Modo Pass-Through) ---")

    from backend.meta_learner import MetaLearner

    # Como não há modelo treinado, deve retornar 0.5
    learner = MetaLearner(model_path="data/models/nonexistent.json")

    # Features mock: [ATR, OBI, Sentiment, Volatility, Hour, AI_Score]
    features = [100.0, 0.3, 0.5, 50.0, 10, 75.0]

    proba = learner.predict_proba(features)
    print(f"Probabilidade retornada (sem modelo): {proba}")
    print("Esperado: 0.5 (Neutro)")

    if proba == 0.5:
        print("✅ Pass-Through CORRETO!")
    else:
        print("❌ ERRO no Pass-Through!")


def test_data_logging():
    print("\n--- Testando Log de Dados para Treinamento ---")

    from backend.meta_learner import MetaLearner
    import pandas as pd

    learner = MetaLearner()

    # Limpar arquivo anterior se existir
    log_path = "data/training/triple_barrier_data.csv"
    if os.path.exists(log_path):
        os.remove(log_path)

    # Logar alguns dados
    features1 = [100.0, 0.3, 0.5, 50.0, 10, 75.0]
    features2 = [120.0, -0.2, -0.1, 60.0, 14, 65.0]

    learner.log_training_data(features1, label=1)  # Gain
    learner.log_training_data(features2, label=-1)  # Loss

    # Verificar se foi salvo
    if os.path.exists(log_path):
        df = pd.read_csv(log_path)
        print(f"Linhas registradas: {len(df)}")
        print(df)
        print("✅ Log de dados CORRETO!")
    else:
        print("❌ ERRO no log de dados!")


if __name__ == "__main__":
    test_meta_learner_passthrough()
    test_data_logging()
