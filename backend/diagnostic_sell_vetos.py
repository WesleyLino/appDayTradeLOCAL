import asyncio
import logging
from datetime import datetime
import sys
import os

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

# Dicionario global para capturar vetos durante o teste
veto_collector = []


def patched_calculate_decision(self, obi, sentiment, patchtst_score, **kwargs):
    # Chamamos a logica original (copiada ou via super se fosse classe herdada)
    # Mas como queremos ver o veto_reason interno, vamos simular a predicao aqui
    # ou simplesmente rodar a original e ver o retorno.

    # Infelizmente veto_reason e uma variavel local na original.
    # Para capturar sem mudar o arquivo, vamos replicar a logica de decisao basica aqui
    # APENAS para fins de log de diagnostico.

    # 1. Obter direcao do PatchTST
    if isinstance(patchtst_score, dict):
        norm_patchtst = (patchtst_score.get("score", 0.5) - 0.5) * 2
    else:
        norm_patchtst = (patchtst_score - 0.5) * 2

    ai_dir = 1 if norm_patchtst > 0 else -1 if norm_patchtst < 0 else 0

    # Se a IA sugeriu VENDA (ai_dir < 0), vamos ver por que ela pode ser vetada
    if ai_dir < 0:
        # Replicar filtros criticos
        if self.macro_bull_lock:
            veto_collector.append("MACRO_BULL_BLOCK")
        elif self.h1_trend == 1:
            veto_collector.append("H1_BULLISH_TREND_VETO")
        elif kwargs.get("vwap_slope_ema", 0) > 8.0:
            veto_collector.append("VETO_CONTRA_TENDENCIA_VWAP_ALTA")
        elif kwargs.get("bluechips_score", 0) > self.bluechips_veto_threshold:
            veto_collector.append("DIVERGENCIA_BLUECHIPS")
        elif kwargs.get("wdo_aggression", 0) < -self.wdo_veto_threshold:
            veto_collector.append("DIVERGENCIA_MACRO_WDO")
        else:
            # Se passou pelos filtros mas o final_score nao atingiu 25.0
            # (provavelmente por falta de confluencia OBI/Sentiment)
            veto_collector.append("CONFLUENCIA_INSUFICIENTE (OBI/Sentiment)")

    # Retorno real da funcao original para nao quebrar o backtest
    return original_calculate_decision(self, obi, sentiment, patchtst_score, **kwargs)


async def diagnostic_sell_vetos():
    logging.basicConfig(level=logging.ERROR)  # Silenciar outros logs
    print("🔬 INICIANDO DIAGNÓSTICO PROFUNDO: POR QUE NÃO VENDE?")

    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"

    target_dates_str = [
        "19/02/2026",
        "20/02/2026",
        "23/02/2026",
        "24/02/2026",
        "25/02/2026",
        "26/02/2026",
        "27/02/2026",
    ]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]

    base_tester = BacktestPro(symbol=symbol, n_candles=25000, timeframe=timeframe)
    full_data = await base_tester.load_data()

    if full_data is None or full_data.empty:
        print("❌ Erro ao carregar dados.")
        return

    # Backup e Patch
    global original_calculate_decision
    original_calculate_decision = AICore.calculate_decision
    AICore.calculate_decision = patched_calculate_decision

    for target_date in dates_to_test:
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(2500).copy()
        if not any(sliced_data.index.date == target_date):
            continue

        ai_instance = AICore()
        ai_instance.buy_threshold = 75.0
        ai_instance.sell_threshold = 25.0
        ai_instance.bluechips_veto_threshold = 0.6
        ai_instance.wdo_veto_threshold = 3.0

        tester = BacktestPro(
            symbol=symbol, n_candles=2500, timeframe=timeframe, ai_core=ai_instance
        )
        tester.opt_params["use_ai_core"] = True
        tester.data = sliced_data
        await tester.run()

    # Resultados
    from collections import Counter

    counts = Counter(veto_collector)

    print("\n--- 📊 RELATÓRIO DE VETOS DE VENDA (MOTIVOS REAIS) ---")
    if not counts:
        print("⚠️ Nenhum sinal de venda foi sequer gerado pelo PatchTST no período.")
    else:
        for reason, count in counts.most_common():
            print(f"🚫 {reason}: {count} vezes")

    print("\n--- 💡 SUGESTÃO DE MELHORIA ---")
    if "H1_BULLISH_TREND_VETO" in counts or "MACRO_BULL_BLOCK" in counts:
        print(
            "Fator Principal: O mercado estava em forte tendência de alta (Bullish) nos tempos maiores."
        )
        print(
            "A IA agiu corretamente ao vetar vendas contra a tendência primária, evitando stops desnecessários."
        )

    # Restaurar
    AICore.calculate_decision = original_calculate_decision


if __name__ == "__main__":
    asyncio.run(diagnostic_sell_vetos())
