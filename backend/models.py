import torch
import torch.nn as nn
import numpy as np

class PatchTST(nn.Module):
    """
    Implementação completa do PatchTST (Patch Time Series Transformer).
    Divide a série temporal em 'patches' para capturar dependências locais.
    """
    def __init__(self, input_dim=1, seq_len=60, patch_size=8, stride=4, num_layers=3, n_heads=4, d_model=128):
        super().__init__()
        self.patch_size = patch_size
        self.stride = stride
        self.num_patches = (seq_len - patch_size) // stride + 1
        
        # Projeção de patches
        self.patch_projection = nn.Linear(patch_size, d_model)
        
        # Positional Encoding (parâmetro treinável)
        self.pos_encoding = nn.Parameter(torch.zeros(1, self.num_patches, d_model))
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=n_heads, 
            dim_feedforward=d_model * 4,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Cabeça de Predição (Linear para 3 quantis: 0.1, 0.5, 0.9)
        self.head = nn.Linear(d_model * self.num_patches, 3)

    def forward(self, x):
        # x shape: [batch, seq_len, input_dim]
        
        # 1. Unfold em patches: [batch, num_patches, patch_size, input_dim]
        # Aqui simplificamos assumindo input_dim=1 para o sinal de entrada
        x = x.unfold(dimension=1, size=self.patch_size, step=self.stride)
        # x: [batch, num_patches, input_dim, patch_size]
        
        x = x.squeeze(2) # [batch, num_patches, patch_size]
        
        # 2. Projeção + Positional Encoding
        x = self.patch_projection(x) + self.pos_encoding
        
        # 3. Transformer Encoder
        x = self.transformer_encoder(x)
        
        x = x.reshape(x.shape[0], -1) # [batch, num_patches * d_model]
        return self.head(x)

class PointQuantileLoss(nn.Module):
    """
    Função de Perda para Regressão Quantílica (Incerteza).
    Calcula a perda para 3 quantis: q10 (Pessimista), q50 (Média), q90 (Otimista).
    """
    def __init__(self, quantiles=[0.1, 0.5, 0.9]):
        super().__init__()
        self.quantiles = quantiles

    def forward(self, preds, target):
        """
        preds: [batch, 3] (q10, q50, q90)
        target: [batch] (valor real)
        """
        loss = 0.0
        for i, q in enumerate(self.quantiles):
            error = target - preds[:, i]
            loss += torch.max((q - 1) * error, q * error).mean()
        return loss

class ConformalPrediction:
    """
    Calibração de Incerteza via Conformal Prediction.
    Gera intervalos de confiança garantidos estatisticamente.
    """
    def __init__(self, alpha=0.1):
        self.alpha = alpha # 90% de confiança
        self.calibration_scores = []
        self.q_hat = 0.0 # Valor de correção calibrado
        
    def calibrate(self, preds_q10, preds_q90, actuals):
        """
        Ajusta o q_hat com base em dados de validação.
        Score = max(q10 - y, y - q90)
        """
        scores = []
        for i in range(len(actuals)):
            # Score de não-conformidade
            score = max(preds_q10[i] - actuals[i], actuals[i] - preds_q90[i])
            scores.append(score)
            
        self.calibration_scores = scores
        # Q-hat é o quantil (1-alpha) dos scores
        k = int(np.ceil((1 - self.alpha) * (len(scores) + 1)))
        if scores:
            self.q_hat = np.sort(scores)[min(k, len(scores)-1)]
            
    def predict_interval(self, q10, q90):
        """Retorna intervalo calibrado: [q10 - q_hat, q90 + q_hat]"""
        return q10 - self.q_hat, q90 + self.q_hat
