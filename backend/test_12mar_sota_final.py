import asyncio
import logging
import os
import sys
import json
from datetime import datetime

# Adiciona diretório raiz ao path para importações locais
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore
import MetaTrader5 as mt5

# [REGRA-PTBR] Configuração de Logging em Português
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ValidacaoSOTA12Mar")


async def test_12mar_sota_final():
    logger.info("🤖 [TESTE-SOTA-v24] Iniciando Validação do dia 12/03...")

    # 1. Carregar Configurações e Calibragem mais recentes (v24)
    params_file = "backend/v24_locked_params.json"
    if not os.path.exists(params_file):
        logger.error(f"❌ Arquivo de parâmetros {params_file} não encontrado!")
        return

    try:
        with open(params_file, "r") as f:
            config = json.load(f)
        sota_params = config.get("strategy_params", config)
        logger.info("✅ Configurações v24 carregadas.")
    except Exception as e:
        logger.error(f"❌ Erro ao ler configurações: {e}")
        return

    # 2. Inicializar Ambiente MetaTrader 5
    if not mt5.initialize():
        logger.error("❌ Falha crítica ao inicializar o terminal MT5.")
        return

    symbol = "WIN$"
    target_date = datetime(2026, 3, 12).date()

    # 3. Preparar dados específicos para 12/03 (Download para garantir fidelidade)
    # n_candles alto para cobrir o dia anterior e histórico
    bt = BacktestPro(
        symbol=symbol,
        capital=500.0,
        n_candles=3000,  # Aumentado para alcançar o dia 12/03 a partir de 13/03
    )

    ai = AICore()
    bt.use_ai_core = True
    bt.ai = ai
    bt.opt_params.update(sota_params)
    bt.opt_params["enable_news_filter"] = False

    logger.info(
        f"📊 Processando simulação para {symbol} (Dia 12/03) em modo SOTA v24..."
    )
    await bt.run()

    # 4. Filtrar Resultados para 12/03
    trades_12mar = [t for t in bt.trades if t["entry_time"].date() == target_date]
    pnl_total = sum(t.get("pnl_fin", 0) for t in trades_12mar)

    logger.info("\n" + "=" * 50)
    logger.info("🏆 RESULTADO DIA 12/03 (SOTA v24)")
    logger.info("==================================================")
    logger.info(f"✅ Trades Realizados: {len(trades_12mar)}")
    logger.info(f"💰 PnL do Dia: R$ {pnl_total:.2f}")

    if trades_12mar:
        for i, t in enumerate(trades_12mar):
            logger.info(
                f"   Trade {i + 1}: {t['side']} | PnL: R$ {t['pnl_fin']:.2f} | Horário: {t['entry_time']}"
            )

    # Auditoria de Vetos
    shadow = bt.shadow_signals
    logger.info("\n🔍 Auditoria de Vigilância (Shadow):")
    logger.info(
        f"   - Vetos por Pânico/Risco: {shadow.get('veto_reasons', {}).get('PANICO_MERCADO_SEM_BYPASS', 0)}"
    )
    logger.info(f"   - Vetos por Baixa Confiança IA: {shadow.get('filtered_by_ai', 0)}")

    logger.info("==================================================\n")

    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(test_12mar_sota_final())
