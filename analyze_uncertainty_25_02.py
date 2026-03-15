import asyncio
import logging
import sys
import os

# Adicionar o diretório atual ao path para importar os módulos do backend
sys.path.append(os.getcwd())

from backend.ai_core import AICore, InferenceEngine
from backend.backtest_pro import BacktestPro

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def analyze_uncertainty():
    symbol = "WIN$"
    data_file = "data/sota_training/training_WIN$_MASTER.csv"

    if not os.path.exists(data_file):
        logging.error(f"Arquivo de dados não encontrado: {data_file}")
        return

    logging.info("--- DIAGNÓSTICO DE INCERTEZA (25/02) ---")

    # Configuração para o dia 25/02
    # Precisamos de candles suficientes para o dia de hoje
    tester = BacktestPro(symbol=symbol, n_candles=1000, use_ai_core=True)

    # Carregar dados
    df = await tester.load_data()
    if df is None or len(df) == 0:
        logging.error("Falha ao carregar dados.")
        return

    # Filtrar apenas o dia 25/02
    today_str = "2026-02-25"
    df_today = df[df.index.strftime("%Y-%m-%d") == today_str]

    if len(df_today) == 0:
        logging.warning(
            "Nenhum dado encontrado para 2026-02-25. Tentando o último dia disponível."
        )
        last_date = df.index[-1].strftime("%Y-%m-%d")
        df_today = df[df.index.strftime("%Y-%m-%d") == last_date]
        logging.info(f"Analisando dados de: {last_date}")

    # Inicializar Inference Engine
    inference = InferenceEngine(model_path="backend/patchtst_weights_sota.pth")
    ai = AICore()
    ai.inference_engine = inference

    findings = []

    # Analisar pontos de alta incerteza
    logging.info(f"Processando {len(df_today)} candles...")

    for i in range(len(df_today)):
        # Pegar o slice dos últimos 60 candles até este ponto
        current_time = df_today.index[i]
        df_slice = df[df.index <= current_time].tail(60)

        if len(df_slice) < 60:
            continue

        # Predição
        try:
            pred = await inference.predict(df_slice)
            uncertainty = pred.get("uncertainty_norm", 0)

            # Se a incerteza for alta (> 50% ou o pico relatado)
            if uncertainty > 1.0:  # 100%+
                findings.append(
                    {
                        "time": current_time,
                        "uncertainty": uncertainty,
                        "close": df_slice.iloc[-1]["close"],
                        "volatility": df_slice.iloc[-1].get("volatility", 0),
                        "atr": df_slice.iloc[-1].get("atr", 0),
                    }
                )
        except Exception:
            continue

    if findings:
        # Sort by uncertainty to find the peak
        findings.sort(key=lambda x: x["uncertainty"], reverse=True)
        peak = findings[0]

        print("\n--- PICO DE INCERTEZA DETECTADO ---")
        print(f"Horário: {peak['time']}")
        print(f"Incerteza: {peak['uncertainty']:.2%}")
        print(f"Preço: {peak['close']}")
        print(f"Volatilidade/ATR: {peak['volatility']:.2f} / {peak['atr']:.2f}")

        # Analisar a vizinhança do pico
        print("\n--- CONTEXTO DO MERCADO NO PICO ---")
        idx = df.index.get_loc(peak["time"])
        context = df.iloc[idx - 5 : idx + 1]

        # Check columns existence
        cols_to_print = ["open", "high", "low", "close"]
        if "tick_volume" in context.columns:
            cols_to_print.append("tick_volume")
        elif "volume" in context.columns:
            cols_to_print.append("volume")

        print(context[cols_to_print])

        # Propose probable cause based on available metrics
        vol_peak = peak["volatility"]
        vol_avg = context["volatility"].mean() if "volatility" in context.columns else 0

        if vol_peak > vol_avg * 1.5 and vol_avg > 0:
            print(
                "\nCAUSA PROVÁVEL: Expansão súbita de volatilidade (Flash Volatility)."
            )
        else:
            print(
                "\nCAUSA PROVÁVEL: Desajuste de resíduos (Model Drift) ou Microestrutura Extrema (OBI/Sentiment)."
            )
    else:
        print("\nNenhum pico de incerteza extrema (>100%) detectado nos dados atuais.")


if __name__ == "__main__":
    asyncio.run(analyze_uncertainty())
