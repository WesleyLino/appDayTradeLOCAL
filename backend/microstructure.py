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

    def calculate_synthetic_index(self, bluechips_data: dict) -> float:
        """
        Calcula um Índice Sintético ponderado baseado nas Blue Chips.
        Retorna um valor float que representa a 'força' do IBOV subjacente.
        Valores > 0.5 indicam força compradora nas ações.
        Valores < -0.5 indicam força vendedora nas ações.
        """
        if not bluechips_data:
            return 0.0
            
        # Pesos aproximados (simplificados para Day Trade)
        weights = {
            "VALE3": 0.14, # Plano Mestre 2.0
            "PETR4": 0.12, # Plano Mestre 2.0
            "ITUB4": 0.10,
            "BBDC4": 0.10,
            "ELET3": 0.05
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for ticker, variation in bluechips_data.items():
            weight = weights.get(ticker, 0.05)
            weighted_sum += variation * weight
            total_weight += weight
            
        if total_weight == 0:
            return 0.0
            
        synthetic_index = weighted_sum / total_weight
        return synthetic_index

    def detect_divergence(self, price_arr, cvd_arr):
        """
        Detecta divergência entre Preço e CVD (Absorção).
        Retorna:
        1.0: Bullish Divergence (Preço Cai/Lateral, CVD Sobe) - Absorção Venda
        -1.0: Bearish Divergence (Preço Sobe/Lateral, CVD Cai) - Absorção Compra
        0.0: Convergência (Normal)
        """
        if len(price_arr) < 10 or len(cvd_arr) < 10:
            return 0.0

        # Normalização simples (Slope)
        try:
            # Inclinação do Preço (últimos n pontos)
            x = np.arange(len(price_arr))
            # slope_price, _, _, _, _ = stats.linregress(x, price_arr) 
            slope_price = np.polyfit(x, price_arr, 1)[0]
            
            # Inclinação do CVD
            # slope_cvd, _, _, _, _ = stats.linregress(x, cvd_arr)
            slope_cvd = np.polyfit(x, cvd_arr, 1)[0]
            
            # Limiares de inclinação (ajustar conforme ativo)
            # Divergência de Alta: Preço caindo/flat, CVD subindo forte
            if slope_price <= 0 and slope_cvd > 5: # CVD subindo forte
                return 1.0
                
            # Divergência de Baixa: Preço subindo/flat, CVD caindo forte
            if slope_price >= 0 and slope_cvd < -5:
                return -1.0
                
            return 0.0
        except Exception as e:
            # logging.error(f"Erro Divergencia: {e}") # Opcional
            return 0.0

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
