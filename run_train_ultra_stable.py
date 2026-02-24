import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import logging
import sys
import os
import glob

# Desativa Dynamo e JIT globalmente para evitar bugs no Python 3.12/Windows
try:
    import torch._dynamo
    torch._dynamo.disable()
except: 
    pass

# Otimização de CPU para Windows
num_cores = os.cpu_count()
torch.set_num_threads(max(1, num_cores // 2))

# Logging com Flush imediato para o arquivo
log_path = os.path.join(os.getcwd(), "backend", "training.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- MANUAL TRANSFORMER (Zero dependencies on complex nn modules that might trigger tracing) ---

class ManualAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.qkv = nn.Linear(d_model, d_model * 3)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        B, N, D = x.shape
        qkv = self.qkv(x).reshape(B, N, 3, self.n_heads, self.d_head).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.d_head ** 0.5)
        attn = torch.softmax(scores, dim=-1)
        out = torch.matmul(attn, v).permute(0, 2, 1, 3).reshape(B, N, D)
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

class SimpleRevIN(nn.Module):
    def __init__(self, num_features):
        super().__init__()
        self.eps = 1e-5
        self.gamma = nn.Parameter(torch.ones(num_features))
        self.beta = nn.Parameter(torch.zeros(num_features))
    def forward(self, x, mode):
        if mode == 'norm':
            self.mu = x.mean(dim=1, keepdim=True).detach()
            # var calculation without biased=False to avoid issues
            self.sigma = torch.sqrt(torch.var(x, dim=1, keepdim=True) + self.eps).detach()
            return ((x - self.mu) / self.sigma) * self.gamma + self.beta
        return x

class UltraStablePatchTST(nn.Module):
    def __init__(self, c_in, context_window, target_window, patch_len, stride, n_layers, n_heads, d_model, n_quantiles):
        super().__init__()
        self.patch_len = patch_len
        self.stride = stride
        self.target_window = target_window
        self.n_quantiles = n_quantiles
        self.n_patches = int((context_window - patch_len) / stride) + 1
        self.revin = SimpleRevIN(c_in)
        self.patch_embedding = nn.Linear(patch_len, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, self.n_patches, d_model))
        self.layers = nn.ModuleList([ManualTransformerBlock(d_model, n_heads) for _ in range(n_layers)])
        self.head = nn.Linear(self.n_patches * d_model, target_window * n_quantiles)
    def forward(self, x):
        B, L, C = x.shape
        x = self.revin(x, 'norm')
        # Patching manual
        x = x.permute(0, 2, 1).unfold(-1, self.patch_len, self.stride) # [B, C, N, P]
        B, C, N, P = x.shape
        x = x.reshape(B * C, N, P)
        x = self.patch_embedding(x) + self.pos_embed
        for layer in self.layers: 
            x = layer(x)
        x = x.reshape(B * C, -1)
        x = self.head(x).reshape(B, C, self.target_window, self.n_quantiles)
        return x[:, 0, :, :] # Alvo é a primeira coluna (WIN)

class StableQuantileLoss(nn.Module):
    def __init__(self, quantiles=[0.1, 0.5, 0.9]):
        super().__init__()
        self.registred_quantiles = quantiles
    def forward(self, preds, target):
        losses = []
        for i, q in enumerate(self.registred_quantiles):
            p = preds[:, :, i].view_as(target)
            errors = target - p
            losses.append(torch.max((q - 1) * errors, q * errors).mean())
        return torch.stack(losses).mean()

class SimpleDataset(Dataset):
    def __init__(self, data_values, seq_len=60, pred_len=5):
        self.data = torch.tensor(data_values, dtype=torch.float32)
        self.seq_len = seq_len
        self.pred_len = pred_len
    def __len__(self):
        return len(self.data) - self.seq_len - self.pred_len + 1
    def __getitem__(self, idx):
        x = self.data[idx : idx + self.seq_len]
        y = self.data[idx + self.seq_len : idx + self.seq_len + self.pred_len, 0:1]
        return x, y

# --- LOOP DE TREINO ---

def run():
    logging.info("======= INICIANDO TREINO ULTRA ESTÁVEL (PULSOS DE HEARTBEAT) =======")
    data_dir = "data/sota_training/"
    files = glob.glob(os.path.join(data_dir, "training_*_MASTER.csv"))
    if not files:
        logging.error("Dados não encontrados em " + data_dir)
        return
    
    dfs = []
    for f in files:
        symbol = os.path.basename(f).split("_")[1]
        df = pd.read_csv(f)
        df['time'] = pd.to_datetime(df['time'])
        df = df.drop_duplicates(subset='time').sort_values('time').set_index('time')
        dfs.append(df[['close']].rename(columns={'close': f'close_{symbol}'}))
    
    m_df = pd.concat(dfs, axis=1, join='inner')
    m_df = m_df.sort_index()
    win_cols = [c for c in m_df.columns if "WIN" in c]
    if win_cols: 
        m_df = m_df[win_cols + [c for c in m_df.columns if c not in win_cols]]
    
    z_df = (m_df - m_df.mean()) / (m_df.std() + 1e-8)
    logging.info(f"Dataset sincronizado: {z_df.shape}. Canais: {list(z_df.columns)}")
    
    ds = SimpleDataset(z_df.values)
    dl = DataLoader(ds, batch_size=128, shuffle=True)
    
    model = UltraStablePatchTST(c_in=len(z_df.columns), context_window=60, target_window=5, patch_len=8, stride=4, n_layers=3, n_heads=4, d_model=128, n_quantiles=3)
    optimizer = optim.Adam(model.parameters(), lr=0.0005)
    criterion = StableQuantileLoss()
    
    logging.info("Iniciando Epochs...")
    for epoch in range(5):
        model.train()
        for i, (x, y) in enumerate(dl):
            optimizer.zero_grad()
            outputs = model(x)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            if i % 10 == 0:
                logging.info(f"--- HEARTBEAT | E{epoch+1} B{i}/{len(dl)} | Loss: {loss.item():.4f} ---")
        
        torch.save(model.state_dict(), "backend/patchtst_weights_sota.pth")
        logging.info(f"Epoch {epoch+1} salva.")
    
    logging.info("✅ TREINAMENTO COMPLETO E ESTÁVEL!")

if __name__ == "__main__":
    run()
