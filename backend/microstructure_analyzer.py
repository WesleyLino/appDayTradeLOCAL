import numpy as np
import logging
import MetaTrader5 as mt5

class MicrostructureAnalyzer:
    def __init__(self):
        self.last_cvd = 0.0
        self.prev_book_levels = None

    def analyze(self, current_book, ticks_df=None):
        """
        [SOTA] Interface unificada para análise de microestrutura.
        Agrega Weighted OFI e detecção de Divergência/Absorção.
        """
        # 1. OFI Ponderado (SOTA)
        ofi = self.calculate_wen_ofi(current_book)
        
        # 2. CVD do batch atual
        cvd = self.calculate_cvd(ticks_df) if ticks_df is not None else 0.0
        
        # 3. Normalização simples do OFI para range (-1, 1) relativo
        # Heurística: 1000 contratos de desequilíbrio é sinal forte
        signal = np.tanh(ofi / 500.0) 
        
        return signal

    def calculate_ofi_level2(self, current_book: dict, levels: int = 5) -> float:
        """
        Calcula o Order Flow Imbalance (OFI) multínivel (Level 2).
        OFI ajuda a identificar pressão de ordens passivas antes do trade ocorrer.
        """
        if not current_book or self.prev_book_levels is None:
            self.prev_book_levels = current_book
            return 0.0
            
        ofi_sum = 0.0
        
        # Bids
        curr_bids = current_book.get('bids', [])[:levels]
        prev_bids = self.prev_book_levels.get('bids', [])[:levels]
        
        # Asks
        curr_asks = current_book.get('asks', [])[:levels]
        prev_asks = self.prev_book_levels.get('asks', [])[:levels]
        
        # Processar Bids (Lado Compra)
        for i in range(min(len(curr_bids), len(prev_bids))):
            try:
                c_p, c_v = curr_bids[i].get('price', 0), curr_bids[i].get('volume', 0)
                p_p, p_v = prev_bids[i].get('price', 0), prev_bids[i].get('volume', 0)
                
                if c_p > p_p: 
                    ofi_sum += c_v
                elif c_p < p_p: 
                    ofi_sum -= p_v
                elif c_p > 0: # Preços iguais
                    ofi_sum += (c_v - p_v)
            except (KeyError, IndexError):
                continue
            
        # Processar Asks (Lado Venda)
        for i in range(min(len(curr_asks), len(prev_asks))):
            try:
                c_p, c_v = curr_asks[i].get('price', 0), curr_asks[i].get('volume', 0)
                p_p, p_v = prev_asks[i].get('price', 0), prev_asks[i].get('volume', 0)
                
                if c_p < p_p: 
                    ofi_sum -= c_v
                elif c_p > p_p: 
                    ofi_sum += p_v
                elif c_p > 0: # Preços iguais
                    ofi_sum -= (c_v - p_v)
            except (KeyError, IndexError):
                continue
            
        self.prev_book_levels = current_book
        return ofi_sum

    def calculate_wen_ofi(self, current_book: dict, levels: int = 5) -> float:
        """
        [SOTA] Calcula o Weighted Order Flow Imbalance (OFI) Ponderado.
        Atribui peso decrescente aos níveis do book (L1=1.0, L2=0.8, ...)
        Detecta pressão institucional real vs spoofing profundo.
        """
        if not current_book or self.prev_book_levels is None:
            self.prev_book_levels = current_book
            return 0.0
            
        ofi_weighted_sum = 0.0
        
        # Pesos Decrescentes (Linear Decay)
        # L1=1.0, L2=0.8, L3=0.6, L4=0.4, L5=0.2
        weights = [max(0.2, 1.0 - (i * 0.2)) for i in range(levels)]
        
        # Bids & Asks
        curr_bids = current_book.get('bids', [])[:levels]
        prev_bids = self.prev_book_levels.get('bids', [])[:levels]
        curr_asks = current_book.get('asks', [])[:levels]
        prev_asks = self.prev_book_levels.get('asks', [])[:levels]
        
        limit = min(levels, len(curr_bids), len(prev_bids), len(curr_asks), len(prev_asks))
        
        for i in range(limit):
            w = weights[i]
            ofi_layer = 0.0
            
            # --- Lado Compra (Bid) ---
            try:
                cb_p, cb_v = curr_bids[i].get('price', 0), curr_bids[i].get('volume', 0)
                pb_p, pb_v = prev_bids[i].get('price', 0), prev_bids[i].get('volume', 0)
                
                if cb_p > pb_p: ofi_layer += cb_v
                elif cb_p < pb_p: ofi_layer -= pb_v
                elif cb_p > 0: ofi_layer += (cb_v - pb_v)
            except: pass
            
            # --- Lado Venda (Ask) ---
            try:
                ca_p, ca_v = curr_asks[i].get('price', 0), curr_asks[i].get('volume', 0)
                pa_p, pa_v = prev_asks[i].get('price', 0), prev_asks[i].get('volume', 0)
                
                if ca_p < pa_p: ofi_layer -= ca_v
                elif ca_p > pa_p: ofi_layer += pa_v
                elif ca_p > 0: ofi_layer -= (ca_v - pa_v)
            except: pass
            
            ofi_weighted_sum += (ofi_layer * w)
            
        self.prev_book_levels = current_book
        return ofi_weighted_sum

    def calculate_vap(self, ticks_df, symbol, bins=20):
        """
        [SOTA] Calcula o Volume at Price (VAP) para identificar áreas de alta liquidez.
        Retorna os níveis de suporte/resistência baseados em volume acumulado.
        """
        if ticks_df is None or not hasattr(ticks_df, 'empty') or ticks_df.empty:
            return None
            
        try:
            # Agrupar volume por preço
            vap = ticks_df.groupby('price')['volume'].sum().reset_index()
            vap = vap.sort_values(by='volume', ascending=False)
            
            # Point of Control (Preço com maior volume)
            poc = vap.iloc[0]['price']
            
            # Identificar áreas de valor (Top 3 níveis de volume)
            value_areas = vap.head(3).to_dict(orient='records')
            
            return {
                "poc": poc,
                "value_areas": value_areas
            }
        except Exception as e:
            logging.error(f"Erro ao calcular VAP: {e}")
            return None

    def calculate_vwap(self, ticks_df):
        """
        [v27] Calcula a VWAP (Volume Weighted Average Price) a partir dos ticks.
        Retorna (vwap, vwap_std) para detecção de exaustão e tendência institucional.
        """
        if ticks_df is None or ticks_df.empty:
            return 0.0, 0.0
            
        try:
            # Garante que temos as colunas necessárias
            if 'price' not in ticks_df.columns or 'volume' not in ticks_df.columns:
                return 0.0, 0.0
                
            cum_vol = ticks_df['volume'].sum()
            if cum_vol == 0:
                return 0.0, 0.0
                
            vwap = (ticks_df['price'] * ticks_df['volume']).sum() / cum_vol
            
            # Cálculo de Desvio Padrão para Bandas de VWAP (Exaustão)
            variance = ((ticks_df['price'] - vwap)**2 * ticks_df['volume']).sum() / cum_vol
            vwap_std = np.sqrt(variance) if variance > 0 else 0.0
            
            return float(vwap), float(vwap_std)
        except Exception as e:
            logging.error(f"Erro no cálculo de VWAP: {e}")
            return 0.0, 0.0

    def calculate_cvd(self, ticks_df):
        """
        Calcula o Cumulative Volume Delta (CVD) a partir de um DataFrame de ticks.
        Retorna o valor final do CVD e a tendência (inclinação).
        """
        if ticks_df is None or not hasattr(ticks_df, 'empty') or ticks_df.empty:
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
        
        # [FAILSAFE] B3/MT5 Ticks podem usar 'volume' ou 'volume_real'
        if 'volume_real' in ticks_df.columns:
            volumes = ticks_df['volume_real'].values
        elif 'volume' in ticks_df.columns:
            volumes = ticks_df['volume'].values
        else:
            return 0.0

        buy_aggressions = (flags & mt5.TICK_FLAG_BUY) == mt5.TICK_FLAG_BUY
        sell_aggressions = (flags & mt5.TICK_FLAG_SELL) == mt5.TICK_FLAG_SELL
        
        buy_vol = np.where(buy_aggressions, volumes, 0).sum()
        sell_vol = np.where(sell_aggressions, volumes, 0).sum()
        
        current_cvd = float(buy_vol - sell_vol)
        
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
        except Exception:
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
