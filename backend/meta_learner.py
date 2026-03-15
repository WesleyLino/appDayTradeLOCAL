import logging
import os
import numpy as np
import pandas as pd


class MetaLearner:
    def __init__(self, model_path="data/models/xgboost_meta_v1.json"):
        self.model_path = model_path
        self.model = None
        self.load_model()

    def load_model(self):
        """
        Carrega o modelo XGBoost se existir.
        Caso contrário, o sistema opera em modo 'Pass-Through' (sem filtro).
        """
        if os.path.exists(self.model_path):
            try:
                # Tenta importar xgboost apenas se o arquivo existir
                import xgboost as xgb

                self.model = xgb.XGBClassifier()
                self.model.load_model(self.model_path)
                logging.info(f"Meta-Learner carregado: {self.model_path}")
            except ImportError:
                logging.warning(
                    "Bibliotexa xgboost não encontrada. Meta-Learner desativado."
                )
            except Exception as e:
                logging.error(f"Erro ao carregar Meta-Learner: {e}")
        else:
            logging.info(
                "Nenhum modelo Meta-Learner encontrado. Operando em modo coleta de dados."
            )

    def predict_proba(self, features):
        """
        Retorna a probabilidade de SUCESSO do trade (0.0 a 1.0).
        Se não houver modelo, retorna 0.5 (Neutro/Pass-Through).

        Features esperadas (ordem importa!):
        [ATR, OBI, Sentiment, Volatility, Hour, AI_Score]
        """
        if self.model is None:
            return 0.5

        try:
            # Converter para DataFrame ou DMatrix conforme necessário pelo XGBoost
            # Aqui assumimos input numpy array (1, N)
            # XGBoost scikit-learn interface aceita numpy
            features_array = np.array(features).reshape(1, -1)

            # predict_proba retorna [[prob_0, prob_1]]
            probs = self.model.predict_proba(features_array)
            prob_gain = float(probs[0][1])  # Retorna prob da classe 1 (Gain)

            if prob_gain < 0.45:
                logging.info(
                    f"🛡️ META-VETO: Baixa prob de ganho ({prob_gain:.2%}) p/ contexto {features}"
                )

            return prob_gain
        except Exception as e:
            logging.error(f"Erro na inferência do Meta-Learner: {e}")
            return 0.5

    def log_training_data(
        self, features, label=None, file_path="data/training/triple_barrier_data.csv"
    ):
        """
        Registra os dados para treinamento futuro (Triple Barrier Method).
        Se label for None, estamos registrando apenas a 'intenção' (ex: realtime).
        Mas para treino, precisamos do label (que será preenchido a posteriori).

        Aqui, vamos salvar em um CSV simples.
        """
        try:
            df = pd.DataFrame(
                [features],
                columns=["ATR", "OBI", "Sentiment", "Volatility", "Hour", "AI_Score"],
            )

            # Se tivermos label (ex: backtest), adicionamos
            if label is not None:
                df["Target"] = label
            else:
                df["Target"] = np.nan  # A ser preenchido pelo Triple Barrier Labeller

            # Timestamp
            df["timestamp"] = pd.Timestamp.now()

            # Salvar append
            header = not os.path.exists(file_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            df.to_csv(file_path, mode="a", header=header, index=False)

        except Exception as e:
            logging.error(f"Erro ao logar dados de treino: {e}")
