import asyncio
import logging
import os
import sys
import json
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore
import MetaTrader5 as mt5

# Protocolo de Idioma: Brasileiro
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Backtest13Mar")


async def run_official_backtest():
    logger.info("🎯 [SOTA-OFFICIAL] Iniciando Backtest Consolidado (13/03)...")

    # 1. Carregar Parâmetros Bloqueados (Golden Params)
    try:
        with open("backend/v22_locked_params.json", "r") as f:
            params = json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar parâmetros bloqueados: {e}")
        return

    # 2. Inicializar MetaTrader 5
    if not mt5.initialize():
        logger.error("❌ Falha crítica ao inicializar MetaTrader 5")
        return

    symbol = "WIN$"

    # 3. Configurar BacktestPro
    bt = BacktestPro(
        symbol=symbol,
        capital=params.get("account_config", {}).get("initial_balance", 500.0),
        n_candles=2000,  # Histórico ampliado para o dia todo
    )

    # Injetar IA com calibragem atualizada
    ai = AICore()
    bt.use_ai_core = True
    bt.ai = ai

    # Aplicar parâmetros do JSON diretamente
    bt.opt_params.update(params)

    logger.info(
        f"🚀 Executando Simulação SOTA em {symbol} | Capital: R$ {bt.initial_balance}..."
    )
    await bt.run()

    # 4. Filtrar resultados para o dia 13/03
    today_date = datetime(2026, 3, 13).date()
    today_trades = [t for t in bt.trades if t["entry_time"].date() == today_date]

    # 5. Relatório Final em Português
    logger.info("\n==================================================")
    logger.info("📊 RESULTADO FINAL - 13/03/2026")
    logger.info("==================================================")
    logger.info(f"✅ Trades Operados: {len(today_trades)}")

    total_pnl = sum(t.get("pnl_fin", 0) for t in today_trades)
    logger.info(f"💰 Lucro Líquido do Dia: R$ {total_pnl:.2f}")

    if len(today_trades) > 0:
        win_trades = [t for t in today_trades if t["pnl_fin"] > 0]
        logger.info(
            f"🎯 Assertividade: {(len(win_trades) / len(today_trades)) * 100:.1f}%"
        )

    # Detalhar trades
    for i, t in enumerate(today_trades, 1):
        logger.info(
            f"   Trade {i}: {t['side'].upper()} @ {t['entry_price']} -> Saída: {t['exit_price']} | PnL: R$ {t['pnl_fin']:.2f} ({t['reason']})"
        )

    logger.info("==================================================")
    logger.info("📁 Relatório Visual Completo em: backend/backtest_report.html")

    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(run_official_backtest())
