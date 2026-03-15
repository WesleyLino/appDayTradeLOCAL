import asyncio
import logging
from datetime import time
from backend.mt5_bridge import MT5Bridge
from backend.risk_manager import RiskManager
from backend.ai_core import AICore


async def run_v24_validation():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("v24_Validation")

    bridge = MT5Bridge()
    risk = RiskManager()
    ai = AICore()

    # SETUP v24
    risk.load_optimized_params("WIN$", "backend/v24_locked_params.json")

    logger.info("🧪 Iniciando Validação v24 (Parâmetros HFT)")

    try:
        # 1. Testar AICore Volume-Weighted Score
        avg_vol = 5000.0
        test_vol = 12000.0  # > 2x avg

        decision = ai.calculate_decision(
            obi=2.6,
            sentiment=0.0,
            patchtst_score=0.85,
            regime=1,
            atr=150,
            volatility=0.1,
            hour=10,
            minute=30,
            ofi=1.5,
            current_price=130000,
            spread=1.0,
            sma_20=130000,
            current_vol=test_vol,
            avg_vol_20=avg_vol,
        )

        logger.info(f"✅ SCORE v24: {decision['score']} (Bônus deve estar incluso)")
        if decision["is_momentum_bypass"]:
            logger.info("🔥 SUCESSO: Bypass de Momentum (84%) ativado.")
        else:
            logger.warning("❌ FALHA: Bypass de Momentum não ativado.")

        # 2. Testar Janela de Ouro via get_order_params
        # 10:30 está dentro da janela (10:00 - 11:30)
        t_golden = time(10, 30)
        import MetaTrader5 as mt5

        params_golden = risk.get_order_params(
            "WIN$",
            mt5.ORDER_TYPE_BUY_LIMIT,
            130000,
            2,
            current_atr=150,
            regime=1,
            current_time=t_golden,
        )

        # SL base para Regime 1 (ATR * 1.3) = 150 * 1.3 = 195
        # TP base para Regime 1 (ATR * 1.5) = 150 * 1.5 = 225
        # TP Golden (+50%) = 225 * 1.5 = 337.5

        logger.info(f"🚀 [v24 GOLDEN-WINDOW] TP: {params_golden['tp']} pts")
        if params_golden["tp"] > 250:  # Deve ser ~337
            logger.info("✅ SUCESSO: Multiplicador Janela de Ouro Funcional.")
        else:
            logger.warning("❌ FALHA: Multiplicador Janela de Ouro IGNORADO.")

        # 3. Testar Trailing Assimétrico
        # Venda (Trigger=120, Step=20)
        # Compra (Trigger=150, Step=50)
        tr_buy, lock_buy, step_buy = risk.get_dynamic_trailing_params(150, side="buy")
        tr_sell, lock_sell, step_sell = risk.get_dynamic_trailing_params(
            150, side="sell"
        )

        logger.info(f"🛡️ Trailing Compra: Step={step_buy} | Venda: Step={step_sell}")
        if step_sell < step_buy:
            logger.info(
                "✅ SUCESSO: Trailing Assimétrico (Venda mais agressiva) configurado."
            )
        else:
            logger.warning("❌ FALHA: Trailing simétrico detectado.")

    except Exception as e:
        logger.error(f"Erro na validação: {e}")


if __name__ == "__main__":
    asyncio.run(run_v24_validation())
