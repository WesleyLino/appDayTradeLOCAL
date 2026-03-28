import sys
import os
import pandas as pd
import numpy as np
import asyncio

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.ai_core import InferenceEngine

async def test_onnx_real_path():
    print("🔍 Testando motor de inferência com patchtst_weights_sota.pth...")
    engine = InferenceEngine("backend/patchtst_weights_sota.pth")
    
    # Criar um dataframe de 60 linhas com dados fictícios
    df = pd.DataFrame({
        "open": np.random.randn(60) + 120000,
        "high": np.random.randn(60) + 120010,
        "low": np.random.randn(60) + 119990,
        "close": np.random.randn(60) + 120000,
        "tick_volume": np.random.randint(100, 1000, 60),
        "cvd": np.random.randn(60),
        "ofi": np.random.randn(60),
        "volume_ratio": np.ones(60)
    })
    
    print(f"Shape do DF: {df.shape}")
    result = await engine.predict(df)
    print("Resultado da Inferência:")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_onnx_real_path())
