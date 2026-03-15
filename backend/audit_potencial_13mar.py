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

# Configuração de Logging (PT-BR)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Audit13Mar")


async def analyze_potencial_13mar():
    logger.info("🤖 [AUDIT-13MAR] Iniciando Diagnóstico de Potencial SOTA v22...")

    # 1. Carregar Parâmetros Atuais
    try:
        with open("backend/v22_locked_params.json", "r") as f:
            current_params = json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar parâmetros: {e}")
        return

    # 2. Inicializar MetaTrader 5
    if not mt5.initialize():
        logger.error("❌ Falha MT5")
        return

    symbol = "WIN$"

    # 3. Preparar Backtest (Ampliando n_candles para ter histórico de sinais)
    bt = BacktestPro(
        symbol=symbol,
        capital=3000.0,
        n_candles=1500,  # Pega dados suficientes para cobrir o dia e ter histórico
    )

    # Injetar AICore e configurar filtros
    ai = AICore()
    bt.use_ai_core = True
    bt.ai = ai

    # [IMPORTANTE] Ajustar parâmetros de confiança para a auditoria se necessário
    # bt.opt_params['confidence_threshold'] = 0.50 # Ver o que a IA detecta

    logger.info("📊 Coletando dados reais e processando simulação...")
    await bt.run()

    # 4. Processar Resultados de Hoje (13/03)
    today = datetime(2026, 3, 13).date()
    trades_today = [t for t in bt.trades if t["entry_time"].date() == today]

    pnl_total = sum(t.get("pnl_fin", 0) for t in trades_today)

    logger.info("\n--- [ BALANÇO REAL SOTA - 13/03 ] ---")
    logger.info(f"✅ Trades Executados: {len(trades_today)}")
    logger.info(f"💰 PnL Total: R$ {pnl_total:.2f}")

    # 5. Auditoria de Oportunidades (Shadow Audit)
    shadow = bt.shadow_signals
    logger.info("\n--- [ SHADOW AUDIT (POTENCIAL) ] ---")
    logger.info(f"🔍 Candidatos Identificados: {shadow.get('v22_candidates', 0)}")
    logger.info(f"🚫 Vetados por Baixa Confiança IA: {shadow.get('filtered_by_ai', 0)}")
    logger.info(
        f"🚫 Vetados por Fluxo/Bias: {shadow.get('filtered_by_flux', 0) + shadow.get('filtered_by_bias', 0)}"
    )

    reasons = shadow.get("veto_reasons", {})
    if reasons:
        logger.info("\n🛠️ Detalhes dos Vetos IA:")
        for r, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"   - {r}: {count}")

    # 6. Análise de Assertividade por Direção
    buys = [t for t in trades_today if t["side"] == "buy"]
    sells = [t for t in trades_today if t["side"] == "sell"]

    logger.info(
        f"\n📈 COMPRAS: {len(buys)} | Ganhos: {len([t for t in buys if t['pnl_fin'] > 0])}"
    )
    logger.info(
        f"📉 VENDAS: {len(sells)} | Ganhos: {len([t for t in sells if t['pnl_fin'] > 0])}"
    )

    # 7. Diagnóstico e Melhoria
    logger.info("\n💡 [DIAGNÓSTICO FINAL]")
    if len(trades_today) < 1 and shadow.get("v22_candidates", 0) > 5:
        logger.info(
            "A IA viu as oportunidades, mas os filtros de segurança (confidence, rigor) os vetaram."
        )
        logger.info("Sugestão: Calibrar 'confidence_relax_factor' para 1.15.")
    elif len(trades_today) > 0 and (pnl_total < 0):
        logger.info(
            "Trades realizados entraram em stop. Verifique Trailing Stop ou Distância de SL."
        )
    else:
        logger.info(
            "Sistema operando com máxima assertividade para o capital de R$ 3k."
        )

    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(analyze_potencial_13mar())
