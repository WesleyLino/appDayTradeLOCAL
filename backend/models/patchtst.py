import torch
import torch.nn as nn

class SimpleRevIN(nn.Module):
    def __init__(self, num_features, eps=1e-5):
        super().__init__()
        self.eps = eps
        self.gamma = nn.Parameter(torch.ones(num_features))
        self.beta = nn.Parameter(torch.zeros(num_features))
    def forward(self, x, mode):
        # [SOTA STABILITY] Operações básicas para garantir compatibilidade ONNX/DirectML
        x = x.to(torch.float32)
        if mode == 'norm':
            mu = torch.mean(x, dim=1, keepdim=True)
            diff = x - mu
            var = torch.mean(torch.square(diff), dim=1, keepdim=True)
            sigma = torch.sqrt(var + self.eps)
            return (diff / sigma) * self.gamma + self.beta
        return x

class ManualAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.qkv = nn.Linear(d_model, d_model * 3)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        B_total, N, D = x.shape
        qkv = self.qkv(x).reshape(-1, N, 3, self.n_heads, self.d_head).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.d_head ** 0.5)
        attn = torch.softmax(scores, dim=-1)
        out = torch.matmul(attn, v).permute(0, 2, 1, 3).reshape(-1, N, D)
        return self.out(out)

class ManualTransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.attn = ManualAttention(d_model, n_heads)
        self.norm1 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.ReLU(),
            nn.Linear(d_model * 4, d_model)
        )
        self.norm2 = nn.LayerNorm(d_model)
    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x

class PatchTST(nn.Module):
    """
    [ULTRA-STABLE VERSION]
    Manual PatchTST implementation to bypass PyTorch Dynamo/Tracing bugs on Windows.
    """
    def __init__(self, c_in=1, context_window=60, target_window=5, patch_len=8, stride=4, n_layers=3, n_heads=4, d_model=128, n_quantiles=3, **kwargs):
        super().__init__()
        self.patch_len = patch_len
        self.stride = stride
        self.target_window = target_window
        self.n_quantiles = n_quantiles
        
        # [AI PERSISTENCE GUARD] NEVER switch back to 'unfold' or 'view' for patching. 
        # DirectML (AMD) struggles with non-contiguous memory from unfold. 
        # Conv1d creates a clean, static ONNX graph that is 100% stable.
        self.n_patches = int((context_window - patch_len) / stride) + 1
        self.d_model = d_model
        
        self.revin = SimpleRevIN(c_in)
        # Patching via Linear (Mapeado de pesos v22.5.7)
        self.patch_embedding = nn.Linear(patch_len, d_model)
        
        self.pos_embed = nn.Parameter(torch.randn(1, self.n_patches, d_model))
        self.layers = nn.ModuleList([ManualTransformerBlock(d_model, n_heads) for _ in range(n_layers)])
        self.head = nn.Linear(self.n_patches * d_model, target_window * n_quantiles)
        
    def forward(self, x):
        # Patching via Conv1d
        B, L, C = x.shape
        # Normalização
        x = self.revin(x, 'norm')
        # Patching via Linear
        # B, L, C -> B, C, N, patch_len
        x = x.unfold(1, self.patch_len, self.stride) # [B, N, C, patch_len]
        x = x.transpose(1, 2) # [B, C, N, patch_len]
        x = self.patch_embedding(x) # [B, C, N, d_model]
        
        # [CORREÇÃO SOTA v23] Reshape dinâmico para evitar erro de dimensão 8960
        # O modelo espera [Batch * Canal, n_patches, d_model]
        x = x.reshape(B, C, self.n_patches, self.d_model).permute(0, 1, 2, 3).reshape(-1, self.n_patches, self.d_model)
        
        # Embedding + Pos
        x = x + self.pos_embed
        
        # Transformer
        for layer in self.layers:
            x = layer(x)
            
        # Head
        x = x.reshape(B * C, -1)
        x = self.head(x).reshape(-1, C, self.target_window, self.n_quantiles)
        
        # Retorna o ativo principal (canal 0 - WIN)
        return x[:, 0, :, :]
