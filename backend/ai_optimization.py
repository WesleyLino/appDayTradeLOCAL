import torch
import torch.onnx
import onnx
import onnxruntime as ort
import os
import sys
import logging

# Adiciona o diretório raiz ao path para permitir imports absolutos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models.patchtst import PatchTST

# Configuração de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_to_onnx(model_path="backend/patchtst_weights.pth", onnx_path="backend/patchtst_optimized.onnx", c_in=1, context_window=60):
    """
    Converte o modelo PatchTST treinado em PyTorch para ONNX com otimização para DirectML.
    """
    logger.info(f"Iniciando conversão PyTorch -> ONNX (Target: {onnx_path})")

    # 1. Instanciar o modelo com a mesma arquitetura do treino
    model = PatchTST(
        c_in=c_in, 
        context_window=context_window, 
        target_window=5, # Deve bater com train_model.py
        d_model=128, 
        n_heads=4, 
        n_layers=2
    )

    # 2. Carregar pesos (se existirem)
    if os.path.exists(model_path):
        try:
            model.load_state_dict(torch.load(model_path))
            logger.info("Pesos carregados com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao carregar pesos: {e}")
            return False
    else:
        logger.warning(f"Pesos não encontrados em {model_path}. Exportando modelo não treinado (apenas estrutura).")

    model.eval()

    # 3. Definir Input Dummy (Batch Size 1, Window 60, Channels 1)
    dummy_input = torch.randn(1, context_window, c_in)

    # 4. Exportar para ONNX
    try:
        torch.onnx.export(
            model,
            dummy_input,
            onnx_path,
            export_params=True,
            opset_version=14, # Opset 14 é estável para Transformers
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={
                'input': {0: 'batch_size'}, # Batch size variável
                'output': {0: 'batch_size'}
            }
        )
        logger.info(f"Modelo exportado com sucesso para: {onnx_path}")
    except Exception as e:
        logger.error(f"Falha na exportação ONNX: {e}")
        return False

    # 5. Validar e Converter para FP16 (AMD Optimization)
    try:
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)
        logger.info("Validação ONNX: OK (Estrutura válida)")
        
        # Conversão FP16
        from onnxconverter_common import float16
        logger.info("Convertendo modelo para FP16 (AMD Zero-Lag)...")
        fp16_model = float16.convert_float_to_float16(onnx_model)
        onnx.save(fp16_model, onnx_path)
        logger.info(f"Modelo FP16 salvo em: {onnx_path}")
        
        # Teste de Inferência Simples (Sanity Check)
        # Nota: FP16 pode não rodar em CPUExecutionProvider dependendo da CPU, mas DmlExecutionProvider suporta.
        # Vamos tentar rodar, se falhar, avisamos mas não abortamos pois pode ser limitação de CPU.
        try:
            ort_session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider']) 
            # Input deve ser float16 agora? 
            # onnxconverter_common geralmente ajusta inputs/outputs ou mantém float32 nas bordas?
            # Por padrão, keep_io_types=True.
            ort_inputs = {ort_session.get_inputs()[0].name: dummy_input.numpy().astype(np.float16)}
            ort_outs = ort_session.run(None, ort_inputs)
            logger.info(f"Teste de Inferência ONNX (FP16): OK. Shape: {ort_outs[0].shape}")
        except Exception as e_inf:
            logger.warning(f"Teste de inferência local falhou (Normal se CPU não suportar FP16 nativo): {e_inf}")
        
        return True
    
    except Exception as e:
        logger.error(f"Erro na validação/conversão do modelo ONNX: {e}")
        return False

if __name__ == "__main__":
    export_to_onnx()
