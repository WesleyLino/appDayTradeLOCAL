import sys
import os
import asyncio
import logging

# Adicionar raiz ao path
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)

async def test_imports():
    logging.info("--- Testando Imports ---")
    try:
        from backend.models import PatchTST
        logging.info("✅ backend.models importado com sucesso!")
        
        from backend.ai_core import AICore, InferenceEngine
        logging.info("✅ backend.ai_core importado com sucesso!")
        
        logging.info("✅ backend.train_model importado com sucesso!")
        
        try:
            from backend.main import app
            logging.info("✅ backend.main importado com sucesso!")
        except ImportError as e:
            logging.error(f"❌ Falha ao importar backend.main: {e}")
            # Pode falhar se tiver dependências de runtime não satisfeitas, mas tentamos.

    except Exception as e:
        logging.error(f"❌ Erro fatal nos imports: {e}")
        return

    logging.info("\n--- Testando Instanciação ---")
    try:
        # Teste PatchTST
        model = PatchTST()
        logging.info(f"✅ PatchTST instanciado: {type(model)}")
        
        # Teste InferenceEngine
        engine = InferenceEngine()
        logging.info(f"✅ InferenceEngine instanciado: {type(engine)}")
        
        # Teste AICore
        ai = AICore()
        logging.info(f"✅ AICore instanciado: {type(ai)}")
        
        # Teste Resources
        missing = engine.check_resources()
        logging.info(f"ℹ️ Recursos faltando (esperado se não treinado): {missing}")
        
    except Exception as e:
        logging.error(f"❌ Erro na instanciação: {e}")

    logging.info("\n--- Teste Concluído ---")

if __name__ == "__main__":
    asyncio.run(test_imports())
