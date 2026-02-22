import time
import subprocess
import logging
import os
import json
from datetime import datetime, timedelta

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
    Executa o optimizer.py para aprimorar os parâmetros.
    Combate o Concept Drift (Degradação Temporal Silenciosa).
    """
    logging.info("🧠 Iniciando Ciclo de Aprendizado Contínuo (Walk-Forward Analysis)...")

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
            logging.info("✅ Ciclo de Aprendizado concluído. best_params_WIN.json atualizado.")
        else:
            logging.error(f"❌ Erro durante a otimização:\n{stderr}")

    except Exception as e:
        logging.error(f"❌ Falha crítica no Continuous Learning Worker: {str(e)}")


def main():
    logging.info("🚀 Sistema Imunológico Autônomo Iniciado. Monitorando Concept Drift...")

    # Executa ciclo imediato na primeira inicialização
    run_optimization_cycle()

    # Loop daemon: agenda próximo ciclo para as 18:05 (pós-fechamento do pregão B3)
    while True:
        now = datetime.now()
        next_run = now.replace(hour=18, minute=5, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run + timedelta(days=1)

        sleep_secs = (next_run - now).total_seconds()
        logging.info(
            f"⏰ Próximo ciclo: {next_run.strftime('%d/%m/%Y %H:%M')} "
            f"(em {sleep_secs / 3600:.1f}h)"
        )
        time.sleep(sleep_secs)
        run_optimization_cycle()


if __name__ == "__main__":
    main()
