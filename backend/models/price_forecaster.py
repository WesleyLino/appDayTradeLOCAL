import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from backend.models.patchtst import PatchTST
from backend.models.conformal import ConformalPrediction
import os

class PriceForecaster:
    """
    [SOTA] Wrapper para PatchTST com Conformal Prediction.
    Gerencia o ciclo de vida do modelo: Treino, Inferência e Incerteza.
    """
    def __init__(self, model_dir="backend/weights"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_dir = model_dir
        
        # Hiperparâmetros SOTA
        self.context_window = 96
        self.target_window = 10
        self.patch_len = 16
        self.stride = 8
        self.c_in = 7 # OHLCV + OFI + Spread
        
        # Modelo Deep Learning
        self.dl_model = PatchTST(
            c_in=self.c_in,
            context_window=self.context_window,
            target_window=self.target_window,
            patch_len=self.patch_len,
            stride=self.stride
        ).to(self.device)
        
        # Conformal Prediction (Incerteza)
        self.cp_model = ConformalPrediction(estimator=LinearRegression())
        self.is_fitted = False
        
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)

    def train(self, df_train, df_val=None):
        """
        Treina o PatchTST e calibra o Conformal Prediction.
        """
        # 1. Preparar Dados (Normalização + Janelamento)
        # TODO: Implementar DataLoader eficiente
        pass

    def predict(self, recent_data):
        """
        Realiza a previsão e retorna intervalo de confiança.
        
        Args:
            recent_data: DataFrame com os últimos 'context_window' candles.
            
        Returns:
            dict: {
                'forecast': float (preço alvo),
                'lower_bound': float,
                'upper_bound': float,
                'confidence': float (1 - alpha)
            }
        """
        self.dl_model.eval()
        
        # Pré-processamento
        x = self._preprocess(recent_data)
        
        with torch.no_grad():
            # [1, Target_Window, Channels]
            forecast_tensor = self.dl_model(x)
            
        # Pega o último ponto de previsão do Close (Assumindo Close é indice 3)
        # Ajustar conforme mapeamento de canais real
        pred_close = forecast_tensor[0, -1, 3].item() 
        
        # Conformal Prediction (Simulado por enquanto, necessita calibração)
        # Na prática, usamos o erro residual do modelo em calibração
        uncertainty = self._estimate_uncertainty(x)
        
        return {
            'forecast': pred_close,
            'lower_bound': pred_close - uncertainty,
            'upper_bound': pred_close + uncertainty,
            'confidence': 0.95
        }

    def _preprocess(self, df):
        # Conversão simples df -> tensor
        # Implementar normalização robusta (RevIN cuida localmente, mas input precisa ser são)
        values = df.values[-self.context_window:] # Garantir tamanho
        tensor = torch.FloatTensor(values).unsqueeze(0).to(self.device)
        return tensor

    def _estimate_uncertainty(self, x):
        # Retorna largura do intervalo baseada na calibração (CP)
        # Placeholder: 0.1% do preço
        return 0.0
    
    def save(self):
        torch.save(self.dl_model.state_dict(), f"{self.model_dir}/patchtst.pth")
        
    def load(self):
        path = f"{self.model_dir}/patchtst.pth"
        if os.path.exists(path):
            self.dl_model.load_state_dict(torch.load(path, map_location=self.device))
            self.is_fitted = True
            return True
        return False
