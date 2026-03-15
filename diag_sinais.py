"""Diagnostico de sinais tecnicos de VENDA nos dados historicos do MT5."""

import sys
import warnings
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

try:
    import MetaTrader5 as mt5
    from datetime import datetime

    dias = [
        ("19/02", datetime(2026, 2, 19, 9, 0), datetime(2026, 2, 19, 17, 30)),
        ("23/02", datetime(2026, 2, 23, 9, 0), datetime(2026, 2, 23, 17, 30)),
        ("24/02", datetime(2026, 2, 24, 9, 0), datetime(2026, 2, 24, 17, 30)),
        ("25/02", datetime(2026, 2, 25, 9, 0), datetime(2026, 2, 25, 17, 30)),
        ("26/02", datetime(2026, 2, 26, 9, 0), datetime(2026, 2, 26, 17, 30)),
        ("27/02", datetime(2026, 2, 27, 9, 0), datetime(2026, 2, 27, 17, 30)),
    ]

    mt5.initialize()

    total_sell = 0
    total_buy = 0

    for label, d_from, d_to in dias:
        rates = mt5.copy_rates_range("WIN$", mt5.TIMEFRAME_M1, d_from, d_to)
        if rates is None or len(rates) == 0:
            print(f"[{label}] Sem dados")
            continue

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)

        # Indicadores
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=14, adjust=False).mean()
        df["rsi"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
        df["sma_20"] = df["close"].rolling(20).mean()
        df["std_20"] = df["close"].rolling(20).std()
        df["upper_bb"] = df["sma_20"] + 2.0 * df["std_20"]
        df["lower_bb"] = df["sma_20"] - 2.0 * df["std_20"]
        df["vol_sma"] = df["tick_volume"].rolling(20).mean()

        # Gatilhos
        sell_raw = (
            (df["rsi"] > 70)
            & (df["close"] > df["upper_bb"])
            & (df["tick_volume"] > df["vol_sma"] * 0.8)
        )
        buy_raw = (
            (df["rsi"] < 30)
            & (df["close"] < df["lower_bb"])
            & (df["tick_volume"] > df["vol_sma"] * 0.8)
        )

        n_sell = sell_raw.sum()
        n_buy = buy_raw.sum()
        total_sell += n_sell
        total_buy += n_buy

        rsi_max = df["rsi"].max()
        rsi_min = df["rsi"].min()

        print(
            f"[{label}] VENDA_RAW={n_sell} | COMPRA_RAW={n_buy} | RSI max={rsi_max:.1f} min={rsi_min:.1f} | Candles={len(df)}"
        )

    mt5.shutdown()
    print()
    print(f"TOTAL: VENDA_RAW={total_sell} | COMPRA_RAW={total_buy} em 6 dias")

except Exception as e:
    import traceback

    print(f"ERRO: {e}")
    traceback.print_exc()
