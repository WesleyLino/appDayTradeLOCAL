## Patch de compatibilidade: onnxscript 0.6.x removeu ParamSchema que beartype 0.19.x
# tenta resolver durante o import de torch.optim. Injetar antes de qualquer import.
try:
    import onnxscript.values as _ov

    if not hasattr(_ov, "ParamSchema"):
        _ov.ParamSchema = type("ParamSchema", (), {})
except Exception:
    pass

import torch
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
import logging
import os
import glob
import time
from backend.models.patchtst import PatchTST
from backend.models.loss import PointQuantileLoss


# --- CONFIGURAÇÃO DE AMBIENTE ---
# Detectar se DirectML (AMD) está disponível ou CPU
try:
    import torch_directml

    device = torch_directml.device()
    logging.info(f"🚀 [SOTA] Hardware: AMD GPU via DirectML ({device})")
except ImportError:
    device = torch.device("cpu")
    logging.info("🚀 [SOTA] Hardware: CPU (DirectML not found)")

# Configuração de Logs
log_path = os.path.join(os.getcwd(), "backend", "training_sota.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
)

# --- DATASETS ---


class MultiAssetSOTADataset(Dataset):
    def __init__(self, data, seq_len=60, pred_len=5):
        self.data = data.astype(np.float32)
        self.seq_len = seq_len
        self.pred_len = pred_len

    def __len__(self):
        return len(self.data) - self.seq_len - self.pred_len + 1

    def __getitem__(self, idx):
        x = self.data[idx : idx + self.seq_len]
        # Alvo é o próximo preço do WIN$ (primeira coluna)
        y = self.data[idx + self.seq_len : idx + self.seq_len + self.pred_len, 0:1]
        return torch.tensor(x), torch.tensor(y)


def load_all_sota_data(data_dir="data/sota_training"):
    """
    Carrega e sincroniza os 5 ativos mestres + features de microestrutura (CVD, OFI, volume_ratio).
    Colunas incluídas: close por ativo + [cvd, ofi, volume_ratio] do WIN$ quando disponíveis.
    """
    files = glob.glob(os.path.join(data_dir, "training_*_MASTER.csv"))
    if not files:
        logging.error(f"Nenhum dado encontrado em {data_dir}")
        return None

    dfs = {}
    micro_df = None  # Features de microestrutura do WIN$

    for f in files:
        sym = os.path.basename(f).split("_")[1]
        df = pd.read_csv(f)
        df["time"] = pd.to_datetime(df["time"])
        df = df.drop_duplicates(subset="time").set_index("time")
        dfs[sym] = df[["close"]].rename(columns={"close": sym})

        # Extrair features de microestrutura apenas do WIN$ (ativo principal)
        if sym == "WIN$":
            micro_cols = [c for c in ["cvd", "ofi", "volume_ratio"] if c in df.columns]
            if micro_cols:
                micro_df = df[micro_cols]
                logging.info(f"🔬 Features de microestrutura encontradas: {micro_cols}")

    # Join interno para alinhamento temporal perfeito
    master_df = pd.concat(dfs.values(), axis=1, join="inner")

    # Ordem SOTA: WIN$ como primeira coluna (Target Principal)
    cols = ["WIN$", "WDO$", "VALE3", "PETR4", "ITUB4"]
    actual_cols = [c for c in cols if c in master_df.columns]
    master_df = master_df[actual_cols]

    # [FASE 3] Adicionar CVD/OFI como canais extras se disponíveis
    if micro_df is not None:
        master_df = master_df.join(micro_df, how="left").fillna(0.0)
        logging.info(
            f"🔬 Dataset enriquecido com microestrutura: {list(master_df.columns)}"
        )

    logging.info(
        f"📊 Dataset SOTA carregado: {master_df.shape} ({len(master_df.columns)} canais)"
    )

    # Normalização Z-Score por coluna
    master_df = (master_df - master_df.mean()) / (master_df.std() + 1e-8)

    return master_df


# --- TRAINING ENGINE ---


def train_sota(epochs=10, batch_size=128, lr=0.0001):
    logging.info("⚡ Iniciando Treinamento SOTA Precisão Absoluta...")

    df = load_all_sota_data()
    if df is None:
        return

    n_channels = len(df.columns)
    dataset = MultiAssetSOTADataset(df.values)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Inicializar PatchTST SOTA
    # Context=60, Pred=5, Layers=3 (Deep precision), Heads=4
    model = PatchTST(
        c_in=n_channels,
        context_window=60,
        target_window=5,
        n_layers=3,
        n_heads=4,
        d_model=128,
        n_quantiles=3,
    ).to(device)

    criterion = PointQuantileLoss(quantiles=[0.1, 0.5, 0.9], weight_mse=0.6)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2
    )

    best_loss = float("inf")
    start_time = time.time()

    for epoch in range(epochs):
        model.train()
        total_loss = 0

        for i, (x, y) in enumerate(loader):
            x, y = x.to(device), y.to(device)

            optimizer.zero_grad()
            preds = model(x)

            loss = criterion(preds, y)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

            if i % 50 == 0:
                logging.info(
                    f"Epoch {epoch + 1}/{epochs} | Batch {i}/{len(loader)} | Loss: {loss.item():.6f}"
                )

        avg_loss = total_loss / len(loader)
        scheduler.step(avg_loss)

        logging.info(f"⭐ Epoch {epoch + 1} Concluída | Avg Loss: {avg_loss:.6f}")

        # Salvar checkpoint PyTorch
        if avg_loss < best_loss:
            best_loss = avg_loss
            weights_path = "backend/patchtst_weights_sota.pth"
            torch.save(model.state_dict(), weights_path)
            logging.info(f"💾 Melhor modelo salvo: {avg_loss:.6f}")

    elapsed = (time.time() - start_time) / 60
    logging.info(
        f"✅ Treinamento concluído em {elapsed:.2f} min. Melhor Loss: {best_loss:.6f}"
    )

    # --- EXPORT TO ONNX (SOTA STABILITY) ---
    export_to_onnx(model, n_channels)


def export_to_onnx(model, n_channels):
    """
    Exporta para ONNX usando backend legado (sem dynamo/onnxscript).
    Regras: FLOAT32 apenas, sem dynamic_axes (AMD/DirectML estabilidade).
    Compatível com torch 2.4.x + onnx 1.20.x.
    """
    logging.info("⚙️ Exportando para ONNX (modo legado — AMD/DirectML compatible)...")
    model.eval()
    model.cpu()

    dummy_input = torch.randn(1, 60, n_channels, dtype=torch.float32)
    onnx_path = "backend/patchtst_weights_sota_optimized.onnx"

    try:
        # [ANTIGRAVITY RULES] Nunca usar dynamic_axes para o SOTA model.
        # Força backend legado com torch.onnx sem acionar onnxscript/dynamo.
        with torch.no_grad():
            torch.onnx.export(
                model,
                dummy_input,
                onnx_path,
                export_params=True,
                opset_version=14,
                do_constant_folding=True,
                input_names=["input"],
                output_names=["output"],
                dynamic_axes=None,  # [ANTIVIBE-CODING] fixed axes only
                verbose=False,
            )
        logging.info(f"✅ ONNX Exportado: {onnx_path}")
    except Exception as e:
        logging.error(f"❌ Falha no export ONNX: {repr(e)}")
        # Salvar checkpoint PyTorch como fallback
        fallback = onnx_path.replace(".onnx", "_fallback.pth")
        torch.save(model.state_dict(), fallback)
        logging.info(f"💾 Fallback PyTorch salvo: {fallback}")


if __name__ == "__main__":
    train_sota(epochs=15, batch_size=64, lr=0.0001)
