# --- encoding: utf-8 ---
"""
Strategy Optimizer - Mini Indice WIN$ (Fev/Mar 2026)
Testa 6 configuracoes progressivas de filtros para maximizar assertividade.
MODO LEITURA: Nenhuma alteracao no codigo de producao.
"""

import asyncio
import pandas as pd
import numpy as np
import json
import os
import sys
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


class NumpyEncoder(json.JSONEncoder):
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


SYMBOL = "WIN$"
N_CANDLES = 10000
PONTO_BRL = 0.20  # R$/ponto/lote
LIMIT_TRADES_DIA = 2
SEP = "=" * 80

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
    "2026-03-11",
]


# =====================================================================
# DEFINICAO DAS 7 ITERACOES
# =====================================================================
@dataclass
class FilterConfig:
    nome: str
    descricao: str
    filtro_bias_h1: bool = True
    filtro_vwap_sell: bool = True
    filtro_vwap_buy: bool = True
    filtro_rsi_extremo: bool = False
    filtro_cooldown_stop: bool = True
    filtro_adx_tendencia: bool = True
    # Variaveis de Refinamento (Overrides)
    sl_override: Optional[float] = 200.0
    tp_override: Optional[float] = 600.0
    tp_buy_override: Optional[float] = None
    tp_sell_override: Optional[float] = None
    bb_dev_override: Optional[float] = None
    vol_mult_override: Optional[float] = None
    adx_min_override: Optional[float] = None
    rsi_buy_override: Optional[float] = None
    rsi_sell_override: Optional[float] = None
    lot_multiplier: float = 1.0
    confidence_buy_override: Optional[float] = None
    confidence_sell_override: Optional[float] = None
    use_trailing: bool = False
    limit_trades_override: Optional[int] = None
    meta_diaria: Optional[float] = None
    stop_diario: Optional[float] = None
    start_time: str = "09:15"
    end_time: str = "17:15"


ITERACOES = [
    FilterConfig(
        nome="ACTIVE_SNIPER_V25",
        descricao="FREQUÊNCIA: RSI 24/76 | 1 Lote | Buscando +Trades/Dia",
        start_time="09:30",
        end_time="12:00",
        rsi_buy_override=24.0,
        rsi_sell_override=76.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="SCALE_SNIPER_V25",
        descricao="ALAVANCAGEM: V24 Asymmetric | 2 Lotes | R$ 3k Capital",
        start_time="09:30",
        end_time="12:00",
        sl_override=200.0,
        tp_buy_override=200.0,
        tp_sell_override=400.0,
        lot_multiplier=2.0,
        rsi_buy_override=18.0,
        rsi_sell_override=82.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="SAFE_DAY_V23",
        descricao="REFERÊNCIA: SAFE V23 (A SER MANTIDA)",
        start_time="09:30",
        end_time="12:00",
        sl_override=200.0,
        tp_override=200.0,
        rsi_buy_override=18.0,
        rsi_sell_override=82.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="TREND_RIDER_V26",
        descricao="ELITE: V24 + Trailing Stop | Capital 3k | 2 Lotes",
        start_time="09:30",
        end_time="12:00",
        sl_override=200.0,
        tp_buy_override=200.0,
        tp_sell_override=1000.0,  # Alvo longo, sai no trail
        lot_multiplier=2.0,
        use_trailing=True,
        rsi_buy_override=18.0,
        rsi_sell_override=82.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="SCALE_SNIPER_V26_3LOTS",
        descricao="AGRESSIVO: V24 | 3 Lotes | Alvo R$ 200+/dia",
        start_time="09:30",
        end_time="12:00",
        sl_override=200.0,
        tp_buy_override=200.0,
        tp_sell_override=400.0,
        lot_multiplier=3.0,
        rsi_buy_override=18.0,
        rsi_sell_override=82.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="ACTIVE_SNIPER_V26_3TRADES",
        descricao="FREQUÊNCIA+: RSI 18/82 | 2 Lotes | Até 3 Trades/Dia",
        start_time="09:15",
        end_time="14:00",
        sl_override=200.0,
        tp_buy_override=200.0,
        tp_sell_override=400.0,
        lot_multiplier=2.0,
        limit_trades_override=3,
        rsi_buy_override=18.0,
        rsi_sell_override=82.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="UNLIMITED_GOLD_V31",
        descricao="GOLD: RSI 18/82 | 3 Lotes | Ilimitado | Meta R$500",
        start_time="09:15",
        end_time="13:00",
        sl_override=200.0,
        tp_buy_override=200.0,
        tp_sell_override=400.0,
        lot_multiplier=3.0,
        limit_trades_override=99,
        rsi_buy_override=18.0,
        rsi_sell_override=82.0,
        meta_diaria=500.0,
        stop_diario=-300.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="UNLIMITED_PRECISION_V31",
        descricao="PRECISION: RSI 16/84 | 3 Lotes | Ilimitado | Dia Inteiro",
        start_time="09:15",
        end_time="17:15",
        sl_override=200.0,
        tp_buy_override=200.0,
        tp_sell_override=400.0,
        lot_multiplier=3.0,
        limit_trades_override=99,
        rsi_buy_override=16.0,
        rsi_sell_override=84.0,
        meta_diaria=600.0,
        stop_diario=-300.0,
        filtro_adx_tendencia=True,
    ),
    FilterConfig(
        nome="HIGH_PERF_CALIBRADA_V36",
        descricao="V36: Calibragem 11/03 | RSI 18/82 | Thr 0.52 SELL | 3 Lotes",
        start_time="09:15",
        end_time="13:00",
        sl_override=200.0,
        tp_buy_override=200.0,
        tp_sell_override=400.0,
        lot_multiplier=3.0,
        limit_trades_override=99,
        rsi_buy_override=18.0,
        rsi_sell_override=82.0,
        confidence_sell_override=0.52,
        meta_diaria=800.0,
        stop_diario=-400.0,
        filtro_adx_tendencia=True,
    ),
]


# =====================================================================
# ENGINE DE TRACE COM FILTROS
# =====================================================================
def traceiar_dia_com_filtros(
    df_all: pd.DataFrame,
    data_str: str,
    p: dict,
    cfg: FilterConfig,
) -> dict | None:
    """
    Trace de sinais M1 para um dia, aplicando os filtros da configuracao.
    Replica os indicadores do BacktestPro.run() sem alterar producao.
    """
    df = df_all[df_all.index.strftime("%Y-%m-%d") == data_str].copy()
    if df.empty:
        return None

    # Parametros base V22 (Refinados pela Fase 2)
    rsi_p = int(p.get("rsi_period", 9))
    bb_d = (
        cfg.bb_dev_override
        if cfg.bb_dev_override is not None
        else float(p.get("bb_dev", 2.0))
    )
    vm = (
        cfg.vol_mult_override
        if cfg.vol_mult_override is not None
        else float(p.get("vol_spike_mult", 1.0))
    )
    sl = (
        cfg.sl_override
        if cfg.sl_override is not None
        else float(p.get("sl_dist", 200.0))
    )
    tp = (
        cfg.tp_override
        if cfg.tp_override is not None
        else float(p.get("tp_dist", 600.0))
    )
    rsi_buy = (
        int(p.get("rsi_buy_level", 32)) if cfg.nome != "OPT4_CONSERVATIVE_RSI" else 20
    )
    rsi_sell = (
        int(p.get("rsi_sell_level", 68)) if cfg.nome != "OPT4_CONSERVATIVE_RSI" else 80
    )
    vol_thr = float(p.get("volatility_pause_threshold", 250.0))
    atr_min = float(p.get("min_atr_threshold", 50.0))

    # Inversão de cooldown se for strict
    COOLDOWN_MIN = 60 if cfg.nome == "REF6_STRICT_COOLDOWN" else 30

    # ---- Indicadores ----
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

    # VWAP
    tp_v = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["tick_volume"]
    df["vwap"] = (tp_v * vol).cumsum() / vol.cumsum()
    df["vwap_std"] = tp_v.rolling(20).std().fillna(0)

    # EMA30/90 para Bias H1
    df["ema30"] = df["close"].ewm(span=30, adjust=False).mean()
    df["ema90"] = df["close"].ewm(span=90, adjust=False).mean()

    # ADX 14
    plus_dm = (df["high"] - df["high"].shift(1)).clip(lower=0)
    minus_dm = (df["low"].shift(1) - df["low"]).clip(lower=0)
    plus_dm.loc[plus_dm < minus_dm] = 0
    minus_dm.loc[minus_dm < plus_dm] = 0
    tr_sm = tr.ewm(span=14, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=14, adjust=False).mean() / (tr_sm + 1e-9))
    minus_di = 100 * (minus_dm.ewm(span=14, adjust=False).mean() / (tr_sm + 1e-9))
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
    df["adx"] = dx.ewm(span=14, adjust=False).mean()

    # Filtro ATR abertura
    df_ab = df.between_time("09:00", "09:10")
    hl_abertura = (
        float((df_ab["high"] - df_ab["low"]).mean()) if not df_ab.empty else 0.0
    )
    dia_pausado = hl_abertura >= vol_thr

    # ---- Trace de Sinais com Filtros ----
    sinais = []
    cooldown_buy = datetime(2000, 1, 1)
    cooldown_sell = datetime(2000, 1, 1)
    COOLDOWN_MIN = 30
    trades_dia = 0
    pnl_acumulado = 0.0
    limite_trades = (
        cfg.limit_trades_override
        if cfg.limit_trades_override is not None
        else LIMIT_TRADES_DIA
    )

    for i in range(max(25, rsi_p * 2), len(df)):
        row = df.iloc[i]
        hora = row.name.strftime("%H:%M")
        if hora < cfg.start_time or hora > cfg.end_time:
            continue

        if trades_dia >= limite_trades:
            continue

        # Filtro de Metas Financeiras
        if cfg.meta_diaria and pnl_acumulado >= cfg.meta_diaria:
            dia_pausado = "META_ATINGIDA"
            continue
        if cfg.stop_diario and pnl_acumulado <= cfg.stop_diario:
            dia_pausado = "STOP_DIARIO"
            continue

        vol_ok = float(row["tick_volume"]) >= float(row["vol_sma"]) * vm
        atr_ok = float(row["atr"]) >= atr_min if not np.isnan(row["atr"]) else False
        rsi_val = float(row["rsi"])

        r_buy = cfg.rsi_buy_override if cfg.rsi_buy_override is not None else rsi_buy
        r_sell = (
            cfg.rsi_sell_override if cfg.rsi_sell_override is not None else rsi_sell
        )

        cond_buy = (
            rsi_val <= r_buy
            and float(row["close"]) <= float(row["lower_bb"])
            and vol_ok
            and atr_ok
        )
        cond_sell = (
            rsi_val >= r_sell
            and float(row["close"]) >= float(row["upper_bb"])
            and vol_ok
            and atr_ok
        )

        if not (cond_buy or cond_sell):
            continue

        lado = "BUY" if cond_buy else "SELL"

        # --- Aplicacao dos Filtros ---
        motivo_veto = None

        # Filtro 1: Bias H1
        if cfg.filtro_bias_h1 and motivo_veto is None:
            tendencia_alta = float(row["ema30"]) > float(row["ema90"])
            if lado == "BUY" and not tendencia_alta:
                motivo_veto = "BIAS_H1_CONTRA"
            if lado == "SELL" and tendencia_alta:
                motivo_veto = "BIAS_H1_CONTRA"

        # Filtro 2: VWAP SELL
        if cfg.filtro_vwap_sell and motivo_veto is None and lado == "SELL":
            if float(row["close"]) < float(row["vwap"]) - float(row["vwap_std"]):
                motivo_veto = "VWAP_SELL_BAIXO"

        # Filtro 3: VWAP BUY
        if cfg.filtro_vwap_buy and motivo_veto is None and lado == "BUY":
            if float(row["close"]) > float(row["vwap"]) + float(row["vwap_std"]):
                motivo_veto = "VWAP_BUY_ALTO"

        # Filtro 4: ADX tendencia
        if cfg.filtro_adx_tendencia and motivo_veto is None:
            adx_val = float(row["adx"]) if not np.isnan(row["adx"]) else 0.0
            adx_min = cfg.adx_min_override if cfg.adx_min_override is not None else 20.0
            if adx_val < adx_min:
                motivo_veto = f"ADX_FRACO_{adx_min}"

        # Filtro 5: Cooldown pos-STOP
        if cfg.filtro_cooldown_stop and motivo_veto is None:
            ts = row.name.to_pydatetime().replace(tzinfo=None)
            if lado == "BUY" and cooldown_buy > ts:
                motivo_veto = "COOLDOWN_BUY"
            if lado == "SELL" and cooldown_sell > ts:
                motivo_veto = "COOLDOWN_SELL"

        entry = float(row["close"])
        sl_atual = cfg.sl_override if cfg.sl_override is not None else sl

        # TP Assimétrico
        if lado == "BUY":
            tp_atual = cfg.tp_buy_override if cfg.tp_buy_override is not None else tp
        else:
            tp_atual = cfg.tp_sell_override if cfg.tp_sell_override is not None else tp

        trades_dia += 1

        sl_val = entry - sl_atual if lado == "BUY" else entry + sl_atual
        tp_val = entry + tp_atual if lado == "BUY" else entry - tp_atual

        resultado = "VETADO" if motivo_veto else "EXPIRADO"
        pnl_pts = 0.0
        saiu_hora = hora

        if not motivo_veto:
            for j in range(i + 1, min(i + 120, len(df))):
                f = df.iloc[j]
                if lado == "BUY":
                    if float(f["low"]) <= sl_val:
                        resultado = (
                            "STOP" if sl_val <= (entry - sl_atual + 5) else "TAKE_TRAIL"
                        )
                        pnl_pts = sl_val - entry
                        saiu_hora = f.name.strftime("%H:%M")
                        break
                    if float(f["high"]) >= tp_val:
                        resultado = "TAKE"
                        pnl_pts = tp_atual
                        saiu_hora = f.name.strftime("%H:%M")
                        break

                    if cfg.use_trailing:
                        dist = float(f["high"]) - entry
                        if dist >= 200:
                            sl_val = max(sl_val, entry + 10)  # BE+10
                        if dist >= 400:
                            sl_val = max(sl_val, float(f["high"]) - 150)  # Trail 150
                else:  # SELL
                    if float(f["high"]) >= sl_val:
                        resultado = (
                            "STOP" if sl_val >= (entry + sl_atual - 5) else "TAKE_TRAIL"
                        )
                        pnl_pts = entry - sl_val
                        saiu_hora = f.name.strftime("%H:%M")
                        break
                    if float(f["low"]) <= tp_val:
                        resultado = "TAKE"
                        pnl_pts = tp_atual
                        saiu_hora = f.name.strftime("%H:%M")
                        break

                    if cfg.use_trailing:
                        dist = entry - float(f["low"])
                        if dist >= 200:
                            sl_val = min(sl_val, entry - 10)  # BE+10
                        if dist >= 400:
                            sl_val = min(sl_val, float(f["low"]) + 150)  # Trail 150

            # Atualiza cooldown apos STOP
            if resultado == "STOP" and cfg.filtro_cooldown_stop:
                ts = row.name.to_pydatetime().replace(tzinfo=None)
                dead = ts + timedelta(minutes=COOLDOWN_MIN)
                if lado == "BUY":
                    cooldown_buy = dead
                else:
                    cooldown_sell = dead

        pnl_brl = round(
            abs(pnl_pts) * PONTO_BRL * cfg.lot_multiplier * (1 if pnl_pts > 0 else -1),
            2,
        )
        pnl_acumulado += pnl_brl

        sinais.append(
            {
                "hora": hora,
                "hora_saida": saiu_hora,
                "lado": lado,
                "rsi": round(rsi_val, 1),
                "resultado": resultado,
                "pnl_pts": round(float(pnl_pts), 1),
                "pnl_brl": float(pnl_brl),
                "motivo_veto": motivo_veto,
            }
        )

    def resumir(lado_str):
        sub = [s for s in sinais if s["lado"] == lado_str]
        atv = [s for s in sub if s["resultado"] != "VETADO"]
        takes = [s for s in atv if s["resultado"] == "TAKE"]
        stops = [s for s in atv if s["resultado"] == "STOP"]
        vet = [s for s in sub if s["resultado"] == "VETADO"]
        n_atv = len(atv)
        return {
            "sinais_brutos": len(sub),
            "ativos": n_atv,
            "vetados": len(vet),
            "takes": len(takes),
            "stops": len(stops),
            "ganho_brl": round(sum(s["pnl_brl"] for s in takes), 2),
            "perda_brl": round(abs(sum(s["pnl_brl"] for s in stops)), 2),
            "pnl_liquido": round(sum(s["pnl_brl"] for s in atv), 2),
            "assertividade": round(len(takes) / n_atv * 100, 1) if n_atv > 0 else 0.0,
        }

    return {
        "data": data_str,
        "dia_pausado": bool(dia_pausado),
        "hl_abertura": round(hl_abertura, 1),
        "buy": resumir("BUY"),
        "sell": resumir("SELL"),
        "pnl_dia": round(
            sum(s["pnl_brl"] for s in sinais if s["resultado"] != "VETADO"), 2
        ),
        "total_sinais_ativos": len([s for s in sinais if s["resultado"] != "VETADO"]),
    }


# =====================================================================
# RUNNER PRINCIPAL
# =====================================================================
async def executar_iteracao(df_all, p, cfg: FilterConfig) -> dict:
    """Executa uma iteracao sobre todos os dias e retorna resumo."""
    resultados = []
    for data in DIAS:
        if data not in set(df_all.index.strftime("%Y-%m-%d").unique()):
            continue
        r = traceiar_dia_com_filtros(df_all, data, p, cfg)
        if r:
            resultados.append(r)

    if not resultados:
        return {"config": cfg.nome, "dados": []}

    tb = sum(r["buy"]["takes"] for r in resultados)
    sb = sum(r["buy"]["stops"] for r in resultados)
    ts = sum(r["sell"]["takes"] for r in resultados)
    ss = sum(r["sell"]["stops"] for r in resultados)
    ab = sum(r["buy"]["ativos"] for r in resultados)
    as_ = sum(r["sell"]["ativos"] for r in resultados)
    pnl = round(sum(r["pnl_dia"] for r in resultados), 2)
    dias_pos = sum(1 for r in resultados if r["pnl_dia"] > 0)
    dias_neg = sum(1 for r in resultados if r["pnl_dia"] < 0)

    buy_assert = round(tb / ab * 100, 1) if ab > 0 else 0.0
    sell_assert = round(ts / as_ * 100, 1) if as_ > 0 else 0.0
    total_atv = ab + as_
    total_t = tb + ts
    total_assert = round(total_t / total_atv * 100, 1) if total_atv > 0 else 0.0

    ganho_total = sum(
        r["buy"]["ganho_brl"] + r["sell"]["ganho_brl"] for r in resultados
    )
    perda_total = sum(
        r["buy"]["perda_brl"] + r["sell"]["perda_brl"] for r in resultados
    )

    # Fator de Lucro (Profit Factor)
    pf = round(ganho_total / max(perda_total, 0.01), 2)

    return {
        "config": cfg.nome,
        "descricao": cfg.descricao,
        "dias_analisados": len(resultados),
        "dias_positivos": dias_pos,
        "dias_negativos": dias_neg,
        "buy_ativos": ab,
        "buy_takes": tb,
        "buy_stops": sb,
        "buy_assert": buy_assert,
        "sell_ativos": as_,
        "sell_takes": ts,
        "sell_stops": ss,
        "sell_assert": sell_assert,
        "total_ativos": total_atv,
        "total_assert": total_assert,
        "ganho_total_brl": round(ganho_total, 2),
        "perda_total_brl": round(perda_total, 2),
        "pnl_total_brl": pnl,
        "profit_factor": pf,
        "por_dia": resultados,
    }


async def main():
    print("🚀  OPTIMIZER ITERATIVO — WIN$ Mini Índice | 15 Pregões Fev/Mar 2026")
    print(SEP)

    bt = BacktestPro(symbol=SYMBOL, n_candles=N_CANDLES)
    p = bt.opt_params  # Golden Params V22

    print(
        f"⚙️   RSI={p['rsi_period']} | SL={p['sl_dist']} | TP={p['tp_dist']} | BB={p['bb_dev']}"
    )
    print(
        f"     RSI-Compra≤{p['rsi_buy_level']} | RSI-Venda≥{p['rsi_sell_level']} | MultVol={p['vol_spike_mult']}"
    )
    print("📥   Coletando histórico MT5...")

    df_all = await bt.load_data()
    if df_all is None or df_all.empty:
        print("❌  Falha na coleta MT5.")
        return

    datas_disp = set(df_all.index.strftime("%Y-%m-%d").unique())
    print(
        f"✅   {len(df_all)} candles | {df_all.index[0].date()} → {df_all.index[-1].date()}"
    )
    print(SEP)

    print(
        f"\n{'Config':<22} {'Assert':>8} {'PnL Total':>11} {'PF':>6} {'Dias+':>6} {'BUY%':>6} {'SELL%':>7} {'Ativos':>7}"
    )
    print("-" * 80)

    todos_resultados = []
    melhor = None

    for cfg in ITERACOES:
        r = await executar_iteracao(df_all, p, cfg)
        todos_resultados.append(r)

        flag = (
            "⭐"
            if (melhor is None or r["pnl_total_brl"] > melhor["pnl_total_brl"])
            else "  "
        )
        if melhor is None or r["pnl_total_brl"] > melhor["pnl_total_brl"]:
            melhor = r

        print(
            f"  {flag} {cfg.nome:<20} {r['total_assert']:>7.1f}% "
            f"R${r['pnl_total_brl']:>+9.2f} "
            f"{r['profit_factor']:>5.2f}x "
            f"{r['dias_positivos']:>5}/{r['dias_analisados']} "
            f"{r['buy_assert']:>5.1f}% "
            f"{r['sell_assert']:>6.1f}% "
            f"{r['total_ativos']:>7}"
        )

    print(SEP)

    # Salvar resultados completos
    out = "backend/optimizer_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(todos_resultados, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    # Tabela de métricas completa
    print("\n📊  TABELA COMPARATIVA COMPLETA")
    print(SEP)
    hdr = f"{'Config':<22} {'Total Ativos':>13} {'Takes':>6} {'Stops':>6} {'Assert':>8} {'Ganho':>11} {'Perda':>11} {'PnL':>11} {'PF':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in todos_resultados:
        total_t = r["buy_takes"] + r["sell_takes"]
        total_s = r["buy_stops"] + r["sell_stops"]
        print(
            f"  {r['config']:<22} {r['total_ativos']:>13} {total_t:>6} {total_s:>6} "
            f"{r['total_assert']:>7.1f}% "
            f"R${r['ganho_total_brl']:>9.2f} "
            f"R${r['perda_total_brl']:>9.2f} "
            f"R${r['pnl_total_brl']:>+9.2f} "
            f"{r['profit_factor']:>5.2f}x"
        )

    print(SEP)
    print(f"\n🏆  MELHOR CONFIGURACAO: {melhor['config']}")
    print(
        f"    PnL Total: R$ {melhor['pnl_total_brl']:+.2f} | Assertividade: {melhor['total_assert']:.1f}% | PF: {melhor['profit_factor']:.2f}x"
    )
    print(
        f"    BUY Assert: {melhor['buy_assert']:.1f}% | SELL Assert: {melhor['sell_assert']:.1f}%"
    )
    print(f"    Dias positivos: {melhor['dias_positivos']}/{melhor['dias_analisados']}")

    # Tabela por dia para a melhor config
    print(f"\n📅  DETALHE POR DIA — {melhor['config']}")
    print(
        f"  {'Data':<14} {'PnL Dia':>10} {'BUY T/S':>10} {'BUY%':>7} {'SELL T/S':>10} {'SELL%':>7}"
    )
    print("  " + "-" * 62)
    for r_dia in sorted(melhor["por_dia"], key=lambda x: x["pnl_dia"], reverse=True):
        flag = "🟢" if r_dia["pnl_dia"] >= 0 else "🔴"
        b = r_dia["buy"]
        s = r_dia["sell"]
        buy_str = f"{b['takes']}T/{b['stops']}S"
        sell_str = f"{s['takes']}T/{s['stops']}S"
        print(
            f"  {r_dia['data']} {flag} R${r_dia['pnl_dia']:>+8.2f}   "
            f"{buy_str:>8}  {b['assertividade']:>5.1f}%   "
            f"{sell_str:>8}  {s['assertividade']:>5.1f}%"
        )

    print(f"\n✅  Resultados completos salvos em: {out}")


if __name__ == "__main__":
    asyncio.run(main())
