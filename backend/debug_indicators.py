import pandas as pd
import sys
import os

# Adiciona o diretório atual ao path para importar os módulos locais
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro


def debug_indicators():
    print("🔬 [DEBUG-INDICATORS] Carregando dados do cache para inspeção...")

    # Busca um arquivo CSV de exemplo gerado pelo validador
    files = [
        f for f in os.listdir(".") if f.startswith("temp_multi_") and f.endswith(".csv")
    ]
    if not files:
        print("❌ Nenhum arquivo temp_multi_ encontrado. Rode o validador primeiro.")
        return

    filepath = files[0]
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)

    bt = BacktestPro("WIN$")
    bt.opt_params = {
        "bb_dev": 2.0,
        "rsi_period": 9,
        "rsi_buy_level": 32,
        "rsi_sell_level": 68,
        "vol_spike_mult": 0.8,
        "confidence_threshold": 0.75,
        "sl_dist": 250,
        "tp_dist": 150,
        "base_lot": 1,
        "start_time": "09:00",
        "end_time": "17:30",
        "use_ai_core": True,
    }

    print(f"📊 Processando {len(df)} candles de {filepath}...")
    bt.data = df.copy()
    bt._calculate_indicators()

    # Analisar o DataFrame resultante
    cols = [
        "close",
        "rsi",
        "sma_20",
        "upper_bb",
        "lower_bb",
        "atr_current",
        "vol_sma",
        "tick_volume",
    ]
    sample = bt.data[cols].head(200)

    # Verificar se as condições v22_buy_raw seriam verdadeiras em algum momento
    bt.data["cond_rsi_buy"] = bt.data["rsi"] < 32
    bt.data["cond_bb_buy"] = bt.data["close"] < bt.data["lower_bb"]
    bt.data["cond_vol_buy"] = bt.data["tick_volume"] > (bt.data["vol_sma"] * 0.8)
    bt.data["v22_buy_raw"] = (
        bt.data["cond_rsi_buy"] & bt.data["cond_bb_buy"] & bt.data["cond_vol_buy"]
    )

    hits = bt.data[bt.data["v22_buy_raw"]]

    print(
        f"\n📈 [RESULTADO] Encontrados {len(hits)} candidatos a BUY em {len(bt.data)} velas."
    )

    if len(hits) > 0:
        print("\nExemplo de Hit:")
        print(hits[cols].head())
    else:
        print("\n❌ NENHUM HIT - Analisando faixas de valores:")
        print(
            f"RSI: Min={bt.data['rsi'].min():.2f}, Max={bt.data['rsi'].max():.2f}, Avg={bt.data['rsi'].mean():.2f}"
        )
        print(
            f"Distancia Close-BB_Lower: min={(bt.data['close'] - bt.data['lower_bb']).min():.2f}"
        )
        print(
            f"Volume Ratio: max={(bt.data['tick_volume'] / bt.data['vol_sma']).max():.2f}"
        )

    sample.to_csv("debug_indicators_output.csv")
    print("\n✅ Report de 200 velas salvo em debug_indicators_output.csv")


if __name__ == "__main__":
    debug_indicators()
