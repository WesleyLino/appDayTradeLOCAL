import torch
import sys
import os

# Ajuste de path para importar backend
sys.path.append(os.getcwd())


model_path = "backend/patchtst_weights_sota.pth"

if os.path.exists(model_path):
    print(f"--- Inspecionando {model_path} ---")
    state_dict = torch.load(model_path, map_location="cpu")
    for key, value in state_dict.items():
        if "weight" in key or "pos_embed" in key:
            print(f"{key}: {value.shape}")

    # Tenta inferir d_model do pos_embed
    if "pos_embed" in state_dict:
        # shape: [1, n_patches, d_model]
        pos_shape = state_dict["pos_embed"].shape
        print(f"\nDetectado d_model: {pos_shape[2]}")
        print(f"Detectado n_patches: {pos_shape[1]}")

    # Tenta inferir patch_len do patch_embedding
    if "patch_embedding.weight" in state_dict:
        # shape: [d_model, patch_len]
        pe_shape = state_dict["patch_embedding.weight"].shape
        print(f"Detectado patch_len: {pe_shape[1]}")

else:
    print("Arquivo de pesos não encontrado.")
