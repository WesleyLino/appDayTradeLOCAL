import asyncio
import logging
import sys
import os

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

# MONKEY PATCH: Relaxar filtros de incerteza da IA para análise de potencial
original_decision = AICore.calculate_decision


def relaxed_decision(
    self, obi, sentiment, patchtst_score, regime=0, atr=0.0, volatility=0.0, hour=0
):
    # Forçamos a incerteza a ser baixa para ver o sinal bruto
    if isinstance(patchtst_score, dict):
        patchtst_score["uncertainty_norm"] = 0.001
    return original_decision(
        self, obi, sentiment, patchtst_score, regime, atr, volatility, hour
    )


AICore.calculate_decision = relaxed_decision


async def run_analysis():
    # Logging simples sem unicode ruidoso
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("INICIANDO SIMULACAO RELAXADA (Feb 23) - Mini Indice")

    symbol = "WIN$"
    capital = 3000.0
    data_path = "backend/data_23feb_m1.csv"

    if not os.path.exists(data_path):
        logging.error("Arquivo de dados nao encontrado.")
        return

    # 2. Configurar BacktestPro com limites reduzidos
    tester = BacktestPro(
        symbol=symbol,
        data_file=data_path,
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=False,
    )

    # MUITO AGRESSIVO (Lower thresholds to capture all V22 triggers)
    tester.opt_params["use_ai_core"] = False
    tester.opt_params["use_flux_filter"] = True
    tester.opt_params["vol_spike_mult"] = 1.0  # Standard requirement

    # 3. Executar Simulação
    report = await tester.run()

    # Analisar o que aconteceu nos bastidores
    shadow = tester.shadow_signals
    print("\nESTATISTICAS DE FILTRO (SHADOW):")
    print(f"- Total Sinais V22 Detectados: {shadow.get('total_missed', 0)}")
    print(f"- Candidatos V22 (RSI+BB):     {shadow.get('v22_candidates', 0)}")
    print(f"- Negados pela IA:            {shadow.get('filtered_by_ai', 0)}")
    print(f"- Negados pelo Fluxo:         {shadow.get('filtered_by_flux', 0)}")
    print(f"- Falhas de Filtro:           {shadow.get('component_fail', {})}")

    # Analisar o Dataframe para ver por que V22 não disparou
    try:
        df = tester.data  # Usa o dataframe com indicadores calculados
        print("\nESTATISTICAS DO MERCADO (INDICADORES REAIS):")
        print(f"- Candles Processados: {len(df)}")
        print(f"- RSI Range: {df['rsi'].min():.1f} a {df['rsi'].max():.1f}")
        print(
            f"- ATR Range: {df['atr_current'].min():.1f} a {df['atr_current'].max():.1f}"
        )

        rsi_low = len(df[df["rsi"] < 30])
        rsi_high = len(df[df["rsi"] > 70])
        print(f"- Oportunidades RSI < 30: {rsi_low}")
        print(f"- Oportunidades RSI > 70: {rsi_high}")

        bb_lower = len(df[df["close"] < df["lower_bb"]])
        bb_upper = len(df[df["close"] > df["upper_bb"]])
        print(f"- Rompimentos BB Inf: {bb_lower}")
        print(f"- Rompimentos BB Sup: {bb_upper}")

        # Amostra dos indicadores
        print("\nAMOSTRA DE INDICADORES (ULTIMOS 5):")
        print(df[["close", "rsi", "atr_current", "upper_bb", "lower_bb"]].tail(5))

    except Exception as e:
        print(f"Erro na analise de mercado: {e}")


if __name__ == "__main__":
    asyncio.run(run_analysis())
