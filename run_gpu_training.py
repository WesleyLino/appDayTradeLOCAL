import torch
import torch.nn as nn
import torch.optim as optim
import time

def test_dml_training():
    print("🔬 TESTE DE TREINAMENTO HARDWARE (AMD GPU)")
    
    # 1. Verificar disponibilidade
    try:
        import torch_directml
        device = torch_directml.device()
        print(f"✅ DirectML Detectado: {device}")
    except ImportError:
        print("❌ torch-directml NÃO instalado. O treino usará CPU.")
        device = torch.device('cpu')
    
    # 2. Criar modelo e dados simples
    model = nn.Sequential(
        nn.Linear(60 * 5, 256),
        nn.ReLU(),
        nn.Linear(256, 5 * 3)
    ).to(device)
    
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()
    
    # Gerar dados falsos no device
    x = torch.randn(32, 60 * 5).to(device)
    y = torch.randn(32, 5 * 3).to(device)
    
    print(f"🚀 Iniciando micro-treino no device: {device}")
    
    start_time = time.time()
    for i in range(100):
        optimizer.zero_grad()
        output = model(x)
        loss = criterion(output, y)
        loss.backward()
        optimizer.step()
        
        if (i+1) % 20 == 0:
            print(f"Iteração {i+1}/100 - Loss: {loss.item():.4f}")
            
    end_time = time.time()
    print(f"✅ Treino Finalizado em {end_time - start_time:.2f}s")
    
if __name__ == "__main__":
    test_dml_training()
