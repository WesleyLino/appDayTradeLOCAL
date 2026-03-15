import logging
from backend.ai_core import AICore

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def verify_meta_filter():
    logging.info("🔬 Iniciando Verificação do Meta-Filter (XGBoost)...")

    ai = AICore()

    # Caso 1: Sinal Forte do PatchTST, mas Contexto Meta-Learner RUIM (Veto esperado)
    # Vamos simular um cenário onde o PatchTST dá um score alto, mas o Meta-Learner
    # (com base no ATR/Volatilidade/Hora) desconfia do sinal.

    logging.info("\n🧪 Teste 1: Sinal forte com Contexto Suspeito (Veto)")
    decision_veto = ai.calculate_decision(
        obi=0.8,
        sentiment=0.5,
        patchtst_score=0.9,  # Sinal fortíssimo de compra
        regime=2,  # Ruído (Contexto difícil)
        atr=10.0,  # Exemplo de ATR
        volatility=0.05,  # Volatilidade alta
        hour=12,
    )

    logging.info(
        f"Resultado: Direction={decision_veto['direction']}, Score={decision_veto['score']:.2f}"
    )
    logging.info(
        f"   Breakdown Meta: prob={decision_veto['breakdown'].get('meta_score'):.2f}, veto={decision_veto['breakdown'].get('veto')}"
    )
    if decision_veto["direction"] == "NEUTRAL":
        if decision_veto.get("breakdown", {}).get("veto") == "META-FILTER":
            logging.info("✅ Veto aplicado com sucesso pelo Meta-Learner.")
        else:
            logging.info("ℹ️ Sinal foi NEUTRAL por score baixo (não veto).")

    # Caso 2: Sinal Forte e Contexto Meta-Learner BOM (Aprovação esperada)
    logging.info("\n🧪 Teste 2: Sinal forte com Contexto Favorável (Aprovação)")
    decision_ok = ai.calculate_decision(
        obi=0.99,  # Fluxo massivo
        sentiment=0.9,
        patchtst_score=0.98,
        regime=1,  # Tendência (Contexto favorável)
        atr=2.0,  # ATR Baixo/Estável
        volatility=0.005,  # Vol baixa
        hour=10,
    )

    logging.info(
        f"Resultado: Direction={decision_ok['direction']}, Score={decision_ok['score']:.2f}"
    )
    if decision_ok["direction"] == "BUY":
        logging.info("✅ Sinal aprovado com sucesso.")
    else:
        logging.info(f"❌ Sinal deveria ser BUY, mas foi {decision_ok['direction']}.")
        logging.info(f"   Breakdown: {decision_ok['breakdown']}")

    logging.info("\n📌 Detalhes Meta-Learner:")
    logging.info(f" - raw_signal_score: {decision_ok['breakdown'].get('ai_score_raw')}")
    logging.info(f" - meta_probability: {decision_ok['breakdown'].get('meta_score')}")


if __name__ == "__main__":
    verify_meta_filter()
