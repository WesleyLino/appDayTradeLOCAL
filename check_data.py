import pandas as pd
import os

path = os.path.join("data", "sota_training", "training_WIN$_MASTER.csv")
if os.path.exists(path):
    df = pd.read_csv(path)
    body = (df["close"] - df["open"]).abs()
    hl = (df["high"] - df["low"]).replace(0, 1e-8)
    ofi = body / hl
    print(f"OFI Max: {ofi.max():.4f}")
    print(f"OFI Mean: {ofi.mean():.4f}")
    print(f"OFI Std: {ofi.std():.4f}")
    print(f"OFI > 0.8: {(ofi > 0.8).sum()} samples")
    print(f"OFI > 0.9: {(ofi > 0.9).sum()} samples")
else:
    print(f"Path not found: {path}")
