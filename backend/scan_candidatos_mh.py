"""
[MELHORIA-H VALIDAÇÃO] Scanner robusto de dias candidatos — v3 (numpy structured array fix).
Identifica dias onde risk_index > 2.5 para validar o Bypass Condicional de Pânico.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

SYMBOL   = "WIN$"
ATR_MM20 = 75.0

# Últimos ~60 pregões (3 meses corridos)
data_fim    = datetime(2026, 3, 14)
data_inicio = datetime(2025, 12, 15)

mt5.initialize()
print(f"Varrendo {SYMBOL} de {data_inicio.date()} até {data_fim.date()}...")
print(f"Critério: risk_index > 2.5 (ATR > {ATR_MM20*2.5:.0f} pts)\n")

resultados = []
dias_ok = 0
data_atual = data_inicio

while data_atual <= data_fim:
    if data_atual.weekday() >= 5:          # pular fim de semana
        data_atual += timedelta(days=1)
        continue

    d_from = datetime(data_atual.year, data_atual.month, data_atual.day, 9,  0)
    d_to   = datetime(data_atual.year, data_atual.month, data_atual.day, 17, 30)

    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, d_from, d_to)

    # Guard: sem dados (feriado ou pregão fechado)
    if rates is None or len(rates) < 30:
        data_atual += timedelta(days=1)
        continue

    # Numpy structured array → DataFrame diretamente (NÃO usar list())
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df["hl"]         = df["high"] - df["low"]
    df["atr"]        = df["hl"].rolling(14).mean().fillna(df["hl"])
    df["risk_index"] = df["atr"] / ATR_MM20

    panico_c   = int((df["risk_index"] > 2.5).sum())
    vol_alta_c = int(((df["risk_index"] > 1.6) & (df["risk_index"] <= 2.5)).sum())
    atr_max    = float(df["atr"].max())
    atr_medio  = float(df["atr"].mean())
    ri_max     = float(df["risk_index"].max())
    mov_total  = float((df["high"] - df["low"]).sum())

    # Score composto
    score = panico_c * 5 + vol_alta_c + (3 if mov_total > 5000 else 0)

    resultados.append({
        "data":             str(data_atual.date()),
        "score":            int(score),
        "panico_candles":   panico_c,
        "vol_alta_candles": vol_alta_c,
        "atr_max":          round(atr_max, 1),
        "atr_medio":        round(atr_medio, 1),
        "risk_index_max":   round(ri_max, 2),
        "mov_total":        int(mov_total),
        "total_candles":    len(df),
    })
    dias_ok += 1
    data_atual += timedelta(days=1)

mt5.shutdown()

# ── Relatório ──────────────────────────────────────────────────────────────────
df_res = pd.DataFrame(resultados).sort_values("score", ascending=False)
com_panico  = df_res[df_res["panico_candles"] > 0]
sem_panico  = df_res[df_res["panico_candles"] == 0]

print("=" * 85)
print(f"  TOP CANDIDATOS — {len(com_panico)} pregões com pânico (de {dias_ok} analisados)")
print("=" * 85)
print(f"  {'Data':12s}  {'Sc':4s}  {'Pânico':7s}  {'VolAlta':8s}  {'ATR Max':8s}  {'ATR Med':8s}  {'RI Max':6s}")
print("-" * 85)

candidatos_datas = []
for _, row in com_panico.head(12).iterrows():
    ideal = " ◄ IDEAL" if row["panico_candles"] >= 3 and row["mov_total"] > 5000 else ""
    print(
        f"  {row['data']:12s}  {row['score']:3d}    {row['panico_candles']:4d}     "
        f"{row['vol_alta_candles']:5d}    {row['atr_max']:7.1f}   {row['atr_medio']:6.1f}   {row['risk_index_max']:5.2f}{ideal}"
    )
    candidatos_datas.append(row["data"])

print()
print("  CONTROLE — 5 dias sem pânico (para comparação A×B):")
controle_datas = []
for _, row in sem_panico.sort_values("atr_medio", ascending=False).head(5).iterrows():
    print(f"  {row['data']:12s}  ATR Med={row['atr_medio']:.1f}  RI Max={row['risk_index_max']:.2f}")
    controle_datas.append(row["data"])
print("=" * 85)

# ── Export JSON ────────────────────────────────────────────────────────────────
output = {
    "candidatos_melhoria_h": candidatos_datas[:8],
    "dias_controle":          controle_datas,
    "gerado_em":              str(datetime.now()),
    "criterio":               f"risk_index > 2.5 (ATR > {ATR_MM20*2.5:.0f} pts)"
}
with open("backend/candidatos_melhoria_h.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print("\n  ✅ Exportado: backend/candidatos_melhoria_h.json")
print(f"  {len(candidatos_datas)} candidatos | {len(controle_datas)} controles")
