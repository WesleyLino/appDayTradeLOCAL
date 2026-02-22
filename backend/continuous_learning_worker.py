import time
import subprocess
import logging
import os
import json
from datetime import datetime

# Configuração de log
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, 'continuous_learning.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_optimization_cycle():
    """
    Executa o optimizer.py silenciosamente para aprimorar os parâmetros.
    Combate o Concept Drift (Degradação Temporal Silenciosa).
    """
    logging.info("🧠 Iniciando Ciclo de Aprendizado Contínuo (Walk-Forward Analysis)...")
    
    # Define os parâmetros da otimização oculta
    # Usamos um N menor (ex: 5000) para otimização rápida diária/semanal
    cmd = [
        "python", 
        os.path.join(os.path.dirname(__file__), "optimizer.py"),
        "--symbol", "WIN$",
        "--n", "5000",
        "--silent" # Argumento hipotético/opcional para reduzir I/O se implementado no optimizer
    ]
    
    try:
        # Executa o processo bloqueando até terminar
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            logging.info("✅ Ciclo de Aprendizado concluído com sucesso. best_params_WIN.json atualizado.")
        else:
            logging.error(f"❌ Erro durante a otimização:\n{stderr}")
            
    except Exception as e:
        logging.error(f"❌ Falha crítica no Continuous Learning Worker: {str(e)}")

def main():
    logging.info("🚀 Sistema Imunológico Autônomo Iniciado. Monitorando Concept Drift...")
    
    # Em produção, isso seria gerenciado por um CronJob (Linux) ou Agendador de Tarefas (Windows).
    # Como worker daemon, ele dorme e acorda periodcamente.
    # Exemplo: Rodar a cada 24 horas (86400 segundos)
    
    CYCLE_INTERVAL = 86400 # 24 horas
    
    # Para teste imediato, rodamos uma vez!
    run_optimization_cycle()
    
    # Loop infinito para daemon (descomentar se for rodar como serviço)
    # while True:
    #     time.sleep(CYCLE_INTERVAL)
    #     run_optimization_cycle()

if __name__ == "__main__":
    main()
