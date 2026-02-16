import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
import logging
import sys
import os

# Adiciona o diretório raiz ao sys.path para permitir imports absolutos como 'backend.data_collector'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.data_collector import DataCollector
from backend.models import PatchTST, PointQuantileLoss

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TradingDataset(Dataset):
    def __init__(self, data, seq_len=60, pred_len=5):
        self.data = data
        self.seq_len = seq_len
        self.pred_len = pred_len

    def __len__(self):
        return len(self.data) - self.seq_len - self.pred_len + 1

    def __getitem__(self, idx):
        x = self.data[idx : idx + self.seq_len]
        y = self.data[idx + self.seq_len : idx + self.seq_len + self.pred_len]
        # Retornamos x e y. y[0] é o próximo candle (fechamento)
        return torch.tensor(x, dtype=torch.float32).unsqueeze(-1), torch.tensor(y[0], dtype=torch.float32)



def generate_synthetic_data(n_samples=1000):
    """Gera dados de senoide com ruído para cold-start."""
    logging.info("Gerando dados sintéticos para treinamento inicial...")
    x = np.linspace(0, 50 * np.pi, n_samples)
    y = np.sin(x) + np.random.normal(0, 0.1, n_samples)
    
    # Normalização simples (min-max para manter escala controlada)
    y_min, y_max = y.min(), y.max()
    y_norm = (y - y_min) / (y_max - y_min)
    
    return pd.DataFrame({'close': y_norm})

def train():
    logging.info("Iniciando pipeline de treinamento...")
    
    # 1. Tentar coletar dados reais
    try:
        collector = DataCollector("WIN$") # Tenta pegar o ativo atual do MT5 se possível
        # Tenta pegar dados. Se falhar (MT5 fechado), retorna None
        data = collector.get_h1_history(n_candles=2000)
        
        if data is None or data.empty:
            logging.warning("Falha ao coletar dados reais. Usando dados sintéticos.")
            data = generate_synthetic_data()
        else:
             # Normalização Z-Score
            data = collector.apply_zscore(data)
            # Usar a coluna zscore se disponível, senão close
            if 'zscore' in data.columns:
                data = pd.DataFrame({'close': data['zscore'].values}) # PatchTST espera apenas valores numéricos
            else:
                logging.warning("Z-Score não disponível, usando dados brutos normalizados.")
                data = generate_synthetic_data() # Fallback seguro
    except Exception as e:
        logging.error(f"Erro crítico no DataCollector: {e}. Usando dados sintéticos.")
        data = generate_synthetic_data()

    # Prepara dataset
    dataset = TradingDataset(data['close'].values)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
    
    # Modelo e Otimização
    model = PatchTST(seq_len=60, d_model=128, n_heads=4, num_layers=2)
    criterion = PointQuantileLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Loop de Treinamento Rápido (Cold Start)
    epochs = 5
    model.train()
    
    for epoch in range(epochs):
        total_loss = 0
        for x, y in dataloader:
            optimizer.zero_grad()
            outputs = model(x)
            
            # O output do modelo é [batch, 3] (3 quantis)
            # O target y é [batch] (valor real)
            loss = criterion(outputs, y)
            
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        logging.info(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}")
        
    # Salvar Pesos
    save_path = "backend/patchtst_weights.pth"
    torch.save(model.state_dict(), save_path)
    logging.info(f"Modelo salvo com sucesso em: {save_path}")

if __name__ == "__main__":
    import sys
    # Adiciona o diretório raiz ao path para imports funcionarem se rodado diretamente
    sys.path.append(os.getcwd())
    train()
