import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
import json
import numpy as np

# Configuração Padrão
SYMBOL_CONTINUO = "WIN$"
SYMBOL_CONTRAT = "WINJ25"
TIMEFRAME = mt5.TIMEFRAME_M1
PARAMS_FILE = "backend/v22_locked_params.json"  # Lendo os pesos reais que geram lucro
CAPITAL = 3000.0


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


def load_params():
    try:
        with open(PARAMS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("strategy_params", {})
    except Exception as e:
        print(f"Erro ao carregar parametros: {e}")
        return {}


def run_simulation():
    if not mt5.initialize():
        print("Falha ao inicializar MT5")
        return

    print(
        f"Analisando Dia 09/03 no {SYMBOL_CONTINUO} / {SYMBOL_CONTRAT} - Capital R$ {CAPITAL:.2f}"
    )

    # 1. Carregar Dados de 09/03 de um ano util (Testando 2025 e 2026)
    # Como hoje e 11/03/2026, o 09/03/2026 ja aconteceu (Segunda-Feira).
    timezone_offset = timedelta(hours=3)
    start_time = datetime(2026, 3, 9, 9, 0) + timezone_offset
    end_time = datetime(2026, 3, 9, 18, 0) + timezone_offset

    rates = mt5.copy_rates_range(SYMBOL_CONTRAT, TIMEFRAME, start_time, end_time)
    if rates is None or len(rates) == 0:
        print("Aviso: Testando simbolo continuo...")
        rates = mt5.copy_rates_range(SYMBOL_CONTINUO, TIMEFRAME, start_time, end_time)

    df = pd.DataFrame(rates)
    if not df.empty:
        df["time"] = pd.to_datetime(df["time"], unit="s") - timezone_offset
    else:
        print(
            "Sem dados para a data especificada. O MT5 precisa estar conectado e o ativo WING26 / WINJ26 liberado no market watch."
        )
        mt5.shutdown()
        return

    # 2. Carregar Ouro (SOTA Params)
    params = load_params()
    rsi_per = params.get("rsi_period", 7)
    vol_mult = params.get("vol_spike_mult", 1.5)
    atr_min = params.get("min_atr_threshold", 50.0)
    tp_pts = params.get("tp_dist", 150.0)
    sl_pts = -params.get("sl_dist", 150.0)
    be_trigger = 40.0  # Protecao Golden

    # Pre-calculos
    df["rsi"] = calculate_rsi(df["close"], period=rsi_per)
    df["vol_sma"] = df["real_volume"].rolling(20).mean()
    df["atr"] = calculate_atr(df, period=14)

    compras_realizadas = []
    vendas_realizadas = []
    oportunidades_perdidas = []
    pos_open = None

    # Trade loop
    for i in range(25, len(df)):
        current = df.iloc[i]
        c_time = current["time"].time()

        # Ignorar leilão inicial e final
        if c_time < time(9, 15) or c_time >= time(17, 15):
            if pos_open:
                pnl_pts = (
                    current["close"] - pos_open["price"]
                    if pos_open["type"] == "BUY"
                    else pos_open["price"] - current["close"]
                )
                pos_open["pnl_pts"] = pnl_pts
                pos_open["reason"] = "TIME_LIMIT"
                if pos_open["type"] == "BUY":
                    compras_realizadas.append(pos_open)
                else:
                    vendas_realizadas.append(pos_open)
                pos_open = None
            continue

        # Marcador de Oportunidades Perdidas
        if current["high"] - current["low"] > 150 and not pos_open:
            oportunidades_perdidas.append(
                {
                    "time": str(c_time),
                    "amplitude": current["high"] - current["low"],
                    "atr_momento": current["atr"],
                    "vol_vs_media": current["real_volume"] / current["vol_sma"]
                    if current["vol_sma"] > 0
                    else 0,
                    "motivo_rejeicao": "ATR abaixo de 50"
                    if current["atr"] < atr_min
                    else "RSI nao ativou",
                    "direcao": "ALTA"
                    if current["close"] > current["open"]
                    else "BAIXA",
                }
            )

        if pos_open:
            # Em operacao - Tracking de Maximos e Minimos (como o preco desenrolou no candle)
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

            # Dinamica Break-Even
            current_sl = sl_pts
            if pos_open["max_runup"] >= be_trigger or max_pnl_pts >= be_trigger:
                current_sl = 0

            # Stop Loss (ou BE)
            if min_pnl_pts <= current_sl:
                pos_open["pnl_pts"] = current_sl
                pos_open["reason"] = "BREAK_EVEN" if current_sl == 0 else "STOP_LOSS"
                if pos_open["type"] == "BUY":
                    compras_realizadas.append(pos_open)
                else:
                    vendas_realizadas.append(pos_open)
                pos_open = None
                continue

            # Take Profit
            if max_pnl_pts >= tp_pts:
                pos_open["pnl_pts"] = tp_pts
                pos_open["reason"] = "TAKE_PROFIT"
                if pos_open["type"] == "BUY":
                    compras_realizadas.append(pos_open)
                else:
                    vendas_realizadas.append(pos_open)
                pos_open = None
                continue

            # Atualiza RunUp
            if max_pnl_pts > pos_open["max_runup"]:
                pos_open["max_runup"] = max_pnl_pts

        else:
            # Buscar Entradas Válidas
            vol_condition = current["real_volume"] > (current["vol_sma"] * vol_mult)
            atr_condition = current["atr"] >= atr_min

            if vol_condition and atr_condition:
                if current["rsi"] <= 30:  # Compra
                    pos_open = {
                        "type": "BUY",
                        "price": current["close"],
                        "time": str(c_time),
                        "max_runup": 0,
                    }
                elif current["rsi"] >= 70:  # Venda
                    pos_open = {
                        "type": "SELL",
                        "price": current["close"],
                        "time": str(c_time),
                        "max_runup": 0,
                    }

    # Exportar resultados
    with open("results_buy_09.json", "w") as f:
        json.dump(compras_realizadas, f)
    with open("results_sell_09.json", "w") as f:
        json.dump(vendas_realizadas, f)
    with open("results_missed_09.json", "w") as f:
        json.dump(oportunidades_perdidas, f)

    print("BACKTEST 09/03 CONCLUIDO. Analise exportada.")
    mt5.shutdown()


if __name__ == "__main__":
    run_simulation()
