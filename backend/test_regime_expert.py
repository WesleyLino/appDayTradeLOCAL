import asyncio
import logging
from backend.ai_core import AICore
from backend.risk_manager import RiskManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RegimeExpertTest")


async def test_regime_detection():
    logger.info("🧪 [SMOKE TEST] Iniciando teste de detecção de regime V36 Expert...")

    ai = AICore()
    risk = RiskManager()

    # Simular dados de mercado
    scenarios = [
        {"name": "TENDÊNCIA", "vol": 0.05, "obi": 1.2},
        {"name": "LATERAL", "vol": 0.02, "obi": 0.1},
        {"name": "VOLÁTIL", "vol": 0.25, "obi": 0.5},
    ]

    for sc in scenarios:
        logger.info(f"\n--- Testando cenário: {sc['name']} ---")
        regime = ai.detect_regime(volatility=sc["vol"], obi=sc["obi"])
        logger.info(f"Retorno de detect_regime: {regime} (Tipo: {type(regime)})")

        try:
            params = risk.get_regime_specific_params(regime)
            logger.info(f"Parâmetros Trailing: {params}")
        except Exception as e:
            logger.error(f"Erro ao obter parâmetros para {regime}: {e}")

    logger.info("\n✅ [SMOKE TEST] Verificação concluída.")


if __name__ == "__main__":
    asyncio.run(test_regime_detection())
