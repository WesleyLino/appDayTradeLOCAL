import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import os


def collect_data(date_str, filename):
    if not mt5.initialize():
        print("❌ Falha ao inicializar MT5")
        return False

    date_dt = datetime.strptime(date_str, "%d/%m/%Y")
    start_time = datetime(date_dt.year, date_dt.month, date_dt.day, 9, 0)
    end_time = datetime(date_dt.year, date_dt.month, date_dt.day, 18, 0)

    print(f"📥 Coletando {date_str} (WIN$)...")
    rates = mt5.copy_rates_range("WIN$", mt5.TIMEFRAME_M1, start_time, end_time)

    if rates is None or len(rates) == 0:
        print(f"❌ Nenhum dado encontrado para {date_str}")
        return False

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.to_csv(filename, index=False)
    print(f"✅ Salvo em {filename} ({len(df)} candles)")
    return True


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    collect_data("27/02/2026", "data/audit_m1_20260227.csv")
    mt5.shutdown()
