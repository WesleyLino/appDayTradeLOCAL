import sys
import os
import numpy as np
import pandas as pd
import traceback

sys.path.append(os.getcwd())
from backend.ai_core import InferenceEngine


async def final_check():
    try:
        engine = InferenceEngine("backend/patchtst_weights_sota.pth")

        # Simular input (5 ativos, 60 candles)
        data = np.random.randn(60, 5).astype(np.float32)
        df = pd.DataFrame(data, columns=["cl1", "cl2", "cl3", "cl4", "cl5"])

        print("--- TESTE DE INFERÊNCIA DIRETO ---")
        try:
            res = await engine.predict(df)
            print(f"Resultado: {res}")
            if res["score"] == 0.5 and res["uncertainty_norm"] == 1.0:
                print("⚠️ ALERTA: Fallback detectado!")
        except Exception:
            print("❌ EXCEÇÃO CAPTURADA NO PREDICT:")
            traceback.print_exc()

    except Exception:
        print("❌ ERRO NA INICIALIZAÇÃO DO ENGINE:")
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio

    asyncio.run(final_check())
