import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
import json
import numpy as np

# Configuração Padrão
SYMBOL_CONTINUO = "WIN$"
SYMBOL_CONTRAT = "WINJ25"
TIMEFRAME = mt5.TIMEFRAME_M1
PARAMS_FILE = "backend/v22_locked_params.json"
CAPITAL = 3000.0

DATAS_TESTE = [
    (2026, 2, 19),
    (2026, 2, 20),
    (2026, 2, 23),
    (2026, 2, 24),
    (2026, 2, 25),
    (2026, 2, 26),
    (2026, 2, 27),
    (2026, 3, 2),
    (2026, 3, 3),
    (2026, 3, 4),
    (2026, 3, 5),
    (2026, 3, 6),
    (2026, 3, 9),
    (2026, 3, 10),
]


def calculate_rsi(prices, period=7):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()


def load_params():
    try:
        with open(PARAMS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("strategy_params", {})
    except Exception as e:
        print(f"Erro ao carregar parametros: {e}")
        return {}


def simular_dia(ano, mes, dia, params):
    timezone_offset = timedelta(hours=3)
    start_time = datetime(ano, mes, dia, 9, 0) + timezone_offset
    end_time = datetime(ano, mes, dia, 18, 0) + timezone_offset

    rates = mt5.copy_rates_range(SYMBOL_CONTRAT, TIMEFRAME, start_time, end_time)
    if rates is None or len(rates) == 0:
        rates = mt5.copy_rates_range(SYMBOL_CONTINUO, TIMEFRAME, start_time, end_time)

    df = pd.DataFrame(rates)
    if df.empty:
        return {"compras": [], "vendas": [], "perdidas": [], "valido": False}

    df["time"] = pd.to_datetime(df["time"], unit="s") - timezone_offset

    # Carregar Ouro (SOTA Params)
    rsi_per = params.get("rsi_period", 7)
    vol_mult = params.get("vol_spike_mult", 1.5)
    atr_min = params.get("min_atr_threshold", 50.0)
    tp_pts = params.get("tp_dist", 450.0)
    sl_pts = -params.get("sl_dist", 150.0)
    be_trigger = 40.0  # Protecao

    # Pre-calculos
    df["rsi"] = calculate_rsi(df["close"], period=rsi_per)
    df["vol_sma"] = df["real_volume"].rolling(20).mean()
    df["atr"] = calculate_atr(df, period=14)

    compras_realizadas = []
    vendas_realizadas = []
    oportunidades_perdidas = []
    pos_open = None

    for i in range(25, len(df)):
        current = df.iloc[i]
        c_time = current["time"].time()

        # Ignorar leilão
        if c_time < time(9, 15) or c_time >= time(17, 15):
            if pos_open:
                pnl_pts = (
                    current["close"] - pos_open["price"]
                    if pos_open["type"] == "BUY"
                    else pos_open["price"] - current["close"]
                )
                pos_open["pnl_pts"] = pnl_pts
                pos_open["reason"] = "TIME_LIMIT"
                if pos_open["type"] == "BUY":
                    compras_realizadas.append(pos_open)
                else:
                    vendas_realizadas.append(pos_open)
                pos_open = None
            continue

        # Marcador Oportunidades
        if current["high"] - current["low"] > 150 and not pos_open:
            oportunidades_perdidas.append(
                {"amplitude": current["high"] - current["low"]}
            )

        if pos_open:
            max_pnl_pts = (
                current["high"] - pos_open["price"]
                if pos_open["type"] == "BUY"
                else pos_open["price"] - current["low"]
            )
            min_pnl_pts = (
                current["low"] - pos_open["price"]
                if pos_open["type"] == "BUY"
                else pos_open["price"] - current["high"]
            )

            # Dinamica Break-Even
            current_sl = sl_pts
            if pos_open["max_runup"] >= be_trigger or max_pnl_pts >= be_trigger:
                current_sl = 0

            if min_pnl_pts <= current_sl:
                pos_open["pnl_pts"] = current_sl
                pos_open["reason"] = "BREAK_EVEN" if current_sl == 0 else "STOP_LOSS"
                if pos_open["type"] == "BUY":
                    compras_realizadas.append(pos_open)
                else:
                    vendas_realizadas.append(pos_open)
                pos_open = None
                continue

            if max_pnl_pts >= tp_pts:
                pos_open["pnl_pts"] = tp_pts
                pos_open["reason"] = "TAKE_PROFIT"
                if pos_open["type"] == "BUY":
                    compras_realizadas.append(pos_open)
                else:
                    vendas_realizadas.append(pos_open)
                pos_open = None
                continue

            if max_pnl_pts > pos_open["max_runup"]:
                pos_open["max_runup"] = max_pnl_pts

        else:
            vol_condition = current["real_volume"] > (current["vol_sma"] * vol_mult)
            atr_condition = current["atr"] >= atr_min
            if vol_condition and atr_condition:
                if current["rsi"] <= 30:
                    pos_open = {
                        "type": "BUY",
                        "price": current["close"],
                        "time": str(c_time),
                        "max_runup": 0,
                    }
                elif current["rsi"] >= 70:
                    pos_open = {
                        "type": "SELL",
                        "price": current["close"],
                        "time": str(c_time),
                        "max_runup": 0,
                    }

    return {
        "compras": compras_realizadas,
        "vendas": vendas_realizadas,
        "perdidas": oportunidades_perdidas,
        "valido": True,
    }


def run_all_days():
    if not mt5.initialize():
        print("Falha MT5")
        return

    print("===================================================================")
    print("    AUDITORIA MACRO-DIRECIONAL (SOTA GOLDEN V3) - 14 DIAS UTEIS")
    print("===================================================================")

    params = load_params()
    total_compras = 0
    total_vendas = 0
    total_pnl = 0.0
    total_be = 0
    total_loss = 0
    total_tp = 0
    total_perdidas = 0

    for a, m, d in DATAS_TESTE:
        dia_str = f"{d:02d}/{m:02d}"
        res = simular_dia(a, m, d, params)
        if not res["valido"]:
            print(f"[{dia_str}] -> SEM DADOS")
            continue

        c = res["compras"]
        v = res["vendas"]
        p_c = sum(x["pnl_pts"] * 0.2 for x in c)
        p_v = sum(x["pnl_pts"] * 0.2 for x in v)
        pnl_dia = p_c + p_v

        qt_be = sum(1 for x in c + v if x["reason"] == "BREAK_EVEN")
        qt_sl = sum(1 for x in c + v if x["reason"] == "STOP_LOSS")
        qt_tp = sum(1 for x in c + v if x["reason"] == "TAKE_PROFIT")

        print(
            f"► [{dia_str}] PnL: R$ {pnl_dia:>7.2f} | Compras: {len(c)} | Vendas: {len(v)} | Defesas(BE): {qt_be} | Losses: {qt_sl} | Big Pernas Iguais: {len(res['perdidas'])}"
        )

        total_compras += len(c)
        total_vendas += len(v)
        total_pnl += pnl_dia
        total_be += qt_be
        total_loss += qt_sl
        total_tp += qt_tp
        total_perdidas += len(res["perdidas"])

    print("-------------------------------------------------------------------")
    print(f"  SALDO GLOBAL (14 DIAS)  : R$ {total_pnl:.2f}")
    print(
        f"  TOTAL DE ENTRADAS       : {total_compras + total_vendas} trades (C:{total_compras} V:{total_vendas})"
    )
    print(
        f"  BLINDAGENS P/ BREAK-EVEN: {total_be} trades (Eram perdas que fecharam em R$ 0,00)"
    )
    print(f"  LOSSES CHEIOS ESPERA    : {total_loss} trades")
    print(f"  OPORTUNIDADES GIGANTES  : {total_perdidas} pernas ignoradas pela Matriz")
    print("===================================================================")
    mt5.shutdown()


if __name__ == "__main__":
    run_all_days()
