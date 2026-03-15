import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def trace_signals():
    params_path = "backend/v22_locked_params.json"
    with open(params_path, "r") as f:
        config = json.load(f)
        strategy_params = config.get("strategy_params", {})

    target_date = "2026-03-06"
    bt = BacktestPro(
        symbol="WIN$", n_candles=2500, initial_balance=3000.0, **strategy_params
    )
    df_full = await bt.load_data()
    df = df_full[df_full.index.strftime("%Y-%m-%d") == target_date].copy()

    # Rodar os indicadores
    bt.data = df

    print(f"Analisando {len(df)} candles de {target_date}...")

    # RSI, BB, etc
    rsi_p = strategy_params["rsi_period"]
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=rsi_p, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))
    bb_d = strategy_params["bb_dev"]
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["std_20"] = df["close"].rolling(window=20).std()
    df["upper_bb"] = df["sma_20"] + bb_d * df["std_20"]
    df["lower_bb"] = df["sma_20"] - bb_d * df["std_20"]
    df["vol_sma"] = df["tick_volume"].rolling(window=20).mean()

    signals = []
    v_mult = strategy_params.get("vol_spike_mult", 0.8)

    for i in range(20, len(df)):
        row = df.iloc[i]

        # Candidate definition (loose)
        is_candidate_buy = row["rsi"] < 32 and row["close"] < row["lower_bb"]
        is_candidate_sell = row["rsi"] > 68 and row["close"] > row["upper_bb"]

        if is_candidate_buy or is_candidate_sell:
            side = "buy" if is_candidate_buy else "sell"
            entry = row["close"]
            sl = entry - 150 if side == "buy" else entry + 150
            tp = entry + 450 if side == "buy" else entry - 450

            outcome = "STILL_OPEN"
            exit_price = entry
            for j in range(i + 1, min(i + 61, len(df))):
                f_row = df.iloc[j]
                if side == "buy":
                    if f_row["low"] <= sl:
                        outcome = "STOP"
                        exit_price = sl
                        break
                    if f_row["high"] >= tp:
                        outcome = "TAKE"
                        exit_price = tp
                        break
                else:
                    if f_row["high"] >= sl:
                        outcome = "STOP"
                        exit_price = sl
                        break
                    if f_row["low"] <= tp:
                        outcome = "TAKE"
                        exit_price = tp
                        break

            signals.append(
                {
                    "time": row.name.strftime("%H:%M"),
                    "side": side,
                    "outcome": outcome,
                    "rsi": row["rsi"],
                    "pnl": round(
                        (exit_price - entry) * 0.2
                        if side == "buy"
                        else (entry - exit_price) * 0.2,
                        2,
                    ),
                }
            )

    print(f"\n🔍 RASTREIO DE CANAIS TÉCNICOS (BRUTO): Encontrados {len(signals)}")
    with open("backend/trace_06mar_results.json", "w") as f:
        json.dump(signals, f, indent=2)
    print("✅ Resultados salvos em backend/trace_06mar_results.json")


if __name__ == "__main__":
    asyncio.run(trace_signals())
