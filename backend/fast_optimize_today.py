import os
import sys
import asyncio
import pandas as pd
import json
import logging
import itertools

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def run_test(params, df_today):
    bt = BacktestPro(symbol="WIN", initial_balance=3000.0, **params)
    bt.balance = 3000.0
    bt.position = None
    bt.trades = []

    for i in range(len(df_today)):
        row = df_today.iloc[i]
        if bt.position:
            exit_type, exit_price = bt.simulate_oco(row, bt.position)
            if exit_type:
                pnl = (
                    (exit_price - bt.position["entry_price"])
                    if bt.position["side"] == "buy"
                    else (bt.position["entry_price"] - exit_price)
                )
                bt.balance += pnl * bt.position["lots"] * 0.20
                bt.trades.append(pnl)
                bt.position = None
            elif i - bt.position["index"] > 20:
                pnl = (
                    (row["close"] - bt.position["entry_price"])
                    if bt.position["side"] == "buy"
                    else (bt.position["entry_price"] - row["close"])
                )
                bt.balance += pnl * bt.position["lots"] * 0.20
                bt.trades.append(pnl)
                bt.position = None

        if not bt.position:
            rsi = row["rsi"]
            if (
                rsi < 30
                and row["close"] < row["lower_bb"]
                and row["tick_volume"] > (row["vol_sma"] * params["vol_spike_mult"])
            ):
                side = "buy"
            elif (
                rsi > 70
                and row["close"] > row["upper_bb"]
                and row["tick_volume"] > (row["vol_sma"] * params["vol_spike_mult"])
            ):
                side = "sell"
            else:
                side = None

            if side:
                sl = (
                    row["close"] - params["sl_dist"]
                    if side == "buy"
                    else row["close"] + params["sl_dist"]
                )
                tp = (
                    row["close"] + params["tp_dist"]
                    if side == "buy"
                    else row["close"] - params["tp_dist"]
                )
                bt.position = {
                    "side": side,
                    "entry_price": row["close"],
                    "sl": sl,
                    "tp": tp,
                    "lots": 1,
                    "index": i,
                }

    return bt.balance - 3000.0, len(bt.trades)


async def fast_optimize_today_strict():
    data_file = "data/sota_training/training_WIN$_MASTER.csv"
    df = pd.read_csv(data_file)
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)

    # Indicadores
    df["rsi"] = 100 - (
        100
        / (
            1
            + (
                df["close"].diff().where(df["close"].diff() > 0, 0).rolling(14).mean()
                / (
                    -(df["close"].diff().where(df["close"].diff() < 0, 0))
                    .rolling(14)
                    .mean()
                    + 1e-6
                )
            )
        )
    )
    df["sma_20"] = df["close"].rolling(20).mean()
    df["upper_bb"] = df["sma_20"] + 2.0 * df["close"].rolling(20).std()
    df["lower_bb"] = df["sma_20"] - 2.0 * df["close"].rolling(20).std()
    df["vol_sma"] = df["tick_volume"].rolling(20).mean()

    df_today = df[df.index.strftime("%Y-%m-%d") == "2026-02-23"].copy()

    grid = {
        "sl_dist": [130, 200],
        "tp_dist": [100, 150, 200, 300],
        "vol_spike_mult": [1.2, 1.5],
        "use_trailing_stop": [False],  # Forçar alvos fixos
        "be_trigger": [50, 80],
        "be_lock": [0, 20],
    }

    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    best_results = []
    for p in combinations:
        pnl, trades = run_test(p, df_today)
        if trades > 0:
            best_results.append((pnl, trades, p))

    best_results.sort(key=lambda x: x[0], reverse=True)

    if best_results:
        pnl, trades, params = best_results[0]
        print(f"🏆 MELHOR AJUSTE ESTRITO: R$ {pnl:.2f} PnL ({trades} trades)")
        print(f"Params: {params}")

        with open("best_params_WIN.json", "w") as f:
            json.dump(
                {"params": params, "net_profit": pnl, "trades": trades}, f, indent=4
            )


if __name__ == "__main__":
    asyncio.run(fast_optimize_today_strict())
