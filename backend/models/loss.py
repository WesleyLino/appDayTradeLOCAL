import torch
import torch.nn as nn


class PointQuantileLoss(nn.Module):
    """
    [SOTA] Point-Quantile Loss para Previsão Probabilística.
    Combina:
    1. MSE Loss para a estimativa pontual (média/mediana).
    2. Quantile Loss para os,limites de incerteza (intervalos de confiança).

    Usado para treinar o PatchTST para prever não apenas o preço, mas a distribuição.
    """

    def __init__(self, quantiles=[0.1, 0.5, 0.9], weight_mse=0.5):
        super().__init__()
        self.quantiles = quantiles
        self.weight_mse = weight_mse
        self.mse_loss = nn.MSELoss()

    def forward(self, preds, target):
        """
        Args:
            preds: Tensor [Batch, Window, Quantiles] ou [Batch, Window] se apenas 1 saída
            target: Tensor [Batch, Window, 1]
        """
        # Se o modelo retornar apenas 1 canal (ex: preço), usa MSE simples
        if preds.dim() == 2 or preds.size(-1) == 1:
            return self.mse_loss(preds, target.squeeze(-1))

        losses = []
        for i, q in enumerate(self.quantiles):
            # Forçamos p a ter o mesmo shape de target [Batch, Window, 1]
            p = preds[:, :, i].view_as(target)
            errors = target - p
            loss = torch.max((q - 1) * errors, q * errors)
            losses.append(loss.mean())

        quantile_loss = torch.stack(losses).mean()

        mse = 0
        if 0.5 in self.quantiles:
            idx_median = self.quantiles.index(0.5)
            # Garantir shape idêntico para MSE via view_as
            p_median = preds[:, :, idx_median].view_as(target)
            mse = self.mse_loss(p_median, target)

        return (1 - self.weight_mse) * quantile_loss + self.weight_mse * mse
