import asyncio
import logging
import pandas as pd
import os
import sys
import json
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# Adiciona diretório raiz ao path para importações locais
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro

# [REGRA-PTBR] Monitoramento de Auditoria SOTA
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Auditoria27Fev")

async def run_audit_27feb():
    logger.info("🛡️ [SOTA-v24.5] Iniciando Auditoria Focada de 1 Dia: 27/02/2026")
    logger.info("💰 Capital Inicial: R$ 500.00 | Alocação: 1 Lote (WIN)")

    # 1. Inicializar MetaTrader 5
    if not mt5.initialize():
        logger.error("❌ Falha crítica ao inicializar o terminal MT5.")
        return

    symbol = "WIN$"
    timeframe = mt5.TIMEFRAME_M1

    # Coleta de dados: 26/02 (warmup) e 27/02 (audit)
    date_from = datetime(2026, 2, 26, 9, 0)
    date_to = datetime(2026, 2, 27, 18, 0)

    logger.info(f"📊 Sincronizando dados históricos via MT5: {date_from.strftime('%d/%m')} até {date_to.strftime('%d/%m')}...")
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)

    if rates is None or len(rates) == 0:
        logger.error("❌ Falha ao coletar dados do MT5. Verifique se o ativo WIN$ está no Market Watch.")
        mt5.shutdown()
        return

    df_rates = pd.DataFrame(rates)
    df_rates["time"] = pd.to_datetime(df_rates["time"], unit="s")
    df_rates.set_index("time", inplace=True)

    # Injeção de Microestrutura simplificada para compatibilidade SOTA
    df_rates["cvd_normal"] = (df_rates["close"] - df_rates["open"]) / (df_rates["high"] - df_rates["low"]).replace(0, 1)
    df_rates["ofi_normal"] = df_rates["tick_volume"] * df_rates["cvd_normal"]
    df_rates["trap_index"] = 0.0

    logger.info(f"✅ {len(df_rates)} candles processados para simulação.")

    # 2. Configurar BacktestPro com Capital de R$ 500
    bt = BacktestPro(
        symbol=symbol, 
        initial_balance=500.0,
        base_lot=1
    )
    bt.data = df_rates

    async def dummy_load():
        return bt.data
    bt.load_data = dummy_load

    # Sincronização SOTA v24.5 Parâmetros
    params_path = "backend/v24_locked_params.json"
    sota_params = {}
    if os.path.exists(params_path):
        with open(params_path, "r") as f:
            config = json.load(f)
        sota_params = config.get("strategy_params", config)
        logger.info(f"🎯 Parâmetros SOTA v24.5 carregados.")
    
    # Garantir travas específicas para R$ 500
    bt.opt_params.update(sota_params)
    bt.opt_params["base_lot"] = 1 # Forçado para capital baixo
    bt.opt_params["dynamic_lot"] = False
    bt.opt_params["enable_news_filter"] = False # Histórico puro

    # 3. Execução da Simulação
    logger.info("🚀 Simulando motor de HFT (High Fidelity)...")
    await bt.run()

    # 4. Análise de Resultados 27/02
    target_date = datetime(2026, 2, 27).date()
    trades_day = [t for t in bt.trades if t["entry_time"].date() == target_date]
    
    buys = [t for t in trades_day if t["side"] == "buy"]
    sells = [t for t in trades_day if t["side"] == "sell"]
    
    total_pnl = sum(t.get("pnl_fin", 0) for t in trades_day)
    win_rate = (len([t for t in trades_day if t.get("pnl_fin", 0) > 0]) / len(trades_day) * 100) if trades_day else 0

    logger.info("\n" + "═" * 60)
    logger.info(f"📋 RELATÓRIO DE AUDITORIA - 27/02/2026")
    logger.info(f"💰 Resultado Financeiro: R$ {total_pnl:.2f}")
    logger.info(f"📊 Atividade: {len(trades_day)} trades | Assertividade: {win_rate:.1f}%")
    logger.info(f"📈 Compras: {len(buys)} | 📉 Vendas: {len(sells)}")
    logger.info(f"📉 Max Drawdown Simulado: R$ {bt.max_drawdown:.2f}")
    logger.info(f"🔎 Oportunidades Perdidas (Shadow): {bt.shadow_signals['total_missed']}")
    
    if bt.shadow_signals['total_missed'] > 0:
        logger.info("   Motivos Principais:")
        for reason, count in bt.shadow_signals['veto_reasons'].items():
            logger.info(f"   - {reason}: {count}")
    
    logger.info("═" * 60)

    # Exportar resultados para análise posterior
    results = {
        "date": "2026-02-27",
        "pnl": total_pnl,
        "trades": trades_day,
        "shadow": bt.shadow_signals,
        "drawdown": bt.max_drawdown
    }
    
    with open("backend/audit_27feb_results.json", "w") as f:
        json.dump(results, f, indent=4, default=str)
    
    logger.info("💾 Resultados exportados para backend/audit_27feb_results.json")
    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(run_audit_27feb())
