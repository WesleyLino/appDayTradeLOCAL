import sys
import os
import pandas as pd
import numpy as np
import asyncio

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.ai_core import InferenceEngine

async def test_zeros():
    print("🔍 Testando motor de inferência com ZEROS...")
    engine = InferenceEngine("backend/patchtst_weights_sota.pth")
    
    # Criar um dataframe de 60 linhas com zeros
    df = pd.DataFrame({
        "open": np.zeros(60),
        "high": np.zeros(60),
        "low": np.zeros(60),
        "close": np.zeros(60),
        "tick_volume": np.zeros(60),
        "cvd": np.zeros(60),
        "ofi": np.zeros(60),
        "volume_ratio": np.ones(60)
    })
    
    result = await engine.predict(df)
    print("Resultado da Inferência (Zeros):")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_zeros())
