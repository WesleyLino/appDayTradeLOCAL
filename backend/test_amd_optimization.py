import sys
import os
import logging
import asyncio
import numpy as np
import pandas as pd

# Setup paths
sys.path.append(os.getcwd())

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AMD_TEST")

from backend.ai_optimization import export_to_onnx
from backend.ai_core import InferenceEngine

async def test_amd_pipeline():
    logger.info("=== INICIANDO TESTE DE OTIMIZAÇÃO AMD ===\n")

    # 1. Testar Exportação ONNX
    logger.info("[1/3] Testando Exportação ONNX...")
    model_path = "backend/patchtst_weights.pth"
    onnx_path = "backend/patchtst_optimized.onnx"
    
    # Se não existir pesos, export_to_onnx vai criar dummy
    success = export_to_onnx(model_path, onnx_path)
    if not success:
        logger.error("❌ Falha na exportação. Abortando.")
        return
    
    if os.path.exists(onnx_path):
        logger.info(f"✅ Arquivo ONNX criado: {onnx_path}")
    else:
        logger.error("❌ Arquivo ONNX não encontrado após exportação.")
        return

    # 2. Testar InferenceEngine (Carregamento)
    logger.info("\n[2/3] Testando Carregamento no InferenceEngine...")
    engine = InferenceEngine(model_path)
    
    if engine.use_onnx:
        logger.info("✅ ENGINE USANDO ONNX RUNTIME!")
        providers = engine.ort_session.get_providers()
        logger.info(f"   Providers Disponíveis: {providers}")
        if 'DmlExecutionProvider' in providers:
            logger.info("🚀 AMD DIRECTML DETECTADO E ATIVO!")
        else:
            logger.warning("⚠️ DirectML não detectado. Rodando em CPU (mas via ONNX).")
    else:
        logger.error("❌ Engine falhou ao carregar ONNX. Usando PyTorch fallback.")

    # 3. Testar Inferência (Latência)
    logger.info("\n[3/3] Testando Inferência (Latência)...")
    
    # Criar DataFrame Fake (60 candles)
    dummy_data = pd.DataFrame({
        'close': np.random.randn(100) # 100 pontos
    })
    
    # Warm-up já foi no init, mas vamos rodar um predict
    import time
    start = time.perf_counter()
    result = await engine.predict(dummy_data)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    logger.info(f"⏱️ Tempo de Inferência: {elapsed_ms:.2f} ms")
    logger.info(f"   Resultado keys: {result.keys()}")
    
    if "upper_bound" in result and "lower_bound" in result:
        logger.info("✅ Chaves de Incerteza (Conformal) presentes.")
    else:
        logger.error("❌ Chaves 'upper_bound'/'lower_bound' ausentes no resultado!")
    
    if elapsed_ms < 50:
        logger.info("✅ PERFORMANCE APROVADA (< 50ms)")
    else:
        logger.warning(f"⚠️ PERFORMANCE ALTA ({elapsed_ms:.2f}ms) - Verificar Carga de GPU")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_amd_pipeline())
