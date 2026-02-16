import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
from datetime import datetime

class DataCollector:
    def __init__(self, symbol):
        self.symbol = symbol

    def get_h1_history(self, n_candles=1000):
        """Coleta histórico de candles M1 para treinamento/ajuste."""
        if not mt5.initialize():
            logging.error("Falha ao inicializar MT5 no coletor.")
            return None

        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, n_candles)
        if rates is None or len(rates) == 0:
            logging.error(f"Não foi possível obter dados para {self.symbol}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def apply_zscore(self, df, window=60):
        """Aplica normalização Z-Score usando janela deslizante (evita look-ahead bias)."""
        # Focamos no preço de fechamento para a normalização
        df['close_mean'] = df['close'].rolling(window=window).mean()
        df['close_std'] = df['close'].rolling(window=window).std()
        
        # Z-Score = (x - mean) / std
        df['zscore'] = (df['close'] - df['close_mean']) / df['close_std']
        
        # Limpar NaNs resultantes da janela inicial
        return df.dropna(subset=['zscore'])

if __name__ == "__main__":
    # Teste rápido
    logging.basicConfig(level=logging.INFO)
    collector = DataCollector("WIN$") # Use o símbolo genérico se preferir
    data = collector.get_h1_history(200)
    if data is not None:
        normalized = collector.apply_zscore(data)
        print(normalized[['time', 'close', 'zscore']].tail())
