# --- encoding: utf-8 ---
"""
Multi-Day Trace - Mini Indice WIN$ (Feb/Mar 2026)
Capital: R$ 3.000,00 | Params: Golden V22 | Candles: M1
MODO LEITURA: Nenhuma logica ou parametro alterado.
"""

import asyncio
import pandas as pd
import numpy as np
import json
import os
import sys


class NumpyEncoder(json.JSONEncoder):
    """Converte tipos numpy para tipos Python nativos antes de serializar."""

    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro

# =====================================================================
# CONFIGURACAO
# =====================================================================
CAPITAL = 3000.0
SYMBOL = "WIN$"
N_CANDLES = 6000  # Suficiente para cobrir ~30 dias de M1
PONTO_VALOR = 0.20  # R$/ponto por lote (Mini Indice)
BASE_LOTE = 1

DIAS = [
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
]

SEP = "=" * 70


def pnl_brl(pontos: float, lotes: int = BASE_LOTE) -> float:
    return round(pontos * lotes * PONTO_VALOR, 2)


def traceiar_dia(df_all: pd.DataFrame, data_str: str, p: dict) -> dict | None:
    """
    Trace completo de sinais com os mesmos parametros do BacktestPro.
    Usa mesma logica de indicadores (RSI-EWM, BB, VWAP, ATR, ADX, Vol).
    Retorna resumo por BUY/SELL e lista de sinais.
    """
    df = df_all[df_all.index.strftime("%Y-%m-%d") == data_str].copy()
    if df.empty:
        return None

    # ---- Indicadores (replicando backtest_pro.run() L296-349) ----
    rsi_p = int(p.get("rsi_period", 9))
    bb_d = float(p.get("bb_dev", 2.0))
    vm = float(p.get("vol_spike_mult", 1.0))
    sl = float(p.get("sl_dist", 150.0))
    tp = float(p.get("tp_dist", 400.0))
    rsi_buy = int(p.get("rsi_buy_level", 32))
    rsi_sell = int(p.get("rsi_sell_level", 68))
    vol_thr = float(p.get("volatility_pause_threshold", 250.0))
    atr_min = float(p.get("min_atr_threshold", 50.0))

    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    df["rsi"] = df["rsi"].fillna(50.0)

    df["sma_20"] = df["close"].rolling(20).mean()
    df["std_20"] = df["close"].rolling(20).std()
    df["upper_bb"] = df["sma_20"] + bb_d * df["std_20"]
    df["lower_bb"] = df["sma_20"] - bb_d * df["std_20"]

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    df["vol_sma"] = df["tick_volume"].rolling(20).mean().bfill()

    # VWAP Intraday
    tp_v = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["tick_volume"]
    df["vwap"] = (tp_v * vol).cumsum() / vol.cumsum()

    # EMA30/90 para bias de tendencia
    df["ema30"] = df["close"].ewm(span=30, adjust=False).mean()
    df["ema90"] = df["close"].ewm(span=90, adjust=False).mean()

    # ---- Filtro de Volatilidade na Abertura (pausa ATR) ----
    df_abert = df.between_time("09:00", "09:10")
    hl_abertura = (
        float((df_abert["high"] - df_abert["low"]).mean())
        if not df_abert.empty
        else 0.0
    )
    dia_pausado = hl_abertura >= vol_thr
    atr_medio = float(df["atr"].mean())

    # ---- Trace de Sinais ----
    sinais = []
    for i in range(max(20, rsi_p * 2), len(df)):
        row = df.iloc[i]
        hora = row.name.strftime("%H:%M")
        if hora < "09:15" or hora > "17:15":
            continue

        vol_ok = row["tick_volume"] >= (row["vol_sma"] * vm)
        atr_ok = row["atr"] >= atr_min
        cond_buy = (
            row["rsi"] <= rsi_buy
            and row["close"] <= row["lower_bb"]
            and vol_ok
            and atr_ok
        )
        cond_sell = (
            row["rsi"] >= rsi_sell
            and row["close"] >= row["upper_bb"]
            and vol_ok
            and atr_ok
        )

        if not (cond_buy or cond_sell):
            continue

        lado = "buy" if cond_buy else "sell"
        entry = row["close"]
        sl_val = entry - sl if lado == "buy" else entry + sl
        tp_val = entry + tp if lado == "buy" else entry - tp

        # Contexto de mercado no sinal
        bias_h1 = "alta" if row["ema30"] > row["ema90"] else "baixa"
        a_favor = (lado == "buy" and bias_h1 == "alta") or (
            lado == "sell" and bias_h1 == "baixa"
        )
        acima_vwap = row["close"] > row["vwap"]

        # Forward look ate 120 candles (~2h)
        resultado = "EXPIRADO"
        pnl_pts = 0.0
        saiu_hora = hora
        for j in range(i + 1, min(i + 120, len(df))):
            f = df.iloc[j]
            if lado == "buy":
                if f["low"] <= sl_val:
                    resultado = "STOP"
                    pnl_pts = -sl
                    saiu_hora = f.name.strftime("%H:%M")
                    break
                if f["high"] >= tp_val:
                    resultado = "TAKE"
                    pnl_pts = tp
                    saiu_hora = f.name.strftime("%H:%M")
                    break
            else:
                if f["high"] >= sl_val:
                    resultado = "STOP"
                    pnl_pts = -sl
                    saiu_hora = f.name.strftime("%H:%M")
                    break
                if f["low"] <= tp_val:
                    resultado = "TAKE"
                    pnl_pts = tp
                    saiu_hora = f.name.strftime("%H:%M")
                    break

        pnl_financeiro = pnl_brl(abs(pnl_pts)) * (
            1 if pnl_pts > 0 else (-1 if pnl_pts < 0 else 0)
        )

        sinais.append(
            {
                "hora": hora,
                "hora_saida": saiu_hora,
                "lado": lado.upper(),
                "entry": round(float(entry), 0),
                "sl": round(float(sl_val), 0),
                "tp": round(float(tp_val), 0),
                "rsi": round(float(row["rsi"]), 1),
                "resultado": resultado,
                "pnl_pts": round(float(pnl_pts), 1),
                "pnl_brl": float(pnl_financeiro),
                "bias_h1": bias_h1,
                "a_favor_bias": bool(a_favor),
                "acima_vwap": bool(acima_vwap),
                "dia_pausado": bool(dia_pausado),
            }
        )

    def resumir(lado_str: str) -> dict:
        sub = [s for s in sinais if s["lado"] == lado_str]
        takes = [s for s in sub if s["resultado"] == "TAKE"]
        stops = [s for s in sub if s["resultado"] == "STOP"]
        exps = [s for s in sub if s["resultado"] == "EXPIRADO"]
        ganho = sum(s["pnl_brl"] for s in takes)
        perda = sum(abs(s["pnl_brl"]) for s in stops)
        net = sum(s["pnl_brl"] for s in sub)
        ok = len(sub)
        assert_pct = (len(takes) / ok * 100) if ok > 0 else 0.0
        return {
            "sinais": ok,
            "takes": len(takes),
            "stops": len(stops),
            "expirados": len(exps),
            "ganho_brl": round(ganho, 2),
            "perda_brl": round(perda, 2),
            "pnl_liquido": round(net, 2),
            "assertividade": round(assert_pct, 1),
        }

    return {
        "data": data_str,
        "dia_pausado": dia_pausado,
        "hl_abertura": round(hl_abertura, 1),
        "atr_medio": round(atr_medio, 1),
        "buy": resumir("BUY"),
        "sell": resumir("SELL"),
        "pnl_dia": round(sum(s["pnl_brl"] for s in sinais), 2),
        "total_sinais": len(sinais),
        "sinais": sinais,
    }


async def main():
    print("🚀  AUDITORIA MULTI-DIA WIN$ | Capital: R$ 3.000,00")
    print(SEP)

    # Cria instancia do BacktestPro para usar load_data() e os parametros V22 ja carregados
    bt = BacktestPro(symbol=SYMBOL, n_candles=N_CANDLES)
    p = bt.opt_params  # Golden Params V22 lidos do JSON

    print(
        f"⚙️  Params: RSI={p['rsi_period']} | RSI-Buy<={p['rsi_buy_level']} / RSI-Sell>={p['rsi_sell_level']}"
    )
    print(
        f"          SL={p['sl_dist']} | TP={p['tp_dist']} | BB-Dev={p['bb_dev']} | VolMult={p['vol_spike_mult']}"
    )
    print(f"📅  Dias alvo: {len(DIAS)}")
    print(SEP)

    print("📥  Coletando historico MT5...")
    df_all = await bt.load_data()
    if df_all is None or df_all.empty:
        print("❌  Falha na coleta. Verifique a conexao com o MT5.")
        return

    datas_disp = set(df_all.index.strftime("%Y-%m-%d").unique())
    print(
        f"✅  {len(df_all)} candles | {df_all.index[0].date()} -> {df_all.index[-1].date()}"
    )
    print(SEP)

    resultados = []
    for data in DIAS:
        if data not in datas_disp:
            print(f"⚠️   {data}: Sem dados (Feriado/Fim de semana/Fora do historico)")
            continue

        r = traceiar_dia(df_all, data, p)
        if r is None:
            print(f"⚠️   {data}: Dados insuficientes para calculo.")
            continue

        resultados.append(r)
        status_flag = "🔴 PAUSADO" if r["dia_pausado"] else "🟢 ATIVO  "
        b, s = r["buy"], r["sell"]
        print(
            f"{data} {status_flag} | "
            f"BUY {b['takes']}T/{b['stops']}S={b['assertividade']:>5.1f}% "
            f"R${b['pnl_liquido']:>+7.2f} | "
            f"SELL {s['takes']}T/{s['stops']}S={s['assertividade']:>5.1f}% "
            f"R${s['pnl_liquido']:>+7.2f} | "
            f"PnL Dia: R${r['pnl_dia']:>+8.2f}"
        )

    # Salvar JSON detalhado
    out = "backend/multiday_trace_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    # ---- RESUMO CONSOLIDADO ----
    print(f"\n{SEP}")
    print("📊  RESUMO CONSOLIDADO")
    print(SEP)
    if not resultados:
        print("❌  Nenhum resultado. Verifique a conexao e o historico.")
        return

    total_buy_t = sum(r["buy"]["takes"] for r in resultados)
    total_buy_s = sum(r["buy"]["stops"] for r in resultados)
    total_sell_t = sum(r["sell"]["takes"] for r in resultados)
    total_sell_s = sum(r["sell"]["stops"] for r in resultados)
    total_pnl = sum(r["pnl_dia"] for r in resultados)
    dias_ativos = [r for r in resultados if not r["dia_pausado"]]
    dias_pausados = [r for r in resultados if r["dia_pausado"]]

    buy_total = total_buy_t + total_buy_s
    sell_total = total_sell_t + total_sell_s
    buy_assert = (total_buy_t / buy_total * 100) if buy_total > 0 else 0
    sell_assert = (total_sell_t / sell_total * 100) if sell_total > 0 else 0

    pnl_buy = sum(r["buy"]["pnl_liquido"] for r in resultados)
    pnl_sell = sum(r["sell"]["pnl_liquido"] for r in resultados)
    ganho_pot_buy = sum(r["buy"]["ganho_brl"] for r in resultados)
    perda_pot_buy = sum(r["buy"]["perda_brl"] for r in resultados)
    ganho_pot_sell = sum(r["sell"]["ganho_brl"] for r in resultados)
    perda_pot_sell = sum(r["sell"]["perda_brl"] for r in resultados)

    print(
        f"📅  Dias analisados: {len(resultados)} | Ativos: {len(dias_ativos)} | Pausados (filtro ATR): {len(dias_pausados)}"
    )
    print("")
    print(
        f"{'Lado':<8} {'Sinais':>7} {'Takes':>7} {'Stops':>7} {'Assert':>9} {'Ganho':>10} {'Perda':>10} {'PnL':>10}"
    )
    print(
        f"{'-' * 8} {'-' * 7} {'-' * 7} {'-' * 7} {'-' * 9} {'-' * 10} {'-' * 10} {'-' * 10}"
    )
    print(
        f"{'BUY':<8} {buy_total:>7} {total_buy_t:>7} {total_buy_s:>7} {buy_assert:>8.1f}% "
        f"R${ganho_pot_buy:>8.2f} R${perda_pot_buy:>8.2f} R${pnl_buy:>+8.2f}"
    )
    print(
        f"{'SELL':<8} {sell_total:>7} {total_sell_t:>7} {total_sell_s:>7} {sell_assert:>8.1f}% "
        f"R${ganho_pot_sell:>8.2f} R${perda_pot_sell:>8.2f} R${pnl_sell:>+8.2f}"
    )
    print(f"{'-' * 83}")
    print(
        f"{'TOTAL':<8} {buy_total + sell_total:>7} {total_buy_t + total_sell_t:>7} "
        f"{total_buy_s + total_sell_s:>7} "
        f"{((total_buy_t + total_sell_t) / (buy_total + sell_total) * 100) if (buy_total + sell_total) > 0 else 0:>8.1f}% "
        f"R${ganho_pot_buy + ganho_pot_sell:>8.2f} R${perda_pot_buy + perda_pot_sell:>8.2f} R${total_pnl:>+8.2f}"
    )
    print("")
    print(f"💰  PnL Total Bruto (sinais tecnicos): R$ {total_pnl:+.2f}")
    print(
        f"💡  Ganho potencial total (Takes):     R$ {ganho_pot_buy + ganho_pot_sell:.2f}"
    )
    print(
        f"⚠️   Perda potencial total (Stops):     R$ {perda_pot_buy + perda_pot_sell:.2f}"
    )
    print(f"\n✅  Resultados detalhados: {out}")

    # ---- Analise por Dias Pausados ----
    if dias_pausados:
        pnl_pausados = sum(r["pnl_dia"] for r in dias_pausados)
        print(
            f"\n⚠️   DIAS PAUSADOS (filtro ATR > {p.get('volatility_pause_threshold', 250)}): {len(dias_pausados)}"
        )
        for r in dias_pausados:
            print(
                f"    {r['data']}: HL abertura={r['hl_abertura']} pts | PnL se sem filtro: R$ {r['pnl_dia']:+.2f}"
            )
        print(
            f"    PnL acumulado dos dias pausados (oportunidade/risco): R$ {pnl_pausados:+.2f}"
        )

    # ---- Top/Bottom por dia ----
    print("\n📈  RANKING DIARIO POR PnL:")
    ranking = sorted(resultados, key=lambda r: r["pnl_dia"], reverse=True)
    for i, r in enumerate(ranking):
        flag = "🟢" if r["pnl_dia"] >= 0 else "🔴"
        print(
            f"  {i + 1:>2}. {r['data']} {flag} R${r['pnl_dia']:>+8.2f} "
            f"| {r['total_sinais']} sinais "
            f"| BUY {r['buy']['assertividade']:.0f}% | SELL {r['sell']['assertividade']:.0f}%"
        )


if __name__ == "__main__":
    asyncio.run(main())
