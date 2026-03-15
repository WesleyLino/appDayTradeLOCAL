# Crie este arquivo em: backend/regime_classifier.py
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
import joblib
import os


class MarketRegimeModel:
    def __init__(self, n_components=3, model_path="data/models/regime_hmm.pkl"):
        self.n_components = n_components
        self.model_path = model_path
        self.model = GaussianHMM(
            n_components=self.n_components, covariance_type="full", n_iter=100
        )
        self.is_trained = False

    def _prepare_features(self, df: pd.DataFrame):
        # Calcula retornos logarítmicos e Volatilidade (ATR proxy)
        df["log_return"] = np.log(df["close"] / df["close"].shift(1))
        df["volatility"] = df["log_return"].rolling(window=14).std()
        df.dropna(inplace=True)
        return df[["log_return", "volatility"]].values

    def train(self, historical_data: pd.DataFrame):
        """Treina o HMM com dados históricos para aprender os 3 estados."""
        features = self._prepare_features(historical_data)
        self.model.fit(features)
        self.is_trained = True
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        print(f"[REGIME] Modelo HMM treinado e salvo em {self.model_path}")

    def load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            self.is_trained = True

    def predict_current_regime(self, recent_data: pd.DataFrame) -> int:
        """
        Retorna:
        0: Tendência Baixa Volatilidade (BULL/BEAR lento)
        1: Tendência Alta Volatilidade (Rompimentos agressivos)
        2: Lateral / Choppy (Não operar direção)
        """
        if not self.is_trained:
            self.load_model()

        features = self._prepare_features(recent_data)
        if len(features) == 0:
            return 2  # Na dúvida, assuma Choppy (Lateral)

        regimes = self.model.predict(features)
        return regimes[-1]  # Retorna o estado do último minuto
