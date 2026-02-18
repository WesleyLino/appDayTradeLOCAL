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
from backend.ai_optimization import export_to_onnx

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
    model = PatchTST(
        c_in=1, # Apenas 'Close' no treinamento simplificado
        context_window=60, 
        target_window=5,
        d_model=128, 
        n_heads=4, 
        n_layers=2
    )
    criterion = PointQuantileLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Loop de Treinamento Rápido (Cold Start)
    epochs = 5
    model.train()
    
    for epoch in range(epochs):
        total_loss = 0
        for x, y in dataloader:
            optimizer.zero_grad()
            outputs = model(x) # [Batch, Target_Window, Channels]
            
            # Selecionar apenas o canal 'Close' (índice 3 assumido) e o último passo de tempo
            # outputs: [Batch, Target_Window, 7] -> Queremos [Batch, 1] (Close do último step)
            # Mas y é [Batch].
            # Ajustando para comparar:
            
            # Assumindo que queremos prever o Close do próximo step (Target_Window=1 no dataset?)
            # O Dataset retorna y como o valor do Close.
            
            # Pegamos o output do Close (idx 3)
            # Se model.target_window > 1, pegamos o último? Ou treinamos todos?
            # Dataset retorna 1 valor `y`. Então pegamos o último do target window ou o primeiro?
            # TradingDataset: y = data[idx + seq_len : idx + seq_len + pred_len] -> y[0]
            # Então target é 1 step ahead e apenas 1 valor.
            
            pred_close = outputs[:, -1, 0].unsqueeze(-1) # [Batch, 1]
            target = y.unsqueeze(-1) # [Batch, 1]
            
            # Loss (PointQuantileLoss vai usar MSE já que temos apenas 1 canal de predição)
            loss = criterion(pred_close, target)
            
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        logging.info(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}")
        
    # Salvar Pesos
    save_path = "backend/patchtst_weights.pth"
    torch.save(model.state_dict(), save_path)
    logging.info(f"Modelo salvo com sucesso em: {save_path}")
    
    # [AMD Aceleração] Exportar para ONNX automaticamente
    logging.info("Iniciando exportação automática para ONNX (DirectML)...")
    if export_to_onnx(model_path=save_path, c_in=1, context_window=60):
        logging.info("✅ Exportação ONNX concluída com sucesso!")
    else:
        logging.error("❌ Falha na exportação ONNX.")

if __name__ == "__main__":
    import sys
    # Adiciona o diretório raiz ao path para imports funcionarem se rodado diretamente
    sys.path.append(os.getcwd())
    train()
