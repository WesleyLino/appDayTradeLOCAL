import os
import sys
import asyncio
import pandas as pd
import logging
from datetime import datetime

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


async def run_validated_backtest():
    # 1. Parâmetros Recalibrados (EXATOS da Otimização Vencedora)
    params = {
        "rsi_period": 14,
        "bb_dev": 2.0,
        "sl_dist": 130.0,
        "tp_dist": 100.0,
        "vol_spike_mult": 1.2,
        "use_trailing_stop": False,
        "be_trigger": 50.0,
        "be_lock": 0.0,
        "max_daily_trades": 30,
        "start_time": "09:15",
        "end_time": "17:15",
    }

    # 2. Carregar Dados MASTER
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
    df["std_20"] = df["close"].rolling(20).std()
    df["upper_bb"] = df["sma_20"] + 2.0 * df["std_20"]
    df["lower_bb"] = df["sma_20"] - 2.0 * df["std_20"]
    df["vol_sma"] = df["tick_volume"].rolling(20).mean()

    df_today = df[df.index.strftime("%Y-%m-%d") == "2026-02-23"].copy()

    # 3. Simulação
    bt = BacktestPro(symbol="WIN", initial_balance=3000.0, **params)
    bt.balance = 3000.0
    bt.position = None
    bt.trades_history = []

    logging.info(
        "📊 Iniciando Backtest Validado para 23/02 | Saldo: R$ 3.000,00 | Alvos Curtos"
    )

    for i in range(len(df_today)):
        row = df_today.iloc[i]

        # Saída
        if bt.position:
            exit_type, exit_price = bt.simulate_oco(row, bt.position)
            if exit_type:
                pnl_pts = (
                    (exit_price - bt.position["entry_price"])
                    if bt.position["side"] == "buy"
                    else (bt.position["entry_price"] - exit_price)
                )
                bt.balance += pnl_pts * 0.20
                bt.trades_history.append(pnl_pts)
                logging.info(
                    f"✅ SAÍDA {exit_type} @ {exit_price} | PnL: R$ {(pnl_pts * 0.2):.2f}"
                )
                bt.position = None
            elif i - bt.position["index"] > 20:
                pnl_pts = (
                    (row["close"] - bt.position["entry_price"])
                    if bt.position["side"] == "buy"
                    else (bt.position["entry_price"] - row["close"])
                )
                bt.balance += pnl_pts * 0.20
                bt.trades_history.append(pnl_pts)
                logging.info(
                    f"⏹️ SAÍDA TIME @ {row['close']} | PnL: R$ {(pnl_pts * 0.2):.2f}"
                )
                bt.position = None

        # Entrada
        if not bt.position:
            if (
                row.name.time() < datetime.strptime("09:15", "%H:%M").time()
                or row.name.time() > datetime.strptime("17:15", "%H:%M").time()
            ):
                continue

            if (
                row["rsi"] < 30
                and row["close"] < row["lower_bb"]
                and row["tick_volume"] > (row["vol_sma"] * params["vol_spike_mult"])
            ):
                side = "buy"
            elif (
                row["rsi"] > 70
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
                side_pt = "COMPRA" if side == "buy" else "VENDA"
                logging.info(
                    f"🎯 ENTRADA {side_pt} @ {row['close']} [{row.name.time()}]"
                )

    # 4. Resultados
    print("\n" + "=" * 50)
    print("🏆 RESULTADO FINAL VALIDADO - 23/02 (PROVA DE RECALIBRAÇÃO)")
    print("=" * 50)
    print("Saldo Inicial: R$ 3000.00")
    print(f"Saldo Final:   R$ {bt.balance:.2f}")
    print(f"Lucro Líquido: R$ {bt.balance - 3000.0:.2f}")
    print(f"Total Trades:  {len(bt.trades_history)}")
    wins = len([t for t in bt.trades_history if t > 0])
    print(f"Win Rate:      {(wins / len(bt.trades_history) * 100):.1f}%")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_validated_backtest())
