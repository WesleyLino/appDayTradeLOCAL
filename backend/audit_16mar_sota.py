import asyncio
import logging
import pandas as pd
import os
import sys
import json
from datetime import datetime

import MetaTrader5 as mt5

# Adiciona diretório raiz ao path para importações locais
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro

# [REGRA-PTBR] Monitoramento de Auditoria SOTA — 16/03/2026
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Auditoria16Mar")


async def run_audit_16mar():
    logger.info("🛡️ [SOTA-v24.5] Iniciando Auditoria Focada de 1 Dia: 16/03/2026")
    logger.info("💰 Capital Inicial: R$ 500.00 | Melhorias A-H + shadow_by_date ativos")

    # 1. Inicializar MetaTrader 5
    if not mt5.initialize():
        logger.error("❌ Falha crítica ao inicializar o terminal MT5.")
        return

    symbol = "WIN$"
    timeframe = mt5.TIMEFRAME_M1

    # Warmup: 13/03 (sexta-feira) → evita gap de fim de semana
    # Pregão alvo: 16/03 (segunda-feira)
    date_from = datetime(2026, 3, 13, 9, 0)
    date_to   = datetime(2026, 3, 16, 18, 0)

    logger.info(
        f"📊 Coletando histórico MT5: {date_from.strftime('%d/%m')} (warmup) "
        f"→ {date_to.strftime('%d/%m')} (pregão alvo)..."
    )
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)

    if rates is None or len(rates) == 0:
        logger.error(
            "❌ Falha ao coletar dados do MT5. "
            "Verifique se o ativo WIN$ está no Market Watch com histórico disponível."
        )
        mt5.shutdown()
        return

    df_rates = pd.DataFrame(rates)
    df_rates["time"] = pd.to_datetime(df_rates["time"], unit="s")
    df_rates.set_index("time", inplace=True)

    # Injeção de Microestrutura simplificada — padrão do audit_27feb
    df_rates["cvd_normal"] = (df_rates["close"] - df_rates["open"]) / (
        df_rates["high"] - df_rates["low"]
    ).replace(0, 1)
    df_rates["ofi_normal"] = df_rates["tick_volume"] * df_rates["cvd_normal"]
    df_rates["trap_index"] = 0.0

    logger.info(f"✅ {len(df_rates)} candles processados para simulação.")

    candles_alvo = df_rates[df_rates.index.date == datetime(2026, 3, 16).date()]
    logger.info(f"📌 Candles do dia alvo (16/03): {len(candles_alvo)}")

    # 2. Configurar BacktestPro com capital R$ 500
    bt = BacktestPro(
        symbol=symbol,
        initial_balance=500.0,
        base_lot=1,
    )
    bt.data = df_rates

    async def dummy_load():
        return bt.data

    bt.load_data = dummy_load

    # Carrega parâmetros SOTA v24.5
    params_path = "backend/v24_locked_params.json"
    sota_params = {}
    if os.path.exists(params_path):
        with open(params_path, "r") as f:
            config = json.load(f)
        sota_params = config.get("strategy_params", config)
        logger.info("🎯 Parâmetros SOTA v24.5 carregados.")
    else:
        logger.warning(
            "⚠️ v24_locked_params.json não encontrado — usando defaults do BacktestPro."
        )

    # Aplica travas operacionais para capital R$ 500
    bt.opt_params.update(sota_params)
    bt.opt_params["base_lot"] = 1          # Forçado para capital baixo
    bt.opt_params["dynamic_lot"] = False   # Lote fixo 1 contrato
    bt.opt_params["enable_news_filter"] = False  # Histórico puro (sem notícias em tempo real)

    # 3. Execução da Simulação
    logger.info("🚀 Executando motor HFT sobre os dados de 13-16/03/2026...")
    await bt.run()

    # 4. Filtrar somente trades do dia alvo (16/03)
    target_date = datetime(2026, 3, 16).date()
    trades_day = [t for t in bt.trades if t["entry_time"].date() == target_date]

    buys  = [t for t in trades_day if t["side"] == "buy"]
    sells = [t for t in trades_day if t["side"] == "sell"]

    total_pnl = sum(t.get("pnl_fin", 0) for t in trades_day)
    win_rate = (
        len([t for t in trades_day if t.get("pnl_fin", 0) > 0]) / len(trades_day) * 100
    ) if trades_day else 0.0

    wins  = [t for t in trades_day if t.get("pnl_fin", 0) > 0]
    loses = [t for t in trades_day if t.get("pnl_fin", 0) <= 0]

    logger.info("\n" + "═" * 60)
    logger.info("📋 RELATÓRIO DE AUDITORIA — 16/03/2026")
    logger.info(f"💰 Resultado Financeiro: R$ {total_pnl:.2f}")
    logger.info(f"📊 Trades: {len(trades_day)} | Assertividade: {win_rate:.1f}%")
    logger.info(f"📈 Compras: {len(buys)} | 📉 Vendas: {len(sells)}")
    logger.info(f"✅ Acertos: {len(wins)} | ❌ Erros: {len(loses)}")
    logger.info(f"📉 Max Drawdown Simulado: R$ {bt.max_drawdown:.2f}")
    logger.info(f"🔎 Oportunidades Perdidas (Shadow): {bt.shadow_signals['total_missed']}")

    # Vetos globais
    if bt.shadow_signals.get("veto_reasons"):
        logger.info("   ↳ Vetos Globais (warmup + pregão):")
        for reason, count in sorted(
            bt.shadow_signals["veto_reasons"].items(), key=lambda x: -x[1]
        ):
            logger.info(f"      - {reason}: {count}")

    # Vetos apenas do dia alvo (shadow_by_date)
    shadow_16mar = bt.shadow_signals.get("shadow_by_date", {}).get("2026-03-16", {})
    if shadow_16mar:
        logger.info("   ↳ Vetos SOMENTE 16/03 (granular):")
        for reason, count in sorted(shadow_16mar.items(), key=lambda x: -x[1]):
            logger.info(f"      - {reason}: {count}")
    else:
        logger.info("   ↳ Nenhum veto no dia 16/03 registrado.")

    logger.info("═" * 60)

    # 5. Exportar resultados
    results = {
        "date": "2026-03-16",
        "pnl": total_pnl,
        "win_rate": round(win_rate, 2),
        "trades_count": len(trades_day),
        "trades_buys": len(buys),
        "trades_sells": len(sells),
        "trades": trades_day,
        "shadow": bt.shadow_signals,
        "shadow_16mar_only": shadow_16mar,
        "drawdown": bt.max_drawdown,
    }

    output_path = "backend/audit_16mar_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, default=str, ensure_ascii=False)

    logger.info(f"💾 Resultados exportados para {output_path}")
    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(run_audit_16mar())
