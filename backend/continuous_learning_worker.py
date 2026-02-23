import sys
import time
import subprocess
import logging
import os
import json
from datetime import datetime, timedelta

# --- CORREÇÃO DE ENCODING PARA WINDOWS ---
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# -----------------------------------------

# Configuração de log
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, 'continuous_learning.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


def run_retraining_cycle():
    """
    Executa o re-treino do PatchTST (Deep Learning).
    Atualiza o cérebro da IA com os dados mais recentes.
    """
    logging.info("🧬 Iniciando Ciclo de Re-treino do PatchTST (Deep Learning)...")
    
    # 1. Coleta e Enriquecimento de Dados
    logging.info("📥 Passo 1/3: Coletando e enriquecendo dados históricos...")
    try:
        cmd_data = ["python", "-m", "backend.data_collector_historical"]
        subprocess.run(cmd_data, check=True, text=True, capture_output=True, encoding='utf-8')
        logging.info("✅ Dados MASTER atualizados com CVD/OFI.")
    except Exception as e:
        logging.error(f"❌ Falha na coleta de dados: {e}")
        return False

    # 2. Treino e Exportação ONNX
    logging.info("🏗️ Passo 2/3: Treinando PatchTST e exportando ONNX...")
    try:
        # Usamos o módulo diretamente para herdar os patches de compatibilidade
        cmd_train = ["python", "-m", "backend.train_patchtst"]
        subprocess.run(cmd_train, check=True, text=True, capture_output=True, encoding='utf-8')
        logging.info("✅ PatchTST re-treinado e ONNX exportado com sucesso.")
    except Exception as e:
        logging.error(f"❌ Falha no re-treino do PatchTST: {e}")
        return False

    return True


def run_optimization_cycle():
    """
    Executa o optimizer.py para aprimorar os parâmetros técnicos (BE, Trailing, Flux).
    Passo 3/3 do ciclo de aprendizado.
    """
    logging.info("🧪 Passo 3/3: Iniciando Otimização de Parâmetros (Bayesian Opt)...")

    cmd = [
        "python",
        os.path.join(os.path.dirname(__file__), "optimizer.py"),
        "--symbol", "WIN$",
        "--n", "5000",
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            logging.info("✅ Parâmetros otimizados: best_params_WIN.json atualizado.")
            return True
        else:
            logging.error(f"❌ Erro durante a otimização:\n{stderr}")
            return False

    except Exception as e:
        logging.error(f"❌ Falha crítica no Optimizer: {str(e)}")
        return False


def main():
    logging.info("🚀 Sistema Imunológico Autônomo Iniciado. Monitorando Concept Drift...")

    # Executa ciclo integral na primeira inicialização
    if run_retraining_cycle():
        run_optimization_cycle()

    # Loop daemon: agenda próximo ciclo para as 18:05 (pós-fechamento do pregão B3)
    while True:
        now = datetime.now()
        # Horário estratégico: fim do pregão para processar os dados do dia
        next_run = now.replace(hour=18, minute=5, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run + timedelta(days=1)

        sleep_secs = (next_run - now).total_seconds()
        logging.info(
            f"⏰ Próximo ciclo: {next_run.strftime('%d/%m/%Y %H:%M')} "
            f"(em {sleep_secs / 3600:.1f}h)"
        )
        time.sleep(sleep_secs)
        
        # Executa ciclo integral diário
        if run_retraining_cycle():
            run_optimization_cycle()


if __name__ == "__main__":
    main()
