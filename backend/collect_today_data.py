import MetaTrader5 as mt5
import pandas as pd
import os
from datetime import datetime
import logging
from backend.data_labeler import apply_triple_barrier_method

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def collect_today():
    if not mt5.initialize():
        logging.error("Falha ao inicializar MT5")
        return

    symbols = ["WIN$", "WDO$", "VALE3", "PETR4", "ITUB4"]
    dataset_dir = "data/sota_training"

    # Hoje
    now = datetime.now()
    start_date = datetime(now.year, now.month, now.day)
    end_date = now

    for symbol in symbols:
        logging.info(f"--- Coletando dados de hoje para {symbol} ---")

        # 1. Candles M1
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_date, end_date)
        if rates is None or len(rates) == 0:
            logging.warning(f"Nenhum dado para {symbol} hoje.")
            continue

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")

        # 2. Ticks para os principais (para calcular CVD/OFI se possível)
        df_ticks = None
        if symbol in ["WIN$", "WDO$"]:
            ticks = mt5.copy_ticks_range(
                symbol, start_date, end_date, mt5.COPY_TICKS_ALL
            )
            if ticks is not None and len(ticks) > 0:
                df_ticks = pd.DataFrame(ticks)
                df_ticks["time"] = pd.to_datetime(df_ticks["time"], unit="s")

        # 3. Processamento Microestrutura (Heurística ou Tick-based)
        if df_ticks is not None and not df_ticks.empty and "flags" in df_ticks.columns:
            df_ticks["time_1m"] = df_ticks["time"].dt.floor("1min")
            df_ticks["buy_vol"] = df_ticks["volume"].where(
                (df_ticks["flags"] & 32) > 0, 0
            )
            df_ticks["sell_vol"] = df_ticks["volume"].where(
                (df_ticks["flags"] & 64) > 0, 0
            )
            agg = (
                df_ticks.groupby("time_1m")
                .agg(buy_vol=("buy_vol", "sum"), sell_vol=("sell_vol", "sum"))
                .reset_index()
            )
            agg["cvd"] = agg["buy_vol"] - agg["sell_vol"]
            agg["ofi"] = (agg["buy_vol"] - agg["sell_vol"]) / (
                agg["buy_vol"] + agg["sell_vol"] + 1e-8
            )
            agg["volume_ratio"] = agg["buy_vol"] / (agg["sell_vol"] + 1e-8)
            agg = agg.rename(columns={"time_1m": "time"})
            df = df.merge(
                agg[["time", "cvd", "ofi", "volume_ratio"]], on="time", how="left"
            )
        else:
            body = df["close"] - df["open"]
            df["cvd"] = df["real_volume"] * body.apply(
                lambda x: 1 if x > 0 else -1 if x < 0 else 0
            )
            df["ofi"] = body / (df["high"] - df["low"] + 1e-8)
            df["volume_ratio"] = df["real_volume"] / (
                df["real_volume"].rolling(20).mean() + 1e-8
            )

        # Preencher NaNs
        for col in ["cvd", "ofi", "volume_ratio"]:
            if col in df.columns:
                df[col] = df[col].fillna(0.0)

        # 4. Rotulagem SOTA
        try:
            df_labeled = apply_triple_barrier_method(df)
        except:
            df_labeled = df

        if "symbol" not in df_labeled.columns:
            df_labeled["symbol"] = symbol

        # 5. Salvar/Anexar
        filename = f"{dataset_dir}/training_{symbol}_MASTER.csv"
        file_exists = os.path.isfile(filename)

        # Evitar duplicatas removendo o que já existe de hoje se houver
        if file_exists:
            existing_df = pd.read_csv(filename)
            existing_df["time"] = pd.to_datetime(existing_df["time"])
            df_labeled["time"] = pd.to_datetime(df_labeled["time"])

            # Manter apenas dados que NÃO são de hoje ou que são novos de hoje
            mask = ~existing_df["time"].dt.date.isin([start_date.date()])
            existing_df = existing_df[mask]

            final_df = pd.concat([existing_df, df_labeled], ignore_index=True)
            final_df.to_csv(filename, index=False)
        else:
            df_labeled.to_csv(filename, index=False)

        logging.info(
            f"✅ Dados de hoje consolidados para {symbol}: {len(df_labeled)} linhas."
        )

    mt5.shutdown()
    logging.info("🚀 Coleta de dados de hoje finalizada.")


if __name__ == "__main__":
    collect_today()
