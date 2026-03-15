import asyncio
import pandas as pd
import os
import json
import logging
import sys
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# Adiciona diretório raiz ao path
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore
from backend.mt5_bridge import MT5Bridge

# Protocolo de Idioma: Brasileiro
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MultiDayValidation")

dates = [
    "2026-02-19",
    "2026-02-20",
    "2026-02-23",
    "2026-02-24",
    "2026-02-25",
    "2026-02-26",
    "2026-02-27",
    "2026-03-02",
    "2026-03-03",
    "2026-03-04",
    "2026-03-05",
    "2026-03-06",
    "2026-03-09",
    "2026-03-10",
    "2026-03-11",
    "2026-03-12",
    "2026-03-13",
]


async def run_validation():
    logger.info(
        "🤖 [SOTA-MULTIDAY] Iniciando validação abrangente (Estratégia: Full History Cache + Debug)..."
    )

    if not mt5.initialize():
        logger.error("❌ Falha crítica: MT5 não inicializado.")
        return

    bridge = MT5Bridge()
    symbol = "WIN$"

    # 1. DOWNLOAD MASSIVO DE DADOS (Aumentado para garantir warm-up)
    n_total_candles = 90000
    logger.info(f"📥 Coletando massa de dados ({n_total_candles} velas)...")

    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, n_total_candles)
    if rates is None or len(rates) == 0:
        logger.error("❌ Falha ao coletar histórico do MT5.")
        mt5.shutdown()
        return

    df_all = pd.DataFrame(rates)
    df_all["time"] = pd.to_datetime(df_all["time"], unit="s")

    # Alinhamento GMT-3 (Server = Brasília - 5h conforme detectado anteriormente)
    df_all["time_br"] = df_all["time"] + timedelta(hours=5)

    logger.info(
        f"✅ Histórico carregado. Período BR: {df_all['time_br'].min()} até {df_all['time_br'].max()}"
    )

    # 2. Carregar Parâmetros
    try:
        with open("backend/v22_locked_params.json", "r") as f:
            params = json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar parâmetros: {e}")
        return

    results = []
    initial_cap = params.get("account_config", {}).get("initial_balance", 500.0)
    cumulative_pnl = 0.0
    ai = AICore()

    # 3. LOOP DE PROCESSAMENTO
    for date_str in dates:
        logger.info(f"\n>>>> PROCESSANDO: {date_str} <<<<")

        # Filtro de dia com 4h de aquecimento (05:00 BR) para indicadores pesados
        dt_day = datetime.strptime(date_str, "%Y-%m-%d")
        start_filter = dt_day + timedelta(hours=5)
        end_filter = dt_day + timedelta(hours=18)

        df_day = df_all[
            (df_all["time_br"] >= start_filter) & (df_all["time_br"] <= end_filter)
        ].copy()

        if df_day.empty or len(df_day) < 200:
            logger.warning(
                f"⚠️ Dados insuficientes para {date_str} ({len(df_day)} velas)."
            )
            continue

        df_day["time"] = df_day["time_br"]
        temp_csv = f"temp_multi_{date_str}.csv"
        df_day[
            [
                "time",
                "open",
                "high",
                "low",
                "close",
                "tick_volume",
                "spread",
                "real_volume",
            ]
        ].to_csv(temp_csv, index=False)

        bt = BacktestPro(
            symbol=symbol, capital=initial_cap, data_file=temp_csv, n_candles=5000
        )
        bt.ai = ai
        bt.use_ai_core = True
        bt.opt_params.update(params)

        # Desativa filtro de notícias para backtest histórico (pois não temos histórico de news no BacktestPro)
        bt.opt_params["enable_news_filter"] = False

        await bt.run()

        day_pnl = sum(t.get("pnl_fin", 0) for t in bt.trades)
        win_rate = (
            (len([t for t in bt.trades if t["pnl_fin"] > 0]) / len(bt.trades) * 100)
            if bt.trades
            else 0
        )

        # Log de Justificativa de Veto
        if not bt.trades:
            logger.info(
                f"🚫 Motivos de veto para {date_str}: {bt.shadow_signals.get('veto_reasons', {})}"
            )
            logger.info(
                f"🔍 AI Filtered: {bt.shadow_signals.get('filtered_by_ai', 0)} | Flux: {bt.shadow_signals.get('filtered_by_flux', 0)}"
            )

        results.append(
            {
                "data": date_str,
                "trades": len(bt.trades),
                "pnl": day_pnl,
                "win_rate": win_rate,
            }
        )

        cumulative_pnl += day_pnl
        logger.info(
            f"💰 {date_str} | PnL R$ {day_pnl:.2f} | WR: {win_rate:.1f}% | Trades: {len(bt.trades)}"
        )

        if os.path.exists(temp_csv):
            os.remove(temp_csv)

    # 4. CONSOLIDAÇÃO FINAL
    logger.info("\n" + "=" * 60)
    logger.info("📊 RELATÓRIO FINAL CONSOLIDADO (SOTA v25)")
    logger.info("============================================================")
    for r in results:
        indicator = "✅" if r["pnl"] > 0 else ("💀" if r["pnl"] < 0 else "⚪")
        logger.info(
            f"{indicator} {r['data']} | Trades: {r['trades']} | PnL: R$ {r['pnl']:8.2f} | WR: {r['win_rate']:5.1f}%"
        )

    logger.info("------------------------------------------------------------")
    logger.info(f"💰 PnL TOTAL ACUMULADO: R$ {cumulative_pnl:.2f}")
    logger.info("============================================================")

    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(run_validation())
