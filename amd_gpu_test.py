import onnxruntime as ort
import numpy as np
import time
import os
import logging

# Configuração de Logging para arquivo (ASCII APENAS)
logging.basicConfig(
    filename='gpu_test_report.log',
    filemode='w',
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_amd_gpu_usage():
    log_lines = []
    
    def log(msg):
        print(msg)
        log_lines.append(msg)
        logging.info(msg)

    log("="*50)
    log("AMD GPU (DIRECTML) USE TEST")
    log("="*50)

    # 1. Provedores
    providers = ort.get_available_providers()
    log(f"Available Providers: {providers}")

    # 2. Caminhos
    potential_paths = [
        "backend/patchtst_weights_sota_optimized.onnx",
        "backend/patchtst_optimized.onnx"
    ]
    
    onnx_path = None
    for path in potential_paths:
        if os.path.exists(path):
            onnx_path = path
            break
    
    if not onnx_path:
        log("ERROR: ONNX model not found!")
        return

    log(f"Loading Model: {onnx_path}")

    # 3. Sessao
    try:
        sess_options = ort.SessionOptions()
        # Nao usar logs verbosos para evitar UnicodeErrors
        sess_options.log_severity_level = 3 
        
        session = ort.InferenceSession(
            onnx_path, 
            sess_options=sess_options, 
            providers=['DmlExecutionProvider', 'CPUExecutionProvider']
        )
        
        active_providers = session.get_providers()
        log(f"Active Providers: {active_providers}")
        
        if 'DmlExecutionProvider' in active_providers:
            log("SUCCESS: AMD GPU (DirectML) is ACTIVE.")
        else:
            log("WARNING: Running on CPU (DirectML not selected/available).")

    except Exception as e:
        log(f"FATAL ERROR during session init: {repr(e)}")
        return

    # 4. Latencia
    try:
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        c_in = input_shape[2]
        dummy_input = np.random.randn(1, 60, c_in).astype(np.float32)

        log(f"Running 100 iterations (Batch=1, Seq=60, Ch={c_in})...")
        
        latencies = []
        for _ in range(100):
            t0 = time.time()
            session.run(None, {input_name: dummy_input})
            latencies.append(time.time() - t0)
        
        avg_lat = np.mean(latencies) * 1000
        log(f"Average Latency: {avg_lat:.2f}ms")
        log(f"Total Time: {sum(latencies):.4f}s")
        log("TERMINATED SUCCESSFULLY")
    except Exception as e:
        log(f"FATAL ERROR during inference: {repr(e)}")

    log("="*50)

    # Salvar report final limpo
    with open('gpu_test_report.txt', 'w') as f:
        f.write('\n'.join(log_lines))

if __name__ == "__main__":
    test_amd_gpu_usage()
