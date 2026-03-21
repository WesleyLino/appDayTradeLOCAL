import numpy as np
import logging
import MetaTrader5 as mt5


class MicrostructureAnalyzer:
    def __init__(self):
        self.last_cvd = 0.0
        self.prev_book_levels = None
        self.cvd_history = []
        self.price_history = []
        self.last_vwap = (0.0, 0.0)  # (vwap, std)
        self.cvd_accel_history = []  # [v50.1] Aceleração de Fluxo
        self.last_cvd_accel = 0.0  # [v24.5] Cache para acesso rápido do bot

    def analyze(self, current_book, ticks_df=None):
        """
        [HFT ELITE] Interface unificada para análise de microestrutura.
        Agrega OFI Ponderado, CVD, Divergência e Icebergs.
        """
        # 1. OFI Ponderado (Pressão do Book - Fluxo de Ordens)
        # O OFI mede a mudança líquida no volume em cada nível.
        ofi = self.calculate_wen_ofi(current_book)

        # 2. OBI (Order Book Imbalance - Estado do Book)
        # O OBI mede a proporção de volume atual entre Compra vs Venda.
        obi_ratio = self.calculate_pure_obi(current_book)

        # 3. CVD do batch atual (Pressão de Agressão)
        cvd = self.calculate_cvd(ticks_df) if ticks_df is not None else 0.0
        self.cvd_history.append(cvd)
        if len(self.cvd_history) > 50:
            self.cvd_history.pop(0)

        # 4. Preço Médio do Batch para Divergência
        if ticks_df is not None and not ticks_df.empty:
            avg_price = ticks_df["price"].mean()
            self.price_history.append(avg_price)
            if len(self.price_history) > 50:
                self.price_history.pop(0)

        # 5. Detecção de Divergência (Absorção)
        divergence = self.detect_divergence(self.price_history, self.cvd_history)

        # 6. Detecção de Icebergs (OHLCV Aprimorado v50.1)
        iceberg_signal = self.detect_icebergs_v50(
            ticks_df, current_book, ticks_df is None
        )

        # 7. Aceleração de CVD (Urgência)
        self.last_cvd_accel = self.calculate_cvd_acceleration()

        # [ANTIVIBE-CODING] - Agregação Sincronizada v24.5 (Padrão Ouro de Assertividade)
        # O OFI ponderado é o coração da microestrutura.
        # O OBI ratio dá o viés de barreira.
        final_signal = (
            (np.tanh(ofi / 500.0) * 0.30)        # Fluxo de Book (Delta)
            + (obi_ratio * 0.15)                 # Estado de Book (Ratio)
            + (np.tanh(cvd / 200.0) * 0.15)      # Agressão TAPE
            + (divergence * 0.15)                # Absorção
            + (iceberg_signal * 0.15)            # Institucional Oculto
            + (self.last_cvd_accel * 0.10)       # Vigor/Urgência
        )

        return float(np.clip(final_signal, -1.0, 1.0))

    def calculate_cvd_acceleration(self) -> float:
        """
        [v50.1] Calcula a aceleração do CVD para detectar Varreduras de Book (Sweeps).
        Mede a segunda derivada do fluxo de agressão.
        """
        if len(self.cvd_history) < 3:
            return 0.0

        # Variação do CVD (Velocidade)
        v1 = self.cvd_history[-1] - self.cvd_history[-2]
        v2 = self.cvd_history[-2] - self.cvd_history[-3]

        # Aceleração
        accel = v1 - v2
        self.cvd_accel_history.append(accel)
        if len(self.cvd_accel_history) > 10:
            self.cvd_accel_history.pop(0)

        # Normaliza aceleração (tanh para esmagar outliers)
        return float(np.tanh(accel / 1000.0))

    def calculate_wen_ofi(self, current_book: dict, levels: int = 5) -> float:
        """
        [ULTRA-FAST v24.5] Weighted Order Flow Imbalance.
        Cálculo otimizado para evitar overhead de dicionário e corrigindo BUG de atribuição de preço.
        """
        if not current_book or self.prev_book_levels is None:
            self.prev_book_levels = current_book
            return 0.0

        curr_bids = current_book.get("bids", [])
        prev_bids = self.prev_book_levels.get("bids", [])
        curr_asks = current_book.get("asks", [])
        prev_asks = self.prev_book_levels.get("asks", [])

        ofi_weighted_sum = 0.0
        # Ponderação Linear L1=1.0 até L5=0.2
        limit = min(levels, len(curr_bids), len(prev_bids), len(curr_asks), len(prev_asks))

        for i in range(limit):
            w = 1.0 - (i * 0.2)
            
            # Lado BID (Compradores Passivos)
            cb_p, cb_v = curr_bids[i]["price"], curr_bids[i]["volume"]
            pb_p, pb_v = prev_bids[i]["price"], prev_bids[i]["volume"]
            
            if cb_p > pb_p:
                ofi_weighted_sum += cb_v * w
            elif cb_p < pb_p:
                ofi_weighted_sum -= pb_v * w
            else:
                ofi_weighted_sum += (cb_v - pb_v) * w

            # Lado ASK (Vendedores Passivos)
            ca_p, ca_v = curr_asks[i]["price"], curr_asks[i]["volume"]
            pa_p, pa_v = prev_asks[i]["price"], prev_asks[i]["volume"]
            
            if ca_p < pa_p:
                ofi_weighted_sum -= ca_v * w
            elif ca_p > pa_p:
                ofi_weighted_sum += pa_v * w
            else:
                ofi_weighted_sum -= (ca_v - pa_v) * w

        self.prev_book_levels = current_book
        return ofi_weighted_sum

    def calculate_pure_obi(self, current_book: dict, levels: int = 5) -> float:
        """
        [v24.5] Order Book Imbalance (Ratio).
        Retorna o ratio Volume_Bid / Volume_Ask.
        Valores > 1.0 (ex: 1.5) indicam predominância de compra.
        Valores < 1.0 (ex: 0.8) indicam predominância de venda.
        Compatível com gatilhos de bypass de ai_core.py (thresh 1.5/1.8).
        """
        if not current_book or not current_book.get("bids") or not current_book.get("asks"):
            return 1.0

        # Ponderação por proximidade ao preço atual
        sum_bid_vol = sum(b.get("volume", 0) * (1.1 - (i * 0.2)) for i, b in enumerate(current_book["bids"][:levels]))
        sum_ask_vol = sum(a.get("volume", 0) * (1.1 - (i * 0.2)) for i, a in enumerate(current_book["asks"][:levels]))

        if sum_ask_vol == 0:
            return 10.0 if sum_bid_vol > 0 else 1.0
        
        ratio = sum_bid_vol / sum_ask_vol
        return float(np.clip(ratio, 0.1, 10.0))

    def calculate_cvd(self, ticks_df):
        """Calcula Cumulative Volume Delta do batch."""
        if ticks_df is None or ticks_df.empty:
            return 0.0

        flags = ticks_df["flags"].values
        volumes = (
            ticks_df["volume_real"].values
            if "volume_real" in ticks_df.columns
            else ticks_df["volume"].values
        )

        buy_aggr = (flags & mt5.TICK_FLAG_BUY) == mt5.TICK_FLAG_BUY
        sell_aggr = (flags & mt5.TICK_FLAG_SELL) == mt5.TICK_FLAG_SELL

        return float(
            np.where(buy_aggr, volumes, 0).sum() - np.where(sell_aggr, volumes, 0).sum()
        )

    def detect_divergence(self, price_arr, cvd_arr):
        """
        [HFT MASTER] Detecta divergência entre Preço e CVD (Absorção).
        Bullish: Preço cai e CVD sobe (Absorção de Venda).
        Bearish: Preço sobe e CVD cai (Absorção de Compra).
        """
        if len(price_arr) < 10 or len(cvd_arr) < 10:
            return 0.0

        try:
            # Correlação de Pearson para detectar se estão andando em sentidos opostos
            corr = np.corrcoef(price_arr[-10:], cvd_arr[-10:])[0, 1]

            # Cálculo de inclinação (Slopes) para confirmar direção
            x = np.arange(10)
            slope_price = np.polyfit(x, price_arr[-10:], 1)[0]
            slope_cvd = np.polyfit(x, cvd_arr[-10:], 1)[0]

            # Divergência de Absorção (Preço e Volume andando em direções opostas)
            if corr < -0.85:  # [RELAXADO] Somente divergências extremas causam veto
                # Bearish Absorption: Preço Sobe mas CVD Cai (Institucional Vendendo Passivo)
                if slope_price > 0 and slope_cvd < 0:
                    logging.debug(
                        f"🚨 [ABSORÇÃO BEARISH] Divergência Detectada! Corr: {corr:.2f}"
                    )
                    return -1.0
                # Bullish Absorption: Preço Cai mas CVD Sobe (Institucional Comprando Passivo)
                if slope_price < 0 and slope_cvd > 0:
                    logging.debug(
                        f"🚨 [ABSORÇÃO BULLISH] Divergência Detectada! Corr: {corr:.2f}"
                    )
                    return 1.0
        except Exception as e:
            logging.error(f"Erro em detect_divergence: {e}")
        return 0.0

    def detect_icebergs_v50(
        self, ticks_df, current_book, is_backtest=False, threshold_ratio=2.5
    ):
        """
        [v50.1] Detecção Master de Icebergs.
        - Produção: Cruza Ticks agredidos vs Variação de Lote no Book.
        - Backtest: Price/Volume Efficiency (Volume alto em candle pequeno).
        """
        if is_backtest:
            # Lógica OHLCV: Se volume > 2x média e preço não se moveu (Efficiency < threshold)
            # Indica que alguém absorveu toda a urgência.
            if len(self.cvd_history) < 10:
                return 0.0

            # Precisamos do candle atual (simulado) para checar eficiência
            # Isso é injetado via breakdown ou história
            return 0.0  # Placeholder: será refinado no backtest_pro.py via injeção de sinais

        if (
            ticks_df is None
            or ticks_df.empty
            or not current_book
            or self.prev_book_levels is None
        ):
            return 0.0

        try:
            buy_vol = self.calculate_cvd_side(ticks_df, side="buy")
            sell_vol = self.calculate_cvd_side(ticks_df, side="sell")

            delta_bid_vol = (
                current_book["bids"][0]["volume"]
                - self.prev_book_levels["bids"][0]["volume"]
                if (current_book["bids"] and self.prev_book_levels["bids"])
                else 0
            )
            delta_ask_vol = (
                current_book["asks"][0]["volume"]
                - self.prev_book_levels["asks"][0]["volume"]
                if (current_book["asks"] and self.prev_book_levels["asks"])
                else 0
            )

            if sell_vol > abs(delta_bid_vol) * threshold_ratio and sell_vol > 50:
                logging.debug(
                    f"❄️ [ICEBERG COMPRA] Executado: {sell_vol} | Sumiu do Book: {abs(delta_bid_vol)}"
                )
                return 1.0

            if buy_vol > abs(delta_ask_vol) * threshold_ratio and buy_vol > 50:
                logging.debug(
                    f"❄️ [ICEBERG VENDA] Executado: {buy_vol} | Sumiu do Book: {abs(delta_ask_vol)}"
                )
                return -1.0
        except Exception as e:
            logging.error(f"Erro em detect_icebergs: {e}")
        return 0.0

    def calculate_cvd_side(self, ticks_df, side="buy"):
        """Auxiliar para calcular volume por lado de agressão."""
        if ticks_df is None or ticks_df.empty:
            return 0.0
        flags = ticks_df["flags"].values
        volumes = (
            ticks_df["volume_real"].values
            if "volume_real" in ticks_df.columns
            else ticks_df["volume"].values
        )
        if side == "buy":
            mask = (flags & mt5.TICK_FLAG_BUY) == mt5.TICK_FLAG_BUY
        else:
            mask = (flags & mt5.TICK_FLAG_SELL) == mt5.TICK_FLAG_SELL
        return float(volumes[mask].sum())

    def calculate_vwap(self, ticks_df):
        if ticks_df is None or ticks_df.empty:
            return self.last_vwap
        volumes = (
            ticks_df["volume_real"].values
            if "volume_real" in ticks_df.columns
            else ticks_df["volume"].values
        )
        prices = ticks_df["price"].values
        cum_vol = volumes.sum()
        if cum_vol == 0:
            return 0.0, 0.0
        vwap = (prices * volumes).sum() / cum_vol
        variance = ((prices - vwap) ** 2 * volumes).sum() / cum_vol
        self.last_vwap = (float(vwap), float(np.sqrt(variance)))
        return self.last_vwap
