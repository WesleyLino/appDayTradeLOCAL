import sys
import os
import numpy as np
import pandas as pd
import traceback

sys.path.append(os.getcwd())
from backend.ai_core import InferenceEngine


async def final_check():
    engine = InferenceEngine("backend/patchtst_weights_sota.pth")

    # Simular input (5 ativos, 60 candles)
    data = np.random.randn(60, 5).astype(np.float32)
    df = pd.DataFrame(data, columns=["WIN$", "ITUB4", "PETR4", "VALE3", "WDO$"])

    print("\n--- TESTE DE INFERÊNCIA DETALHADO ---")

    # Tentar rodar _predict_sync diretamente para ver o erro sem o try-except do predict
    try:
        print(f"Engine State: ONNX={engine.use_onnx}, Model={engine.model is not None}")
        res = engine._predict_sync(df)
        print(f"✅ SUCESSO: {res}")
    except Exception as e:
        print(f"❌ FALHA NA INFERÊNCIA: {repr(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio

    asyncio.run(final_check())
