import sys
import os
import pandas as pd
import json
from datetime import time

# Adiciona ao Path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.ai_core import AICore
from backend.risk_manager import RiskManager

DATA_ALVO = "2026-03-10"


def calculate_rsi(series, period=7):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def run_isolated_backtest(initial_balance=3000.0):
    csv_file = f"data/audit_m1_{DATA_ALVO.replace('-', '')}.csv"
    if not os.path.exists(csv_file):
        return {"error": "CSV nao encontrado"}

    df = pd.read_csv(csv_file)
    df["time"] = pd.to_datetime(df["time"])

    risk = RiskManager(initial_balance=initial_balance)
    risk.load_optimized_params("WIN$", "backend/v22_locked_params.json")
    ai = AICore()

    # [ITERAÇÃO M8: SCALPER EXTREMO (RSI Híper Sensível, Alvo Micro)]
    # Usado para tentar extrair lucro de dias laterais caóticos como 10/03
    rsi_period = 3  # Reduzido para seguir o ruído perfeitamente
    vol_spike_mult = 1.2  # Médio/Alto
    end_time_limit = time(17, 15)
    tp_pts = 40  # Alvo micro (Scalper puro)
    sl_pts = -100  # Fôlego mínimo para correção de M1

    balance = initial_balance
    trades = []
    opportunities_missed = []

    df["rsi"] = calculate_rsi(df["close"], period=rsi_period)
    df["vol_sma"] = df["real_volume"].rolling(20).mean()
    df["atr"] = (df["high"] - df["low"]).rolling(14).mean()

    pos_open = None

    for i in range(25, len(df)):
        current_row = df.iloc[i]
        curr_time = current_row["time"].time()

        if curr_time >= end_time_limit:
            if pos_open:
                pnl = (
                    (current_row["close"] - pos_open["price"]) * 0.2 * pos_open["qty"]
                    if pos_open["type"] == "BUY"
                    else (pos_open["price"] - current_row["close"])
                    * 0.2
                    * pos_open["qty"]
                )
                trades.append(
                    {
                        "type": pos_open["type"],
                        "pnl": pnl,
                        "reason": "TIME_LIMIT",
                        "time": str(current_row["time"]),
                    }
                )
                balance += pnl
                pos_open = None
            continue

        if pos_open:
            pnl_pts = (
                current_row["close"] - pos_open["price"]
                if pos_open["type"] == "BUY"
                else pos_open["price"] - current_row["close"]
            )
            max_pnl_pts = (
                current_row["high"] - pos_open["price"]
                if pos_open["type"] == "BUY"
                else pos_open["price"] - current_row["low"]
            )
            min_pnl_pts = (
                current_row["low"] - pos_open["price"]
                if pos_open["type"] == "BUY"
                else pos_open["price"] - current_row["high"]
            )

            if min_pnl_pts <= sl_pts:
                pnl = sl_pts * 0.2 * pos_open["qty"]
                trades.append(
                    {
                        "type": pos_open["type"],
                        "pnl": pnl,
                        "reason": "STOP_LOSS",
                        "time": str(current_row["time"]),
                    }
                )
                balance += pnl
                pos_open = None
                continue

            if max_pnl_pts >= tp_pts:
                pnl = tp_pts * 0.2 * pos_open["qty"]
                trades.append(
                    {
                        "type": pos_open["type"],
                        "pnl": pnl,
                        "reason": "TAKE_PROFIT",
                        "time": str(current_row["time"]),
                    }
                )
                balance += pnl
                pos_open = None
                continue
        else:
            comprar_cond = current_row["rsi"] < 15 and current_row["real_volume"] > (
                current_row["vol_sma"] * vol_spike_mult
            )
            vender_cond = current_row["rsi"] > 85 and current_row["real_volume"] > (
                current_row["vol_sma"] * vol_spike_mult
            )

            if comprar_cond or vender_cond:
                side = "buy" if comprar_cond else "sell"
                regime = ai.detect_regime(current_row["atr"], 1.0)
                market_val = risk.validate_market_condition(
                    "WIN$", regime, current_row["atr"], df["atr"].mean()
                )

                if market_val["allowed"]:
                    pos_open = {
                        "type": "BUY" if side == "buy" else "SELL",
                        "price": current_row["close"],
                        "time": str(current_row["time"]),
                        "qty": 3,
                    }
                else:
                    opportunities_missed.append(
                        {
                            "time": str(current_row["time"]),
                            "side": side,
                            "reason": market_val["reason"],
                        }
                    )

    report = {
        "capital_inicial": initial_balance,
        "saldo_final": balance,
        "total_trades": len(trades),
        "trades": trades,
        "vetos": opportunities_missed,
    }

    with open("audit_report_10mar.json", "w") as f:
        json.dump(report, f, indent=4)

    return report


if __name__ == "__main__":
    run_isolated_backtest()
