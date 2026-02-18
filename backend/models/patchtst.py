import torch
import torch.nn as nn
import math

class PatchTST(nn.Module):
    """
    [SOTA] PatchTST: Time Series Transformer with Patching.
    Paper: https://arxiv.org/abs/2211.14730
    
    Principais Inovações:
    1. Patching: Agrupa time-steps em patches (tokens) para capturar dependências locais e reduzir complexidade.
    2. Channel Independence: Cada canal (variável) é processado independentemente pelo Transformer (mesmo embedding).
    """
    def __init__(self, 
                 c_in=7,                # Número de variáveis de entrada (Default: 7 [OHLCV+OFI+Spread], mas suporta dinâmico ex: 1)
                 context_window=96,     # Tamanho da janela de entrada (Lookback)
                 target_window=10,      # Horizonte de previsão
                 patch_len=16,          # Tamanho do patch
                 stride=8,              # Passo do patch (Overlap)
                 d_model=128,           # Dimensão do embedding
                 n_heads=4,             # Número de cabeças de atenção
                 n_layers=3,            # Número de camadas do Encoder
                 d_ff=512,              # Dimensão da FeedForward Network
                 dropout=0.1,
                 head_dropout=0.0):
        super().__init__()
        
        self.c_in = c_in
        self.context_window = context_window
        self.target_window = target_window
        self.patch_len = patch_len
        self.stride = stride
        
        # Calcular número de patches
        self.n_patches = int((context_window - patch_len) / stride) + 1
        
        # 1. Reversible Instance Normalization (RevIN) - Normalização robusta a shift de distribuição
        self.revin = RevIN(c_in)
        
        # 2. Patching & Embedding
        self.patch_embedding = nn.Linear(patch_len, d_model)
        self.position_embedding = nn.Parameter(torch.randn(1, self.n_patches, d_model))
        self.dropout = nn.Dropout(dropout)
        
        # 3. Transformer Encoder Backbone
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, dim_feedforward=d_ff, dropout=dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        
        # 4. Flatten Head (Linear Projection)
        self.head = nn.Linear(self.n_patches * d_model, target_window)
        self.head_dropout = nn.Dropout(head_dropout)

    def forward(self, x):
        """
        x: [Batch, Input_Window, Channels]
        """
        # A. RevIN Normalization
        x = self.revin(x, mode='norm')
        
        # B. Patching
        # Reshape customizado para patching: [Batch, Channels, Input_Window] -> [Batch, Channels, N_Patches, Patch_Len]
        x = x.permute(0, 2, 1) # [B, C, L]
        x = x.unfold(dimension=-1, size=self.patch_len, step=self.stride) # [B, C, N_Patches, Patch_Len]
        
        # C. Embedding (Channel Independence: merge Batch and Channels)
        # [B * C, N_Patches, Patch_Len]
        B, C, N, P = x.shape
        x = x.reshape(B * C, N, P)
        
        x = self.patch_embedding(x) # [B*C, N, d_model]
        x = x + self.position_embedding # Add Positional Encoding
        x = self.dropout(x)
        
        # D. Transformer Encoder
        x = self.encoder(x) # [B*C, N, d_model]
        
        # E. Flatten Head
        x = x.reshape(B * C, -1) # [B*C, N * d_model]
        x = self.head_dropout(x)
        x = self.head(x) # [B*C, Target_Window]
        
        # Reshape back to [B, Target_Window, C]
        x = x.reshape(B, C, self.target_window)
        x = x.permute(0, 2, 1) # [B, T, C]
        
        # F. RevIN Denormalization
        x = self.revin(x, mode='denorm')
        
        return x

class RevIN(nn.Module):
    """
    Reversible Instance Normalization (Kim et al., 2022)
    Resolve o problema de 'distribution shift' em séries temporais financeiras.
    """
    def __init__(self, num_features: int, eps=1e-5, affine=True):
        super().__init__()
        self.num_features = num_features
        self.eps = eps
        self.affine = affine
        if self.affine:
            self._init_params()

    def _init_params(self):
        self.affine_weight = nn.Parameter(torch.ones(self.num_features))
        self.affine_bias = nn.Parameter(torch.zeros(self.num_features))

    def forward(self, x, mode:str):
        if mode == 'norm':
            self._get_statistics(x)
            x = self._normalize(x)
        elif mode == 'denorm':
            x = self._denormalize(x)
        else: raise NotImplementedError
        return x

    def _get_statistics(self, x):
        dim2reduce = tuple(range(1, x.ndim-1))
        self.mean = torch.mean(x, dim=dim2reduce, keepdim=True).detach()
        self.stdev = torch.sqrt(torch.var(x, dim=dim2reduce, keepdim=True, unbiased=False) + self.eps).detach()

    def _normalize(self, x):
        x = x - self.mean
        x = x / self.stdev
        if self.affine:
            x = x * self.affine_weight
            x = x + self.affine_bias
        return x

    def _denormalize(self, x):
        if self.affine:
            x = x - self.affine_bias
            x = x / (self.affine_weight + self.eps*1e-5)
        x = x * self.stdev
        x = x + self.mean
        return x
