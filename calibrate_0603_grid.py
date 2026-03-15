import asyncio
import pandas as pd
import json
import os
from backend.backtest_pro import BacktestPro


async def calibrar():
    print("======= INICIANDO CALIBRAÇÃO 06/03 =======")

    # Parâmetros base
    base_params_path = "backend/v22_locked_params.json"
    with open(base_params_path, "r", encoding="utf-8") as f:
        base_data = json.load(f)

    data_file = "data/sota_training/training_WIN$_MASTER.csv"
    df = pd.read_csv(data_file)
    df["time"] = pd.to_datetime(df["time"])
    day_df = df[
        (df["time"] >= "2026-03-06 09:15:00") & (df["time"] <= "2026-03-06 17:15:00")
    ].copy()

    temp_csv = "data/sota_training/temp_calib.csv"
    day_df.to_csv(temp_csv, index=False)

    results = []

    # Grid Search simplificado para o dia 06/03
    tps = [300.0, 450.0, 600.0]
    confidences = [0.65, 0.70, 0.75]
    rsi_periods = [7, 9, 14]

    print(f"Testando {len(tps) * len(confidences) * len(rsi_periods)} combinações...")

    for tp in tps:
        for conf in confidences:
            for rsi in rsi_periods:
                p = base_data["strategy_params"].copy()
                p["tp_dist"] = tp
                p["confidence_threshold"] = conf
                p["rsi_period"] = rsi

                bt = BacktestPro(symbol="WIN$", data_file=temp_csv, **p)
                await bt.run()

                profit = bt.balance - 500.0
                win_rate = 0
                if len(bt.trades) > 0:
                    win_rate = len([t for t in bt.trades if t["pnl_fin"] > 0]) / len(
                        bt.trades
                    )

                results.append(
                    {
                        "tp": tp,
                        "conf": conf,
                        "rsi": rsi,
                        "profit": profit,
                        "trades": len(bt.trades),
                        "win_rate": win_rate,
                    }
                )
                # print(f"TP:{tp} Conf:{conf} RSI:{rsi} | Prof: {profit:.2f} Trades: {len(bt.trades)}")

    # Encontrar melhor resultado
    best = max(results, key=lambda x: (x["profit"], x["win_rate"]))

    print("\n======= MELHOR CALIBRAÇÃO ENCONTRADA =======")
    print(json.dumps(best, indent=2))

    if os.path.exists(temp_csv):
        os.remove(temp_csv)


if __name__ == "__main__":
    asyncio.run(calibrar())
