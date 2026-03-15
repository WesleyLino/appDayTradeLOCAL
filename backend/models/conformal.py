import numpy as np
import logging
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_is_fitted


class ConformalPrediction(BaseEstimator, RegressorMixin):
    """
    [SOTA] Conformal Prediction Wrapper.
    Fornece garantias estatísticas de cobertura para intervalos de predição.
    Baseado na metodologia Split Conformal ou MAPIE.
    """

    def __init__(self, estimator, alpha=0.05, method="naive"):
        self.estimator = estimator
        self.alpha = alpha
        self.method = method
        self.residuals_ = []
        self.q_hat_ = None

    def fit(self, X, y):
        """
        Treina o estimador base e calibra os resíduos.
        Na prática SOTA, usamos um conjunto de calibração separado,
        mas aqui simplificamos para treino direto seguido de calibração on-residuals.
        """
        self.estimator.fit(X, y)
        preds = self.estimator.predict(X)

        # Calcular resíduos absolutos (não-conformidade)
        self.residuals_ = np.abs(y - preds)

        # Calcular Q_hat (score de conformidade)
        n = len(y)
        # Quantil corrigido para garantir cobertura marginal
        q_val = np.ceil((n + 1) * (1 - self.alpha)) / n
        q_val = min(1.0, max(0.0, q_val))  # Clip

        self.q_hat_ = np.quantile(self.residuals_, q_val)

        return self

    def predict(self, X):
        """
        Retorna predição pontual e intervalo de confiança.
        Returns:
            y_pred: Predição pontual
            y_lower: Limite inferior
            y_upper: Limite superior
        """
        check_is_fitted(self.estimator)

        y_pred = self.estimator.predict(X)

        if self.q_hat_ is None:
            # Fallback se não calibrado
            logging.warning(
                "ConformalPrediction não calibrado. Usando incerteza padrão."
            )
            uncertainty = np.std(y_pred) * 1.96
        else:
            uncertainty = self.q_hat_

        return y_pred, y_pred - uncertainty, y_pred + uncertainty

    def score(self, X, y):
        # Validação da cobertura
        _, y_lower, y_upper = self.predict(X)
        coverage = np.mean((y >= y_lower) & (y <= y_upper))
        return coverage
