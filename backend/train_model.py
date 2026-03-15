import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import logging
import os
import glob

# Otimização de CPU
num_cores = os.cpu_count()
torch.set_num_threads(max(1, num_cores // 2))

# Configuração de Logs
log_path = os.path.join(os.getcwd(), "backend", "training.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
)

# --- MODELO MANUAL ---


class SimpleAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.mha = nn.MultiheadAttention(d_model, n_heads, batch_first=True)

    def forward(self, x):
        attn_output, _ = self.mha(x, x, x)
        return attn_output


class TransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff):
        super().__init__()
        self.attn = SimpleAttention(d_model, n_heads)
        self.norm1 = nn.LayerNorm(d_model)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.ReLU(), nn.Linear(d_ff, d_model)
        )
        self.norm2 = nn.LayerNorm(d_model)

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x


class RevIN(nn.Module):
    def __init__(self, num_features, eps=1e-5):
        super().__init__()
        self.eps = eps
        self.affine_weight = nn.Parameter(torch.ones(num_features))
        self.affine_bias = nn.Parameter(torch.zeros(num_features))

    def forward(self, x, mode):
        if mode == "norm":
            self.mean = x.mean(dim=1, keepdim=True).detach()
            self.stdev = torch.sqrt(
                x.var(dim=1, keepdim=True, unbiased=False) + self.eps
            ).detach()
            return (
                (x - self.mean) / self.stdev
            ) * self.affine_weight + self.affine_bias
        elif mode == "denorm":
            x = (x - self.affine_bias) / (self.affine_weight + self.eps)
            return x * self.stdev + self.mean


class PatchTST(nn.Module):
    def __init__(
        self,
        c_in,
        context_window,
        target_window,
        patch_len,
        stride,
        n_layers,
        n_heads,
        d_model,
        n_quantiles,
    ):
        super().__init__()
        self.patch_len = patch_len
        self.stride = stride
        self.target_window = target_window
        self.n_quantiles = n_quantiles
        self.n_patches = int((context_window - patch_len) / stride) + 1
        self.revin = RevIN(c_in)
        self.patch_embedding = nn.Linear(patch_len, d_model)
        self.position_embedding = nn.Parameter(torch.randn(1, self.n_patches, d_model))
        self.encoder = nn.Sequential(
            *[TransformerBlock(d_model, n_heads, d_model * 4) for _ in range(n_layers)]
        )
        self.head = nn.Linear(self.n_patches * d_model, target_window * n_quantiles)

    def forward(self, x):
        B, L, C = x.shape
        x = self.revin(x, "norm")
        x = x.permute(0, 2, 1).unfold(-1, self.patch_len, self.stride)
        B, C, N, P = x.shape
        x = x.reshape(B * C, N, P)
        x = self.patch_embedding(x) + self.position_embedding
        for layer in self.encoder:
            x = layer(x)
        x = x.reshape(B * C, -1)
        x = self.head(x).reshape(B, C, self.target_window, self.n_quantiles)
        return x[:, 0, :, :]


class PointQuantileLoss(nn.Module):
    def __init__(self, weight_mse=0.5):
        super().__init__()
        self.weight_mse = weight_mse
        self.mse_loss = nn.MSELoss()

    def forward(self, preds, target):
        losses = []
        for i, q in enumerate([0.1, 0.5, 0.9]):
            p = preds[:, :, i].view_as(target)
            errors = target - p
            losses.append(torch.max((q - 1) * errors, q * errors).mean())
        quantile_loss = torch.stack(losses).mean()
        mse = self.mse_loss(preds[:, :, 1].view_as(target), target)
        return (1 - self.weight_mse) * quantile_loss + self.weight_mse * mse


# --- LÓGICA DE DADOS ---


class MultiAssetDataset(Dataset):
    def __init__(self, data, seq_len=60, pred_len=5):
        self.data = data
        self.seq_len = seq_len
        self.pred_len = pred_len

    def __len__(self):
        return len(self.data) - self.seq_len - self.pred_len + 1

    def __getitem__(self, idx):
        x = self.data[idx : idx + self.seq_len]
        y = self.data[idx + self.seq_len : idx + self.seq_len + self.pred_len, 0:1]
        return torch.tensor(x, dtype=torch.float32), torch.tensor(
            y, dtype=torch.float32
        )


def load_sota_data(data_dir="data/sota_training/"):
    files = glob.glob(os.path.join(data_dir, "training_*_MASTER.csv"))
    if not files:
        return None
    dfs = {}
    for f in files:
        symbol = os.path.basename(f).split("_")[1]
        df = pd.read_csv(f)
        df["time"] = pd.to_datetime(df["time"])
        df = df.drop_duplicates(subset="time").set_index("time")
        dfs[symbol] = df[["close"]].rename(columns={"close": f"close_{symbol}"})
    m = pd.concat(dfs.values(), axis=1, join="inner")
    # Garantir que WIN seja o primeiro
    win_cols = [c for c in m.columns if "WIN" in c]
    if win_cols:
        m = m[win_cols + [c for c in m.columns if c not in win_cols]]
    m = (m - m.mean()) / (m.std() + 1e-8)
    return m


def train():
    logging.info("🚀 INICIANDO TREINO SOTA SEGURO (MANUAL TRANSF.)")
    data = load_sota_data()
    if data is None:
        return
    ds = MultiAssetDataset(data.values)
    loader = DataLoader(ds, batch_size=64, shuffle=True)
    m = PatchTST(len(data.columns), 60, 5, 8, 4, 3, 4, 128, 3)
    o = optim.Adam(m.parameters(), lr=0.0005)
    c = PointQuantileLoss()
    for e in range(5):
        m.train()
        for i, (x, y) in enumerate(loader):
            o.zero_grad()
            loss = c(m(x), y)
            loss.backward()
            o.step()
            if i % 100 == 0:
                logging.info(f"E{e + 1} B{i}/{len(loader)} L:{loss.item():.4f}")
        torch.save(m.state_dict(), "backend/patchtst_weights_sota.pth")
    logging.info("✅ FINALIZADO!")


if __name__ == "__main__":
    train()
