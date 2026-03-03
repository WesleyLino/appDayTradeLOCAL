import numpy as np
import logging
import MetaTrader5 as mt5

class MicrostructureAnalyzer:
    def __init__(self):
        self.last_cvd = 0.0
        self.prev_book_levels = None
        self.cvd_history = []
        self.price_history = []
        self.last_vwap = (0.0, 0.0) # (vwap, std)

    def analyze(self, current_book, ticks_df=None):
        """
        [HFT ELITE] Interface unificada para análise de microestrutura.
        Agrega OFI Ponderado, CVD, Divergência e Icebergs.
        """
        # 1. OFI Ponderado (Pressão do Book)
        ofi = self.calculate_wen_ofi(current_book)
        
        # 2. CVD do batch atual (Pressão de Agressão)
        cvd = self.calculate_cvd(ticks_df) if ticks_df is not None else 0.0
        self.cvd_history.append(cvd)
        if len(self.cvd_history) > 50: self.cvd_history.pop(0)

        # 3. Preço Médio do Batch para Divergência
        if ticks_df is not None and not ticks_df.empty:
            avg_price = ticks_df['price'].mean()
            self.price_history.append(avg_price)
            if len(self.price_history) > 50: self.price_history.pop(0)
        
        # 4. Detecção de Divergência (Absorção)
        divergence = self.detect_divergence(self.price_history, self.cvd_history)
        
        # 5. Detecção de Icebergs
        iceberg_signal = self.detect_icebergs(ticks_df, current_book) if ticks_df is not None else 0.0
        
        # [ANTIVIBE-CODING] - Pesos de Agregação Congelados
        # OFI (Book) + CVD (Tape) + Divergência (Absorção) + Icebergs (Ocultos)
        final_signal = (np.tanh(ofi / 500.0) * 0.4) + (np.tanh(cvd / 200.0) * 0.3) + (divergence * 0.2) + (iceberg_signal * 0.1)
        
        return float(np.clip(final_signal, -1.0, 1.0))

    def calculate_wen_ofi(self, current_book: dict, levels: int = 5) -> float:
        """
        [SOTA] Calcula o Weighted Order Flow Imbalance (OFI) Ponderado.
        L1=1.0, L2=0.8, L3=0.6, L4=0.4, L5=0.2
        """
        if not current_book or self.prev_book_levels is None:
            self.prev_book_levels = current_book
            return 0.0
            
        ofi_weighted_sum = 0.0
        weights = [max(0.2, 1.0 - (i * 0.2)) for i in range(levels)]
        
        curr_bids = current_book.get('bids', [])[:levels]
        prev_bids = self.prev_book_levels.get('bids', [])[:levels]
        curr_asks = current_book.get('asks', [])[:levels]
        prev_asks = self.prev_book_levels.get('asks', [])[:levels]
        
        limit = min(levels, len(curr_bids), len(prev_bids), len(curr_asks), len(prev_asks))
        
        for i in range(limit):
            w = weights[i]
            ofi_layer = 0.0
            
            try:
                cb_p, cb_v = curr_bids[i].get('price', 0), curr_bids[i].get('volume', 0)
                pb_p, pb_v = prev_bids[i].get('price', 0), prev_bids[i].get('volume', 0)
                if cb_p > pb_p: ofi_layer += cb_v
                elif cb_p < pb_p: ofi_layer -= pb_v
                elif cb_p > 0: ofi_layer += (cb_v - pb_v)
            except: pass
            
            try:
                ca_p, ca_v = curr_asks[i].get('price', 0), curr_asks[i].get('volume', 0)
                pa_p, pa_v = prev_asks[i].get('price', 0), prev_asks[i].get('volume', 0)
                if ca_p < pa_p: ofi_layer -= ca_p # Correção lógica: venda descendo é pressão vendedora
                elif ca_p > pa_p: ofi_layer += pa_v
                elif ca_p > 0: ofi_layer -= (ca_v - pa_v)
            except: pass
            
            ofi_weighted_sum += (ofi_layer * w)
            
        self.prev_book_levels = current_book
        return ofi_weighted_sum

    def calculate_cvd(self, ticks_df):
        """Calcula Cumulative Volume Delta do batch."""
        if ticks_df is None or ticks_df.empty: return 0.0
        
        flags = ticks_df['flags'].values
        volumes = ticks_df['volume_real'].values if 'volume_real' in ticks_df.columns else ticks_df['volume'].values
        
        buy_aggr = (flags & mt5.TICK_FLAG_BUY) == mt5.TICK_FLAG_BUY
        sell_aggr = (flags & mt5.TICK_FLAG_SELL) == mt5.TICK_FLAG_SELL
        
        return float(np.where(buy_aggr, volumes, 0).sum() - np.where(sell_aggr, volumes, 0).sum())

    def detect_divergence(self, price_arr, cvd_arr):
        """[HFT] Detecta divergência entre Preço e CVD (Absorção)."""
        if len(price_arr) < 5 or len(cvd_arr) < 5: return 0.0
        
        try:
            x = np.arange(len(price_arr))
            slope_price = np.polyfit(x, price_arr, 1)[0]
            slope_cvd = np.polyfit(x, cvd_arr, 1)[0]
            
            # Bullish: Preço cai/flat e CVD sobe (Vendedores sendo absorvidos por ordens limitadas de compra)
            if slope_price <= 0.0001 and slope_cvd > 10: return 1.0
            # Bearish: Preço sobe/flat e CVD cai (Compradores sendo absorvidos por ordens limitadas de venda)
            if slope_price >= -0.0001 and slope_cvd < -10: return -1.0
        except: pass
        return 0.0

    def detect_icebergs(self, ticks_df, current_book, threshold_ratio=3.0):
        """
        [HFT] Detecta ordens Iceberg.
        Se Volume Executado > N * Volume Visível no Level 1, há um Iceberg.
        """
        if ticks_df is None or ticks_df.empty or not current_book: return 0.0
        
        try:
            l1_bid_vol = current_book['bids'][0]['volume'] if current_book['bids'] else 1
            l1_ask_vol = current_book['asks'][0]['volume'] if current_book['asks'] else 1
            
            # Volume agredido no preço atual do L1
            # (Poderíamos filtrar pelo PREÇO exato do L1, mas o batch de ticks já é o 'now')
            cvd = self.calculate_cvd(ticks_df)
            
            # Iceberg de Compra (Alguém absorvendo a venda)
            if cvd < 0 and abs(cvd) > (l1_bid_vol * threshold_ratio):
                logging.warning(f"❄️ Iceberg de COMPRA detectado! CVD: {cvd}, L1-Bid: {l1_bid_vol}")
                return 1.0
                
            # Iceberg de Venda (Alguém absorvendo o ataque comprador)
            if cvd > 0 and cvd > (l1_ask_vol * threshold_ratio):
                logging.warning(f"❄️ Iceberg de VENDA detectado! CVD: {cvd}, L1-Ask: {l1_ask_vol}")
                return -1.0
        except: pass
        return 0.0

    def calculate_vwap(self, ticks_df):
        if ticks_df is None or ticks_df.empty: 
            return self.last_vwap
        volumes = ticks_df['volume_real'].values if 'volume_real' in ticks_df.columns else ticks_df['volume'].values
        prices = ticks_df['price'].values
        cum_vol = volumes.sum()
        if cum_vol == 0: return 0.0, 0.0
        vwap = (prices * volumes).sum() / cum_vol
        variance = ((prices - vwap)**2 * volumes).sum() / cum_vol
        self.last_vwap = (float(vwap), float(np.sqrt(variance)))
        return self.last_vwap
