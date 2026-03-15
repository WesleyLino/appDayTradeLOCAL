import sys
import os

sys.path.append(os.getcwd())
from backend.mt5_bridge import MT5Bridge


def diagnose():
    bridge = MT5Bridge()
    bridge.connect()  # Garante conexão
    symbol = "WIN$"
    df = bridge.get_market_data(symbol, n_candles=50)

    if df.empty:
        print("ERRO: MT5 não retornou dados para " + symbol)
        return

    # Calcula RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # Volume SMA
    df["vol_sma"] = df["tick_volume"].rolling(20).mean()

    last_rows = df.tail(5)
    print("\n--- ÚLTIMOS 5 MINUTOS (M1) ---")
    for i, row in last_rows.iterrows():
        print(
            f"Hora: {row.name} | Close: {row['close']} | RSI: {row['rsi']:.2f} | Vol: {row['tick_volume']} | SMA Vol: {row['vol_sma']:.1f}"
        )

    last = df.iloc[-1]
    setup_buy = last["rsi"] < 30
    setup_sell = last["rsi"] > 70
    vol_ok = last["tick_volume"] > (last["vol_sma"] * 1.0)

    print("\nStatus Atual:")
    print(f"- Gatilho Compra (RSI < 30): {setup_buy}")
    print(f"- Gatilho Venda (RSI > 70): {setup_sell}")
    print(f"- Volume > Média: {vol_ok}")


if __name__ == "__main__":
    diagnose()
