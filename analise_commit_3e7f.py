import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
import numpy as np

# Configuração Padrão
SYMBOL_CONTINUO = "WIN$"
SYMBOL_CONTRAT = "WINJ25"
TIMEFRAME = mt5.TIMEFRAME_M1
CAPITAL = 3000.0

# CARREGAR OS PARAMENTROS FIXADOS NO COMMIT 3e7f96c9
PARAMS_ANTIGOS = {
    "rsi_period": 7,
    "bb_dev": 2.0,
    "vol_spike_mult": 0.8,  # Era bem mais baixo que o 1.5 de hoje
    "use_flux_filter": True,
    "flux_imbalance_threshold": 0.95,
    "sl_dist": 150.0,
    "tp_dist": 450.0,
    "adx_min_threshold": 20.0,
    # ATENÇÃO: ATR Volatility Trigger existia (120), mas NÃO HAVIA min_atr_threshold (50) para cortar ruido
    "atr_volatility_trigger": 120.0,
    "bollinger_squeeze_threshold": 1.2,
    "rsi_sell_level": 65,
}


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


def simular_dia(data_foco, label_dia):
    timezone_offset = timedelta(hours=3)
    start_time = datetime(2026, 3, data_foco, 9, 0) + timezone_offset
    end_time = datetime(2026, 3, data_foco, 18, 0) + timezone_offset

    rates = mt5.copy_rates_range(SYMBOL_CONTRAT, TIMEFRAME, start_time, end_time)
    if rates is None or len(rates) == 0:
        rates = mt5.copy_rates_range(SYMBOL_CONTINUO, TIMEFRAME, start_time, end_time)

    df = pd.DataFrame(rates)
    if df.empty:
        return

    df["time"] = pd.to_datetime(df["time"], unit="s") - timezone_offset
    df["rsi"] = calculate_rsi(df["close"], period=PARAMS_ANTIGOS["rsi_period"])
    df["vol_sma"] = df["real_volume"].rolling(20).mean()
    df["atr"] = calculate_atr(df, period=14)

    tp_pts = PARAMS_ANTIGOS["tp_dist"]
    sl_pts = -PARAMS_ANTIGOS["sl_dist"]
    vol_mult = PARAMS_ANTIGOS["vol_spike_mult"]

    trades = []
    pos_open = None

    for i in range(25, len(df)):
        current = df.iloc[i]
        c_time = current["time"].time()

        if c_time < time(9, 15) or c_time >= time(17, 15):
            if pos_open:
                pnl = (
                    current["close"] - pos_open["price"]
                    if pos_open["type"] == "BUY"
                    else pos_open["price"] - current["close"]
                )
                pos_open["pnl"] = pnl
                trades.append(pos_open)
                pos_open = None
            continue

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

            if min_pnl_pts <= sl_pts:
                pos_open["pnl"] = sl_pts
                trades.append(pos_open)
                pos_open = None
            elif max_pnl_pts >= tp_pts:
                pos_open["pnl"] = tp_pts
                trades.append(pos_open)
                pos_open = None
        else:
            vol_condition = current["real_volume"] > (current["vol_sma"] * vol_mult)
            # NOTA: O commit antigo NÃO TINHA ATR MINIMO. Então operava todo tipo de lixo se volume picasse.

            if vol_condition:
                if current["rsi"] <= 30:
                    pos_open = {
                        "type": "BUY",
                        "price": current["close"],
                        "time": str(c_time),
                    }
                elif current["rsi"] >= 70:
                    pos_open = {
                        "type": "SELL",
                        "price": current["close"],
                        "time": str(c_time),
                    }

    # Analise
    lucro_total = sum(t["pnl"] * 0.2 for t in trades)
    print(f"\n--- [ANÁLISE DO COMMIT ANTIGO (3e7f) - Dia {label_dia}/03] ---")
    print(f"Total de Trades: {len(trades)}")
    print(f"Saldo Gerado: R$ {lucro_total:.2f}")

    loss_count = sum(1 for t in trades if t["pnl"] <= sl_pts)
    win_count = len(trades) - loss_count
    print(f"Win/Loss bruto (Sem Break-Even): {win_count}x{loss_count}")
    return lucro_total


def run_all():
    if not mt5.initialize():
        return
    print("====== LABORATÓRIO DE COMMIT ANTIGO (3e7f96c9) ======")
    print("Testando o comportamento daquele código num ambiente díficil.")
    l9 = simular_dia(9, "09")
    l10 = simular_dia(10, "10")
    print("\n[VEREDITO MATEMÁTICO]")
    print(f"Saldo Somado (09/03 e 10/03): R$ {(l9 + l10):.2f}")
    mt5.shutdown()


if __name__ == "__main__":
    run_all()
