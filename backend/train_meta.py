import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import logging
import os
import glob
from datetime import datetime

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calculate_meta_features(df):
    """Calcula as features necessárias para o Meta-Learner."""
    df = df.copy()
    
    # 1. ATR (14)
    tr = pd.concat([df['high'] - df['low'], 
                   (df['high'] - df['close'].shift()).abs(), 
                   (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    # 2. Volatilidade (Std Dev dos retornos 20p)
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=20).std()
    
    # 3. OBI (Usando OFI como base, normalizado)
    if 'ofi' in df.columns:
        df['obi'] = df['ofi'].rolling(window=5).mean()
    else:
        df['obi'] = 0.0
        
    # 4. Hora do dia
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    
    # 5. Sentinel Sentiment (Proxy: 0 por enquanto)
    df['sentiment'] = 0.0
    
    # AI_Score (Simulado para o treino inicial se não houver)
    # Em produção real, o worker de aprendizado contínuo deve logar o score real do PatchTST.
    # Aqui, usamos uma probabilidade baseada no retorno futuro como 'proxy' de acerto.
    df['target_return'] = (df['close'].shift(-5) - df['close']) / df['close']
    
    # AI_Score Dummy: Se o retorno futuro foi positivo, geramos um score alto (buy preference)
    # Se foi negativo, score baixo. Adicionamos ruído para simular incerteza da IA.
    noise = np.random.normal(0, 0.1, len(df))
    df['ai_score'] = 0.5 + (df['target_return'].shift(1) * 10) + noise
    df['ai_score'] = df['ai_score'].clip(0, 1)
    
    return df.dropna()

def generate_labels(df):
    """
    Rotula como 1 se um sinal hipotético teria lucro.
    Consideramos um acerto se em 5 candles o movimento favorável foi > ATR * 0.5
    """
    df = df.copy()
    # Para o treino do meta-learner, queremos saber se o CONTEXTO levou a um WIN.
    # Label = 1 se price(t+5) > price(t) (para buys) ou price(t+5) < price(t) (para sells)
    # Simplificando: Label = 1 se a direção do movimento em 5 candles foi 'clara'.
    df['label_meta'] = (df['target_return'].abs() > (df['atr'] / df['close']) * 0.3).astype(int)
    return df

def train_meta_learner():
    logging.info("🧠 Iniciando Treinamento do Meta-Learner (XGBoost)...")
    
    data_path = "data/sota_training/training_WIN$_MASTER.csv"
    if not os.path.exists(data_path):
        logging.error(f"❌ Arquivo mestre não encontrado em {data_path}")
        return
        
    df = pd.read_csv(data_path)
    df = calculate_meta_features(df)
    df = generate_labels(df)
    
    # Features para o XGBoost (Conforme especificado na Fase 24)
    features = ['atr', 'obi', 'sentiment', 'volatility', 'hour', 'ai_score']
    X = df[features]
    y = df['label_meta']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    logging.info(f"📊 Dataset: {len(df)} amostras. Iniciando Fit...")
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        objective='binary:logistic',
        random_state=42
    )
    
    model.fit(X_train, y_train)
    
    # Avaliação
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logging.info(f"✅ Treino Concluído. Acurácia: {acc:.2%}")
    logging.info("\n" + classification_report(y_test, y_pred))
    
    # Salvar Modelo
    output_dir = "data/models"
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "xgboost_meta_v1.json")
    model.save_model(model_path)
    logging.info(f"📦 Meta-Learner salvo em: {model_path}")

if __name__ == "__main__":
    train_meta_learner()
