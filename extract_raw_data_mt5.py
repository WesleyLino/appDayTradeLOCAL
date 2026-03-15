import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import os

# Script de Coleta HFT Seguro (Sem Dependências Internas da App)


def extract_from_mt5(symbol="WIN$", date_str="2026-03-10"):
    """Conecta no MT5 Terminal, puxa H1, M1 e Ticks Reais para a data."""
    print(f"Iniciando Extração Segura de Dados: {symbol} em {date_str}")

    if not mt5.initialize():
        print("Erro: Falha ao inicializar o MetaTrader 5.")
        return False

    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        print(f"Erro: Símbolo {symbol} não encontrado.")
        mt5.shutdown()
        return False

    # Datas de Limite
    dt_target_start = datetime.strptime(f"{date_str} 08:50:00", "%Y-%m-%d %H:%M:%S")
    dt_target_end = datetime.strptime(f"{date_str} 18:30:00", "%Y-%m-%d %H:%M:%S")

    os.makedirs("data", exist_ok=True)

    # 1. Puxar M1 Data (Preços Base)
    print("1. Extraindo Candles M1...")
    rates_m1 = mt5.copy_rates_range(
        symbol, mt5.TIMEFRAME_M1, dt_target_start, dt_target_end
    )
    if rates_m1 is not None and len(rates_m1) > 0:
        df_m1 = pd.DataFrame(rates_m1)
        df_m1["time"] = pd.to_datetime(df_m1["time"], unit="s")
        file_m1 = f"data/audit_m1_{date_str.replace('-', '')}.csv"
        df_m1.to_csv(file_m1, index=False)
        print(f" - Salvo: {file_m1} ({len(df_m1)} candles)")
    else:
        print(" - Falha ao extrair M1.")

    # 2. Puxar Ticks Reais (L2 Depth Flow Estimable)
    print("2. Extraindo Real Ticks...")
    ticks = mt5.copy_ticks_range(
        symbol, dt_target_start, dt_target_end, mt5.COPY_TICKS_ALL
    )
    if ticks is not None and len(ticks) > 0:
        df_ticks = pd.DataFrame(ticks)
        df_ticks["time"] = pd.to_datetime(df_ticks["time"], unit="s")
        file_ticks = f"data/audit_ticks_{date_str.replace('-', '')}.csv"
        df_ticks.to_csv(file_ticks, index=False)
        print(f" - Salvo: {file_ticks} ({len(df_ticks)} ticks)")
    else:
        print(" - Falha ao extrair Ticks.")

    mt5.shutdown()
    print("Extração finalizada com Sucesso!")
    return True


if __name__ == "__main__":
    import datetime as dt

    # Hoje
    extract_from_mt5("WIN$", dt.datetime.now().strftime("%Y-%m-%d"))
