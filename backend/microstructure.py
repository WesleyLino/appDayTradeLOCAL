import pandas as pd
import numpy as np
import logging
import MetaTrader5 as mt5

class MicrostructureAnalyzer:
    def __init__(self):
        self.last_cvd = 0.0

    def calculate_cvd(self, ticks_df):
        """
        Calcula o Cumulative Volume Delta (CVD) a partir de um DataFrame de ticks.
        Retorna o valor final do CVD e a tendência (inclinação).
        """
        if ticks_df is None or ticks_df.empty:
            return 0.0

        # Identificar agressão
        # TICK_FLAG_BUY = 32 (ou verifique constante MT5)
        # TICK_FLAG_SELL = 64
        # Mas vamos usar as constantes do módulo mt5 se disponíveis, ou hardcoded se necessário.
        # No MT5 Python, flags é um bitmask.
        
        # Agressão de Compra: (flags & mt5.TICK_FLAG_BUY) == mt5.TICK_FLAG_BUY
        # Agressão de Venda: (flags & mt5.TICK_FLAG_SELL) == mt5.TICK_FLAG_SELL
        
        # Vetorização para performance
        flags = ticks_df['flags'].values
        volumes = ticks_df['volume_real'].values # Ou 'volume' se for B3 sem volume real, mas B3 tem.

        buy_aggressions = (flags & mt5.TICK_FLAG_BUY) == mt5.TICK_FLAG_BUY
        sell_aggressions = (flags & mt5.TICK_FLAG_SELL) == mt5.TICK_FLAG_SELL
        
        buy_vol = np.where(buy_aggressions, volumes, 0).sum()
        sell_vol = np.where(sell_aggressions, volumes, 0).sum()
        
        current_cvd = buy_vol - sell_vol
        
        # Simples oscilador de CVD: CVD vs Média móvel dele (não temos histórico aqui, então retornamos o raw)
        # Para tendência, ideal seria ter série temporal.
        # Aqui vamos retornar o NET FLOW (Saldo de Agressão) deste batch de ticks.
        
        return current_cvd

    def detect_divergence(self, price_arr, cvd_arr):
        """
        Detecta divergência entre Preço e CVD (Absorção).
        Ex: Preço caindo (Lower Lows) mas CVD subindo (Higher Lows) -> Absorção de Venda (Bullish).
        """
        # Complexidade de HFT: Requer janela de tempo.
        # Placeholder para v2.0
        pass

    def evaluate_pressure(self, net_flow, threshold=500):
        """
        Avalia a pressão do fluxo.
        WIN: Threshold ~500-1000 contratos de saldo é relevante.
        WDO: Threshold ~50-100 contratos de saldo é relevante.
        """
        if net_flow > threshold:
            return 1 # Pressão de Compra
        elif net_flow < -threshold:
            return -1 # Pressão de Venda
        return 0
