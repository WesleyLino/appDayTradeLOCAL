import asyncio
import MetaTrader5 as mt5
from datetime import datetime
from backend.mt5_bridge import MT5Bridge


async def debug():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ MT5 Off")
        return

    symbol = "WIN$"
    date_from = datetime(2026, 2, 26, 9, 0)
    date_to = datetime(2026, 2, 26, 12, 0)

    print(f"🎬 Coletando dados de {symbol} para {date_from}...")
    df = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, date_from, date_to)

    if df is None or df.empty:
        print("❌ Sem dados")
        return

    print(f"✅ {len(df)} candles coletados.")

    # Cálculos Reais (Sincronizados com BacktestPro)
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).ewm(span=9, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=9, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    df["sma_20"] = df["close"].rolling(20).mean()
    df["std_20"] = df["close"].rolling(20).std()
    df["upper"] = df["sma_20"] + 2.0 * df["std_20"]
    df["lower"] = df["sma_20"] - 2.0 * df["std_20"]
    df["vol_sma"] = df["tick_volume"].rolling(20).mean()

    # Amostra de momentos de "quase trade" (Preço fora das bandas)
    candidatos = df[(df["close"] < df["lower"]) | (df["close"] > df["upper"])]
    print(f"🔍 Candles fora das Bandas: {len(candidatos)}")

    if len(candidatos) > 0:
        print("\nExemplo de candidatos técnicos (Preço vs Bandas vs RSI):")
        print(candidatos[["close", "lower", "upper", "rsi", "tick_volume"]].tail(10))

        # Filtro final
        final = candidatos[(candidatos["rsi"] < 30) | (candidatos["rsi"] > 70)]
        print(f"\n🎯 Candles que também atendem RSI: {len(final)}")
        if len(final) > 0:
            print(final[["close", "rsi", "tick_volume"]].tail(5))

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(debug())
