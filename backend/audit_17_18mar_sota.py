"""
Auditoria SOTA Alta Performance — 17/03 e 18/03/2026
======================================================
Objetivo:
- Analisar potencial de ganho em operações COMPRADAS e VENDIDAS
- Quantificar perdas reais e oportunidades desperdiçadas
- Identificar pontos de melhoria absoluta sem regredir ajustes lucrativos
- Comparar assertividade por direção e por dia
- NÃO altera parâmetros locked (GEMINI.md + ANTIVIBE-CODING)
"""
import asyncio
import logging
import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, date

import MetaTrader5 as mt5

sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Auditoria17_18Mar")

# ─────────────────────────────────────────────────────────────────
# Constante de multiplicador WIN$ (R$/ponto por contrato)
# ─────────────────────────────────────────────────────────────────
WIN_MULT = 0.20  # WIN$ = R$ 0,20 por ponto por contrato


def _build_metrics(trades: list, label: str) -> dict:
    """Calcula métricas completas para um conjunto de trades."""
    if not trades:
        return {
            "label": label,
            "count": 0,
            "pnl_total": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
            "avg_duration_min": 0.0,
        }

    pnls = [t.get("pnl_fin", 0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_win = sum(wins)
    total_loss = abs(sum(losses))

    durations = []
    for t in trades:
        try:
            dur = (t["exit_time"] - t["entry_time"]).total_seconds() / 60
            durations.append(dur)
        except Exception:
            pass

    return {
        "label": label,
        "count": len(trades),
        "pnl_total": round(sum(pnls), 2),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_win": round(total_win / len(wins), 2) if wins else 0.0,
        "avg_loss": round(total_loss / len(losses), 2) if losses else 0.0,
        "profit_factor": round(total_win / total_loss, 2) if total_loss > 0 else float("inf"),
        "max_win": round(max(wins, default=0.0), 2),
        "max_loss": round(min(pnls, default=0.0), 2),
        "avg_duration_min": round(sum(durations) / len(durations), 1) if durations else 0.0,
    }


def _print_metrics(m: dict):
    logger.info(f"   🏷️  Direção: {m['label']}")
    logger.info(f"   Trades      : {m['count']}")
    logger.info(f"   PnL Total   : R$ {m['pnl_total']:.2f}")
    logger.info(f"   Assertividade: {m['win_rate']:.1f}%")
    logger.info(f"   Profit Factor: {m['profit_factor']:.2f}")
    logger.info(f"   Média Acerto: R$ {m['avg_win']:.2f} | Média Perda: R$ {m['avg_loss']:.2f}")
    logger.info(f"   Maior Acerto: R$ {m['max_win']:.2f} | Maior Perda: R$ {m['max_loss']:.2f}")
    logger.info(f"   Duração Média: {m['avg_duration_min']:.1f} min")


def _analyze_missed_opportunities(bt: BacktestPro, target_date: date) -> dict:
    """Analisa oportunidades perdidas com granularidade diária."""
    date_key = str(target_date)
    shadow_day = bt.shadow_signals.get("shadow_by_date", {}).get(date_key, {})
    global_vetos = bt.shadow_signals.get("veto_reasons", {})
    total_missed = bt.shadow_signals.get("total_missed", 0)
    return {
        "total_missed_global": total_missed,
        "vetos_dia": shadow_day,
        "vetos_globais": global_vetos,
    }


def _print_missed(missed: dict, label: str):
    logger.info(f"   🔵 Oportunidades Perdidas — {label}")
    logger.info(f"   Total Perdido (acumulado): {missed['total_missed_global']}")
    if missed["vetos_dia"]:
        logger.info(f"   Motivos (granular do dia):")
        for reason, count in sorted(missed["vetos_dia"].items(), key=lambda x: -x[1]):
            logger.info(f"      - {reason}: {count}")
    else:
        logger.info("   ↳ Nenhum veto registrado para o dia específico.")


def _suggest_improvements(metrics_buy: dict, metrics_sell: dict, missed: dict) -> list:
    """
    Gera sugestões baseadas em evidências.
    Regra: NUNCA sugere reduzir parâmetros que já funcionam.
    Apenas identifica pontos de MELHORIA ABSOLUTA.
    """
    suggestions = []

    # Sugestão 1: Assimetria Buy vs Sell
    if metrics_buy["count"] > 0 and metrics_sell["count"] > 0:
        if metrics_buy["win_rate"] > metrics_sell["win_rate"] + 15:
            suggestions.append(
                f"⚠️ COMPRAS mais assertivas ({metrics_buy['win_rate']:.1f}%) que VENDAS "
                f"({metrics_sell['win_rate']:.1f}%). Considere elevar confidence_sell_threshold "
                f"ou reduzir agressividade de vendas."
            )
        elif metrics_sell["win_rate"] > metrics_buy["win_rate"] + 15:
            suggestions.append(
                f"⚠️ VENDAS mais assertivas ({metrics_sell['win_rate']:.1f}%) que COMPRAS "
                f"({metrics_buy['win_rate']:.1f}%). Considere elevar confidence_buy_threshold."
            )

    # Sugestão 2: Profit Factor abaixo de 1.5
    for m in [metrics_buy, metrics_sell]:
        if m["count"] >= 3 and m["profit_factor"] < 1.5:
            suggestions.append(
                f"⚠️ Profit Factor {m['label']} ({m['profit_factor']:.2f}) abaixo de 1.5. "
                f"Revisar relação SL/TP ou ajustar trailing para proteger ganhos."
            )

    # Sugestão 3: Muitos vetos por Flux/OBI
    vetos = missed.get("vetos_dia", {})
    flux_vetos = sum(v for k, v in vetos.items() if k and ("FLUX" in k.upper() or "OBI" in k.upper()))
    if flux_vetos > 10:
        suggestions.append(
            f"⚠️ {flux_vetos} vetos por Flux/OBI no dia. Avaliar se flux_imbalance_threshold "
            f"(atual 1.5) está excessivamente restritivo para a volatilidade do dia."
        )

    # Sugestão 4: Muitos vetos por cooldown
    cool_vetos = sum(v for k, v in vetos.items() if k and "COOLDOWN" in k.upper())
    if cool_vetos > 8:
        suggestions.append(
            f"⚠️ {cool_vetos} vetos por Cooldown. Avaliar janela de cooldown se mercado "
            f"apresentar alta velocidade de reversão em dias como esse."
        )

    # Sugestão 5: Pouco volume de operações
    total_ops = metrics_buy["count"] + metrics_sell["count"]
    if total_ops < 3 and missed.get("total_missed_global", 0) > 20:
        suggestions.append(
            f"⚠️ Apenas {total_ops} trade(s) executados mas {missed['total_missed_global']} "
            f"oportunidades vetadas. Revisar filtros de entrada para o perfil desse dia."
        )

    if not suggestions:
        suggestions.append("✅ Nenhuma melhoria crítica identificada — parâmetros dentro do esperado.")

    return suggestions


async def _run_single_day_audit(
    symbol: str,
    warmup_from: datetime,
    target_date: date,
    target_to: datetime,
    params_path: str,
    initial_balance: float,
) -> dict:
    """Executa auditoria completa para um único dia de pregão."""
    day_label = target_date.strftime("%d/%m/%Y")
    logger.info(f"\n{'═'*65}")
    logger.info(f"🔎 AUDITANDO DIA: {day_label} | Warmup desde: {warmup_from.strftime('%d/%m/%Y')}")
    logger.info(f"{'═'*65}")

    timeframe = mt5.TIMEFRAME_M1
    rates = mt5.copy_rates_range(symbol, timeframe, warmup_from, target_to)

    if rates is None or len(rates) == 0:
        logger.error(f"❌ Sem dados MT5 para {day_label}. Verifique o Market Watch.")
        return {}

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)

    # Microestrutura mínima (compatível com audit_16mar)
    df["cvd_normal"] = (df["close"] - df["open"]) / (
        df["high"] - df["low"]
    ).replace(0, 1)
    df["ofi_normal"] = df["tick_volume"] * df["cvd_normal"]
    df["trap_index"] = 0.0

    total_candles = len(df)
    alvo_candles = df[df.index.date == target_date]
    logger.info(
        f"✅ {total_candles} candles carregados | {len(alvo_candles)} candles do dia {day_label}"
    )

    # ── BacktestPro Setup ──────────────────────────────────────────
    bt = BacktestPro(
        symbol=symbol,
        initial_balance=initial_balance,
        base_lot=1,
    )
    bt.data = df

    async def _dummy_load():
        return bt.data

    bt.load_data = _dummy_load

    # Carrega Golden Params (v24_locked_params.json)
    sota_params = {}
    if os.path.exists(params_path):
        with open(params_path, "r") as f:
            config = json.load(f)
        sota_params = config.get("strategy_params", config)
        logger.info("🎯 Golden Params v24.5 SNIPER carregados.")
    else:
        logger.warning("⚠️ v24_locked_params.json não encontrado — usando defaults.")

    # Aplica parâmetros sem quebrar lock
    bt.opt_params.update(sota_params)
    bt.opt_params["base_lot"] = 1          # Capital R$ 500 — lote fixo
    bt.opt_params["dynamic_lot"] = False
    bt.opt_params["enable_news_filter"] = False  # Histórico puro

    logger.info("🚀 Executando motor HFT SOTA v24.5...")
    await bt.run()

    # ── Filtrar trades do dia alvo ─────────────────────────────────
    all_trades = bt.trades
    day_trades = [t for t in all_trades if t["entry_time"].date() == target_date]

    buys = [t for t in day_trades if t.get("side") == "buy"]
    sells = [t for t in day_trades if t.get("side") == "sell"]

    metrics_all  = _build_metrics(day_trades, "TOTAL")
    metrics_buy  = _build_metrics(buys, "COMPRA")
    metrics_sell = _build_metrics(sells, "VENDA")
    missed       = _analyze_missed_opportunities(bt, target_date)
    suggestions  = _suggest_improvements(metrics_buy, metrics_sell, missed)

    # ── Impressão do relatório ─────────────────────────────────────
    logger.info(f"\n{'─'*65}")
    logger.info(f"📋 RELATÓRIO — {day_label}")
    logger.info(f"{'─'*65}")
    logger.info(f"💰 PnL Total   : R$ {metrics_all['pnl_total']:.2f}")
    logger.info(f"📊 Assertividade Geral: {metrics_all['win_rate']:.1f}%")
    logger.info(f"📉 Max Drawdown: R$ {bt.max_drawdown:.2f}")
    logger.info("")

    logger.info("📈 ANÁLISE POR DIREÇÃO:")
    _print_metrics(metrics_buy)
    logger.info("")
    _print_metrics(metrics_sell)
    logger.info("")

    _print_missed(missed, day_label)
    logger.info("")

    logger.info("💡 SUGESTÕES DE MELHORIA:")
    for s in suggestions:
        logger.info(f"   {s}")

    logger.info(f"{'─'*65}")

    return {
        "date": str(target_date),
        "pnl": metrics_all["pnl_total"],
        "win_rate": metrics_all["win_rate"],
        "trades_count": metrics_all["count"],
        "max_drawdown": round(bt.max_drawdown, 2),
        "metrics_all": metrics_all,
        "metrics_buy": metrics_buy,
        "metrics_sell": metrics_sell,
        "missed_opportunities": missed,
        "suggestions": suggestions,
        "shadow": bt.shadow_signals,
        "trades": [
            {k: str(v) if isinstance(v, datetime) else v for k, v in t.items()}
            for t in day_trades
        ],
    }


async def run_audit_17_18_mar():
    logger.info("╔══════════════════════════════════════════════════════════════╗")
    logger.info("║   🛡️ SOTA v24.5 SNIPER — AUDITORIA 17/03 e 18/03/2026       ║")
    logger.info("║   Análise: COMPRAS | VENDAS | PERDAS | OPORTUNIDADES         ║")
    logger.info("╚══════════════════════════════════════════════════════════════╝")

    # Inicializa MT5
    if not mt5.initialize():
        logger.error("❌ Falha crítica: MetaTrader5 não inicializado.")
        return

    symbol = "WIN$"
    params_path = "backend/v24_locked_params.json"
    initial_balance = 500.0

    results = {}

    # ── Dia 17/03 ─────────────────────────────────────────────────
    # Warmup: 13/03 (sexta) → garante indicadores aquecidos
    res_17 = await _run_single_day_audit(
        symbol=symbol,
        warmup_from=datetime(2026, 3, 13, 9, 0),
        target_date=date(2026, 3, 17),
        target_to=datetime(2026, 3, 17, 18, 0),
        params_path=params_path,
        initial_balance=initial_balance,
    )
    results["2026-03-17"] = res_17

    # ── Dia 18/03 ─────────────────────────────────────────────────
    # Warmup: 16/03 (segunda) → garante continuidade sem gap de weekend
    res_18 = await _run_single_day_audit(
        symbol=symbol,
        warmup_from=datetime(2026, 3, 16, 9, 0),
        target_date=date(2026, 3, 18),
        target_to=datetime(2026, 3, 18, 18, 0),
        params_path=params_path,
        initial_balance=initial_balance,
    )
    results["2026-03-18"] = res_18

    mt5.shutdown()

    # ── RESUMO COMPARATIVO ────────────────────────────────────────
    logger.info("\n")
    logger.info("╔══════════════════════════════════════════════════════════════╗")
    logger.info("║                  📊 RESUMO COMPARATIVO 2 DIAS               ║")
    logger.info("╚══════════════════════════════════════════════════════════════╝")

    for day_key, res in results.items():
        if not res:
            continue
        logger.info(f"  📅 {day_key}")
        logger.info(f"     PnL      : R$ {res.get('pnl', 0):.2f}")
        logger.info(f"     Trades   : {res.get('trades_count', 0)}")
        logger.info(f"     Assert.  : {res.get('win_rate', 0):.1f}%")
        logger.info(f"     Drawdown : R$ {res.get('max_drawdown', 0):.2f}")
        logger.info("")

    pnl_total_2d = (results.get("2026-03-17", {}).get("pnl", 0) +
                    results.get("2026-03-18", {}).get("pnl", 0))
    logger.info(f"  💰 PnL Acumulado 2 Dias: R$ {pnl_total_2d:.2f}")
    logger.info(f"     (17/03: R$ {results.get('2026-03-17', {}).get('pnl', 0):.2f} | "
                f"18/03: R$ {results.get('2026-03-18', {}).get('pnl', 0):.2f})")

    # Melhoria Absoluta Consolidada
    all_suggestions = []
    for res in results.values():
        all_suggestions.extend(res.get("suggestions", []))
    unique_suggestions = list(dict.fromkeys(all_suggestions))  # dedup preservando ordem

    logger.info("\n  💡 PONTOS DE MELHORIA ABSOLUTA (consolidado 2 dias):")
    for s in unique_suggestions:
        logger.info(f"     {s}")

    logger.info("═" * 65)

    # Exporta JSON
    output_path = "backend/audit_17_18mar_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, default=str, ensure_ascii=False)
    logger.info(f"\n💾 Resultados exportados para: {output_path}")


if __name__ == "__main__":
    asyncio.run(run_audit_17_18_mar())
