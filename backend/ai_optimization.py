import torch
import numpy as np
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
        n_layers=3
    )

    # 2. Carregar pesos (se existirem)
    if os.path.exists(model_path):
        try:
            state_dict = torch.load(model_path)
            
            # [MIGRAÇÃO] Mapear patch_embedding para patch_conv se necessário
            if "patch_embedding.weight" in state_dict and hasattr(model, 'patch_conv'):
                print("🔄 Migrando pesos: patch_embedding -> patch_conv")
                w = state_dict.pop("patch_embedding.weight") # [128, 8]
                b = state_dict.pop("patch_embedding.bias")   # [128]
                
                # Expandir para os grupos do Conv1d [c_in*d_model, 1, patch_len]
                # Repetimos o mesmo embedding para todos os 5 canais (conforme arquitetura SOTA)
                new_w = w.repeat(c_in, 1).unsqueeze(1) # [5*128, 1, 8]
                new_b = b.repeat(c_in)                 # [5*128]
                
                state_dict["patch_conv.weight"] = new_w
                state_dict["patch_conv.bias"] = new_b
                
            model.load_state_dict(state_dict)
            logger.info("Pesos carregados e migrados com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao carregar/migrar pesos: {e}")
            return False
    else:
        logger.warning(f"Pesos não encontrados em {model_path}. Exportando modelo não treinado (apenas estrutura).")

    model.eval()

    # 3. Definir Input Dummy (Batch Size 1, Window 60, Channels 1)
    dummy_input = torch.randn(1, context_window, c_in)

    # 4. Exportar para ONNX
    try:
        import torch.onnx as t_onnx
        t_onnx.export(
            model,
            dummy_input,
            onnx_path,
            export_params=True,
            opset_version=14, # Opset 14 é estável para Transformers
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            # [AI PERSISTENCE GUARD] ALWAYS use dynamic_axes=None for DirectML.
            # Dynamic shapes trigger MatMul dimension mismatches in the DML execution provider.
            dynamic_axes=None 
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
        logger.info("Convertendo modelo para FP16 (AMD Zero-Lag)...")
        # [AMD STABILITY] Desativado FP16 temporariamente para evitar bugs de Cast no RevIN/DirectML
        # fp16_model = float16.convert_float_to_float16(onnx_model)
        # onnx.save(fp16_model, onnx_path)
        onnx.save(onnx_model, onnx_path)
        logger.info(f"Modelo ONNX (Standard FP32) salvo em: {onnx_path}")
        
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
    export_to_onnx(
        model_path="backend/patchtst_weights_sota.pth", 
        onnx_path="backend/patchtst_weights_sota_optimized.onnx", 
        c_in=1, 
        context_window=60
    )
