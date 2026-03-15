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
logger = logging.getLogger("ValidacaoSOTA10Mar")


async def test_10mar_sota_final():
    logger.info("🤖 [TESTE-SOTA-v24] Iniciando Validação do dia 10/03...")

    # 1. Carregar Configurações e Calibragem mais recentes (v24)
    params_file = "backend/v24_locked_params.json"
    if not os.path.exists(params_file):
        logger.error(f"❌ Arquivo de parâmetros {params_file} não encontrado!")
        return

    try:
        with open(params_file, "r") as f:
            config = json.load(f)
        sota_params = config.get("strategy_params", config)
        logger.info(
            f"✅ Configurações v24 carregadas (Confiança: {sota_params.get('confidence_threshold')})"
        )
    except Exception as e:
        logger.error(f"❌ Erro ao ler configurações: {e}")
        return

    # 2. Inicializar Ambiente MetaTrader 5
    if not mt5.initialize():
        logger.error("❌ Falha crítica ao inicializar o terminal MT5.")
        return

    symbol = "WIN$"
    target_date = datetime(2026, 3, 10).date()

    # 3. Configurar Motor de Backtest Pro
    # n_candles=6000 para atingir o dia 10/03 (3 dias atrás) com warm-up
    bt = BacktestPro(symbol=symbol, capital=500.0, n_candles=6000)

    # Injetar AICore com motor ONNX SOTA
    ai = AICore()
    bt.use_ai_core = True
    bt.ai = ai

    # Aplicar calibrações v24
    bt.opt_params.update(sota_params)
    # Desativar filtros que dependem de logs externos (News) para purismo técnico
    bt.opt_params["enable_news_filter"] = False

    logger.info(
        f"📊 Processando simulação para {symbol} (Dia 10/03) em modo SOTA v24..."
    )
    await bt.run()

    # 4. Filtrar Resultados para 10/03
    trades_10mar = [t for t in bt.trades if t["entry_time"].date() == target_date]
    pnl_total = sum(t.get("pnl_fin", 0) for t in trades_10mar)

    logger.info("\n" + "=" * 50)
    logger.info("🏆 RESULTADO DIA 10/03 (SOTA v24)")
    logger.info("==================================================")
    logger.info(f"✅ Trades Realizados: {len(trades_10mar)}")
    logger.info(f"💰 PnL do Dia: R$ {pnl_total:.2f}")

    if trades_10mar:
        for i, t in enumerate(trades_10mar):
            logger.info(
                f"   Trade {i + 1}: {t['side']} | PnL: R$ {t['pnl_fin']:.2f} | Horário: {t['entry_time']}"
            )

    # 5. Auditoria de Vigilância (Shadow Audit)
    shadow = bt.shadow_signals
    logger.info("\n🔍 Auditoria de Vigilância (Shadow):")
    logger.info(f"   - Candidatos v22 Identificados: {shadow.get('v22_candidates', 0)}")
    logger.info(
        f"   - Vetos por Pânico/Risco: {shadow.get('veto_reasons', {}).get('PANICO_MERCADO_SEM_BYPASS', 0)}"
    )
    logger.info(f"   - Vetos por Baixa Confiança IA: {shadow.get('filtered_by_ai', 0)}")

    logger.info(
        f"\n💡 Diagnóstico: O sistema priorizou a {'proteção de capital' if pnl_total == 0 else 'execução sniper'}."
    )
    logger.info("==================================================\n")

    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(test_10mar_sota_final())
