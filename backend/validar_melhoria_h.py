"""
[MELHORIA-H VALIDAÇÃO] Backtest multi-dia com Bypass Condicional de Pânico.
Segue exatamente o mesmo padrão do audit_27feb_500brl_sota.py.
Roda os dias candidatos (risk_index > 2.5) e dias controle (sem pânico).
Exporta: backend/validacao_melhoria_h.json
"""
import asyncio
import logging
import json
import os
import sys
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import pandas as pd

sys.path.append(os.getcwd())
from backend.backtest_pro import BacktestPro  # noqa: E402

logging.basicConfig(
    level=logging.WARNING,    # Suprime logs durante multi-dia para saída limpa
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ValidacaoMelhoriaH")
logger.setLevel(logging.INFO)

# ── Parâmetros ─────────────────────────────────────────────────────────────────
SYMBOL  = "WIN$"
CAPITAL = 500.0

with open("backend/candidatos_melhoria_h.json", encoding="utf-8") as f:
    meta = json.load(f)

CANDIDATOS = meta["candidatos_melhoria_h"][:6]
CONTROLES  = meta["dias_controle"][:3]
TODOS_DIAS = [(d, "CANDIDATO") for d in CANDIDATOS] + [(d, "CONTROLE") for d in CONTROLES]


async def rodar_dia(dia_str: str, tipo: str) -> dict:
    """Executa o backtest completo de 1 dia seguindo o padrão do audit_27feb."""
    d = datetime.strptime(dia_str, "%Y-%m-%d")

    # Coleta: dia anterior (warmup) + dia alvo
    date_from = d - timedelta(days=1)
    # Ajusta warmup para não cair em fim de semana
    while date_from.weekday() >= 5:
        date_from -= timedelta(days=1)
    date_from = datetime(date_from.year, date_from.month, date_from.day, 9, 0)
    date_to   = datetime(d.year, d.month, d.day, 18, 0)

    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, date_from, date_to)
    if rates is None or len(rates) < 30:
        return {"data": dia_str, "tipo": tipo, "erro": "Sem dados MT5"}

    df_rates = pd.DataFrame(rates)
    df_rates["time"] = pd.to_datetime(df_rates["time"], unit="s")
    df_rates.set_index("time", inplace=True)

    # Microestrutura sintética (igual ao audit_27feb)
    df_rates["cvd_normal"] = (df_rates["close"] - df_rates["open"]) / (
        df_rates["high"] - df_rates["low"]
    ).replace(0, 1)
    df_rates["ofi_normal"] = df_rates["tick_volume"] * df_rates["cvd_normal"]
    df_rates["trap_index"] = 0.0

    # Instanciar BacktestPro
    bt = BacktestPro(symbol=SYMBOL, initial_balance=CAPITAL, base_lot=1)
    bt.data = df_rates

    async def dummy_load():
        return bt.data
    bt.load_data = dummy_load

    # Carregar parâmetros SOTA v24
    params_path = "backend/v24_locked_params.json"
    if os.path.exists(params_path):
        with open(params_path) as pf:
            cfg = json.load(pf)
        bt.opt_params.update(cfg.get("strategy_params", cfg))

    bt.opt_params["base_lot"]          = 1
    bt.opt_params["dynamic_lot"]       = False
    bt.opt_params["enable_news_filter"] = False

    await bt.run()

    # Filtrar apenas o dia alvo (excluir warmup)
    target_date = d.date()
    trades_day  = [t for t in bt.trades if t["entry_time"].date() == target_date]

    pnl_total   = sum(t.get("pnl_fin", 0) for t in trades_day)
    wins        = sum(1 for t in trades_day if t.get("pnl_fin", 0) > 0)
    win_rate    = (wins / len(trades_day) * 100) if trades_day else 0.0
    shadow      = bt.shadow_signals or {}
    veto_r      = shadow.get("veto_reasons", {})

    return {
        "data":            dia_str,
        "tipo":            tipo,
        "trades":          len(trades_day),
        "pnl_total":       round(float(pnl_total), 2),
        "win_rate_pct":    round(win_rate, 1),
        "panico_veto":     int(veto_r.get("PANICO_MERCADO_SEM_BYPASS", 0)),
        "panico_sem_h1":   int(veto_r.get("PANICO_SEM_H1", 0)),
        "bypass_ativado":  int(veto_r.get("PANICO_BYPASS_ATIVADO", 0)),  # novo contador
        "total_missed":    int(shadow.get("total_missed", 0)),
        "drawdown":        round(float(getattr(bt, "max_drawdown", 0.0)), 4),
    }


async def main():
    logger.info("=" * 75)
    logger.info("  VALIDAÇÃO MELHORIA-H — BYPASS CONDICIONAL DE PÂNICO")
    logger.info(f"  Dias: {len(CANDIDATOS)} candidatos + {len(CONTROLES)} controles")
    logger.info(f"  Capital: R$ {CAPITAL:.0f} | Símbolo: {SYMBOL}")
    logger.info("=" * 75)

    if not mt5.initialize():
        logger.error("❌ Falha ao inicializar MT5.")
        return

    resultados = []

    for dia_str, tipo in TODOS_DIAS:
        r = await rodar_dia(dia_str, tipo)
        resultados.append(r)

        if "erro" in r:
            print(f"  ⚠️  [{tipo[:4]}] {dia_str}  ERRO: {r['erro']}")
        else:
            status = "✅" if r["pnl_total"] > 0 else ("⚪" if r["pnl_total"] == 0 else "❌")
            print(
                f"  {status} [{tipo[:4]}] {dia_str}  "
                f"PnL=R${r['pnl_total']:>7.2f}  Trades={r['trades']:2d}  "
                f"WR={r['win_rate_pct']:4.0f}%  "
                f"Veto={r.get('panico_veto',0):3d}  "
                f"SemH1={r.get('panico_sem_h1',0):2d}  "
                f"Bypass={r.get('bypass_ativado',0):2d}"
            )

    mt5.shutdown()

    # ── Sumário ────────────────────────────────────────────────────────────────
    print()
    print("=" * 75)
    print("  SUMÁRIO")
    print("=" * 75)

    dias_ok    = [r for r in resultados if "erro" not in r]
    cands_ok   = [r for r in dias_ok if r["tipo"] == "CANDIDATO"]
    ctrl_ok    = [r for r in dias_ok if r["tipo"] == "CONTROLE"]

    def resumo(lista, label):
        if not lista:
            return
        pnl     = sum(r["pnl_total"] for r in lista)
        wr      = sum(r["win_rate_pct"] for r in lista) / len(lista)
        vetos   = sum(r.get("panico_veto", 0) for r in lista)
        sem_h1  = sum(r.get("panico_sem_h1", 0) for r in lista)
        bypass  = sum(r.get("bypass_ativado", 0) for r in lista)
        missed  = sum(r.get("total_missed", 0) for r in lista)
        print(f"  {label} ({len(lista)} dias válidos):")
        print(f"    PnL acumulado    : R$ {pnl:.2f}")
        print(f"    Win Rate médio   : {wr:.1f}%")
        print(f"    Pânico vetado    : {vetos}")
        print(f"    Pânico sem H1    : {sem_h1}")
        print(f"    Bypass ativado   : {bypass}")
        print(f"    Total missed     : {missed}")
        print()

    resumo(cands_ok, "CANDIDATOS (com pânico esperado)")
    resumo(ctrl_ok,  "CONTROLES  (sem pânico)")

    print("  INTERPRETAÇÃO:")
    if cands_ok:
        bypass_total = sum(r.get("bypass_ativado", 0) for r in cands_ok)
        if bypass_total > 0:
            print(f"  ✅ Melhoria H ATIVADA {bypass_total}× — bypass funcionou em dias de pânico com momentum.")
        else:
            print("  ℹ️  Melhoria H não ativou — dias candidatos não tiveram momentum_bypass ativo em simultâneo.")
            print("     Isso é esperado se a IA não detectou tendência forte nesses momentos de pânico.")
    print("=" * 75)

    # ── Export ─────────────────────────────────────────────────────────────────
    output = {
        "validacao_melhoria_h": True,
        "data_execucao":        str(datetime.now()),
        "capital":              CAPITAL,
        "resultados":           resultados,
        "sumario": {
            "candidatos_pnl":     round(sum(r.get("pnl_total", 0) for r in cands_ok), 2),
            "candidatos_wr":      round(sum(r.get("win_rate_pct", 0) for r in cands_ok) / max(len(cands_ok), 1), 1),
            "bypass_total":       sum(r.get("bypass_ativado", 0) for r in cands_ok),
            "panico_veto_total":  sum(r.get("panico_veto", 0) for r in cands_ok),
            "controles_pnl":      round(sum(r.get("pnl_total", 0) for r in ctrl_ok), 2),
        }
    }
    with open("backend/validacao_melhoria_h.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print("\n  ✅ Exportado: backend/validacao_melhoria_h.json")


if __name__ == "__main__":
    asyncio.run(main())
