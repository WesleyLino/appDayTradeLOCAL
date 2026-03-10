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
        self.cvd_accel_history = [] # [v50.1] Aceleração de Fluxo

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
        
        # 5. Detecção de Icebergs (OHLCV Aprimorado v50.1)
        iceberg_signal = self.detect_icebergs_v50(ticks_df, current_book, ticks_df is None)
        
        # 6. Aceleração de CVD (Urgência)
        cvd_accel = self.calculate_cvd_acceleration()
        
        # [ANTIVIBE-CODING] - Pesos de Agregação Atualizados v50.1 (70% Assertiveness Target)
        # OFI (Book) + CVD (Tape) + Divergência (Absorção) + Icebergs (Ocultos) + Aceleração (Urgência)
        # Shift de peso para Urgência e Absorção Oculta
        final_signal = (np.tanh(ofi / 500.0) * 0.35) + \
                       (np.tanh(cvd / 200.0) * 0.20) + \
                       (divergence * 0.15) + \
                       (iceberg_signal * 0.20) + \
                       (cvd_accel * 0.10)
        
        return float(np.clip(final_signal, -1.0, 1.0))

    def calculate_cvd_acceleration(self) -> float:
        """
        [v50.1] Calcula a aceleração do CVD para detectar Varreduras de Book (Sweeps).
        Mede a segunda derivada do fluxo de agressão.
        """
        if len(self.cvd_history) < 3: return 0.0
        
        # Variação do CVD (Velocidade)
        v1 = self.cvd_history[-1] - self.cvd_history[-2]
        v2 = self.cvd_history[-2] - self.cvd_history[-3]
        
        # Aceleração
        accel = v1 - v2
        self.cvd_accel_history.append(accel)
        if len(self.cvd_accel_history) > 10: self.cvd_accel_history.pop(0)
        
        # Normaliza aceleração (tanh para esmagar outliers)
        return float(np.tanh(accel / 1000.0))

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
        """
        [HFT MASTER] Detecta divergência entre Preço e CVD (Absorção).
        Bullish: Preço cai e CVD sobe (Absorção de Venda).
        Bearish: Preço sobe e CVD cai (Absorção de Compra).
        """
        if len(price_arr) < 10 or len(cvd_arr) < 10: return 0.0
        
        try:
            # Correlação de Pearson para detectar se estão andando em sentidos opostos
            corr = np.corrcoef(price_arr[-10:], cvd_arr[-10:])[0, 1]
            
            # Cálculo de inclinação (Slopes) para confirmar direção
            x = np.arange(10)
            slope_price = np.polyfit(x, price_arr[-10:], 1)[0]
            slope_cvd = np.polyfit(x, cvd_arr[-10:], 1)[0]
            
            # Divergência de Absorção (Preço e Volume andando em direções opostas)
            if corr < -0.85: # [RELAXADO] Somente divergências extremas causam veto
                # Bearish Absorption: Preço Sobe mas CVD Cai (Institucional Vendendo Passivo)
                if slope_price > 0 and slope_cvd < 0:
                    logging.debug(f"🚨 [ABSORÇÃO BEARISH] Divergência Detectada! Corr: {corr:.2f}")
                    return -1.0
                # Bullish Absorption: Preço Cai mas CVD Sobe (Institucional Comprando Passivo)
                if slope_price < 0 and slope_cvd > 0:
                    logging.debug(f"🚨 [ABSORÇÃO BULLISH] Divergência Detectada! Corr: {corr:.2f}")
                    return 1.0
        except Exception as e:
            logging.error(f"Erro em detect_divergence: {e}")
        return 0.0

    def detect_icebergs_v50(self, ticks_df, current_book, is_backtest=False, threshold_ratio=2.5):
        """
        [v50.1] Detecção Master de Icebergs.
        - Produção: Cruza Ticks agredidos vs Variação de Lote no Book.
        - Backtest: Price/Volume Efficiency (Volume alto em candle pequeno).
        """
        if is_backtest:
            # Lógica OHLCV: Se volume > 2x média e preço não se moveu (Efficiency < threshold)
            # Indica que alguém absorveu toda a urgência.
            if len(self.cvd_history) < 10: return 0.0
            
            # Precisamos do candle atual (simulado) para checar eficiência
            # Isso é injetado via breakdown ou história
            return 0.0 # Placeholder: será refinado no backtest_pro.py via injeção de sinais
            
        if ticks_df is None or ticks_df.empty or not current_book or self.prev_book_levels is None:
            return 0.0
        
        try:
            buy_vol = self.calculate_cvd_side(ticks_df, side='buy')
            sell_vol = self.calculate_cvd_side(ticks_df, side='sell')
            
            delta_bid_vol = current_book['bids'][0]['volume'] - self.prev_book_levels['bids'][0]['volume'] if (current_book['bids'] and self.prev_book_levels['bids']) else 0
            delta_ask_vol = current_book['asks'][0]['volume'] - self.prev_book_levels['asks'][0]['volume'] if (current_book['asks'] and self.prev_book_levels['asks']) else 0
            
            if sell_vol > abs(delta_bid_vol) * threshold_ratio and sell_vol > 50:
                logging.debug(f"❄️ [ICEBERG COMPRA] Executado: {sell_vol} | Sumiu do Book: {abs(delta_bid_vol)}")
                return 1.0
                
            if buy_vol > abs(delta_ask_vol) * threshold_ratio and buy_vol > 50:
                logging.debug(f"❄️ [ICEBERG VENDA] Executado: {buy_vol} | Sumiu do Book: {abs(delta_ask_vol)}")
                return -1.0
        except Exception as e:
            logging.error(f"Erro em detect_icebergs: {e}")
        return 0.0

    def calculate_cvd_side(self, ticks_df, side='buy'):
        """Auxiliar para calcular volume por lado de agressão."""
        if ticks_df is None or ticks_df.empty: return 0.0
        flags = ticks_df['flags'].values
        volumes = ticks_df['volume_real'].values if 'volume_real' in ticks_df.columns else ticks_df['volume'].values
        if side == 'buy':
            mask = (flags & mt5.TICK_FLAG_BUY) == mt5.TICK_FLAG_BUY
        else:
            mask = (flags & mt5.TICK_FLAG_SELL) == mt5.TICK_FLAG_SELL
        return float(volumes[mask].sum())

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
