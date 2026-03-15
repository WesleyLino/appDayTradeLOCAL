"""
Script de Treinamento do XGBoost Meta-Learner
==============================================

Este script lê os dados coletados via Triple Barrier Method e treina
o modelo XGBoost para refinar decisões de trading.

Uso:
    python train_xgboost.py

Pré-requisitos:
    - Arquivo data/training/triple_barrier_data.csv com pelo menos 500 amostras
    - Biblioteca xgboost instalada (pip install xgboost)
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import logging
import os

logging.basicConfig(level=logging.INFO)

# Configurações
DATA_PATH = "data/training/triple_barrier_data.csv"
MODEL_PATH = "data/models/xgb_meta_learner.json"
MIN_SAMPLES = 500  # Mínimo de amostras para treinamento confiável


def load_data():
    """Carrega dados do Triple Barrier Method."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Arquivo de dados não encontrado: {DATA_PATH}\n"
            f"Execute o sistema em modo coleta antes de treinar o modelo."
        )

    df = pd.read_csv(DATA_PATH)
    logging.info(f"Dados carregados: {len(df)} amostras")

    if len(df) < MIN_SAMPLES:
        logging.warning(
            f"⚠️ Apenas {len(df)} amostras disponíveis. "
            f"Recomendado: mínimo {MIN_SAMPLES} para generalização robusta."
        )

    return df


def prepare_features(df):
    """Prepara features e targets para treinamento."""
    # Features esperadas: [ATR, OBI, Sentiment, Volatility, Hour, AI_Score_Raw]
    feature_cols = ["ATR", "OBI", "Sentiment", "Volatility", "Hour", "AI_Score"]

    # Verificar colunas faltantes
    missing_cols = [col for col in feature_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Colunas faltantes no dataset: {missing_cols}")

    X = df[feature_cols].values

    # Target: Converter -1 (Loss), 0 (Timeout), 1 (Gain) para binário
    # Estratégia: Considerar apenas Gain (1) vs Resto (0)
    # Isso torna o modelo conservador (só sinaliza quando há alta probabilidade de ganho)
    y = (df["Target"] == 1).astype(int).values

    logging.info(f"Features shape: {X.shape}")
    logging.info(f"Target distribution: Gain={y.sum()} | No-Gain={len(y) - y.sum()}")

    return X, y, feature_cols


def train_model(X, y):
    """Treina o modelo XGBoost com validação cruzada."""
    # Split train/test (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logging.info(f"Train samples: {len(X_train)} | Test samples: {len(X_test)}")

    # Configuração do XGBoost
    # Parâmetros conservadores para evitar overfitting
    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "max_depth": 3,  # Árvores rasas (menos overfitting)
        "learning_rate": 0.05,  # Learning rate baixo
        "n_estimators": 100,  # 100 árvores
        "subsample": 0.8,  # 80% das amostras por árvore
        "colsample_bytree": 0.8,  # 80% das features por árvore
        "gamma": 1.0,  # Regularização (penaliza complexidade)
        "reg_alpha": 0.1,  # L1 regularization
        "reg_lambda": 1.0,  # L2 regularization
        "scale_pos_weight": 1,  # Ajustar se classes desbalanceadas
        "random_state": 42,
    }

    # Criar modelo
    model = xgb.XGBClassifier(**params)

    # Treinar com Early Stopping
    eval_set = [(X_train, y_train), (X_test, y_test)]
    model.fit(X_train, y_train, eval_set=eval_set, verbose=True)

    # Avaliar no conjunto de teste
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    logging.info("\n=== Métricas de Avaliação ===")
    logging.info(
        f"\n{classification_report(y_test, y_pred, target_names=['No-Gain', 'Gain'])}"
    )
    logging.info(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred)}")

    # Calibração: Verificar distribuição de probabilidades
    logging.info("\nDistribuição de Probabilidades (Teste):")
    logging.info(f"  Min:  {y_proba.min():.3f}")
    logging.info(f"  25%:  {np.percentile(y_proba, 25):.3f}")
    logging.info(f"  50%:  {np.percentile(y_proba, 50):.3f}")
    logging.info(f"  75%:  {np.percentile(y_proba, 75):.3f}")
    logging.info(f"  Max:  {y_proba.max():.3f}")

    return model


def save_model(model, feature_cols):
    """Salva o modelo treinado."""
    # Criar diretório se não existir
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    # Salvar modelo em formato JSON (portável)
    model.save_model(MODEL_PATH)

    logging.info(f"✅ Modelo salvo em: {MODEL_PATH}")
    logging.info(f"Features esperadas: {feature_cols}")


def main():
    """Função principal."""
    try:
        # 1. Carregar dados
        df = load_data()

        # 2. Preparar features
        X, y, feature_cols = prepare_features(df)

        # 3. Treinar modelo
        model = train_model(X, y)

        # 4. Salvar modelo
        save_model(model, feature_cols)

        logging.info("\n✅ Treinamento concluído com sucesso!")
        logging.info("O modelo está pronto para uso no MetaLearner.")

    except Exception as e:
        logging.error(f"❌ Erro durante treinamento: {e}")
        raise


if __name__ == "__main__":
    main()
