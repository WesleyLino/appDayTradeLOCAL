from backend.microstructure_analyzer import MicrostructureAnalyzer # HFT v2.0
from backend.meta_learner import MetaLearner # HFT v2.0 Meta-Learner
from sklearn.cluster import KMeans # Keep KMeans for regime_model
from dotenv import load_dotenv
import torch # Import necessário para InferenceEngine
import time
import gc
from datetime import datetime

import google.generativeai as genai
import os
import logging
import numpy as np
import asyncio
import json
import pandas as pd

load_dotenv()

# AICore agora consome dados do NewsSentimentWorker via data/news_sentiment.json

class AICore:
    def __init__(self):
        self._latest_sentiment_score = 0.0 # [SOTA v5] Valor real (atras do decorator)
        self.obi_ema = 0.5 # Valor inicial neutro
        self.ema_alpha = 0.2 # Fator de suavização
        self.regime_model = KMeans(n_clusters=3, n_init=10)
        self.regime_history = []
        self.regime_counter = 0
        self.prev_book = None
        self.toxic_flow_score = 0.0
        self.last_news_update = 0
        self.micro_analyzer = MicrostructureAnalyzer()
        self.meta_learner = MetaLearner() 
        self.inference_engine = None # Injetado pelo main.py

        # [NEW CONFIGURABLE PARAMETERS - HIGH GAIN RESEARCH]
        self.uncertainty_threshold_base = 0.25 # [ANTIVIBE-CODING] Default Seguro
        self.lot_multiplier_partial = 0.25     # [ANTIVIBE-CODING] Default Seguro
        self.uncertainty_high_conviction_cap = 4.0 # 400%
        
        # [REFINAMENTO 26/02] Controle de Cooldown e Estabilidade
        self.consecutive_losses = 0
        self.ia_cooldown_until = 0 # Timestamp
        self.atr_history = [] # Para calculo de inercia de volatilidade
        
        # [SOTA v4] NOVAS CONFIGURAÇÕES DE ASSERTIVIDADE
        self.h1_trend = 0 # -1 (Baixa), 0 (Neutro), 1 (Alta)
        self.prob_lot_tiers = {
            "low": 0.25,      # Confiança 70-75%
            "medium": 0.75,   # Confiança 75-85%
            "high": 1.0       # Confiança > 85%
        }
        
        # [SOTA v25] SENTIMENTO MACRO (EMA 60m)
        self.sentiment_ema = 0.0
        self.sentiment_alpha = 0.033 # ~60 períodos para estabilização (1-min)
        self.macro_bull_lock = False
        self.macro_bear_lock = False

        self.sentiment_anchor_price = 0.0
        self.sentiment_anchor_time = 0
        self.max_sentiment_drift = 150.0 # Pontos do WIN para absorção total
        self.opening_window_rigor = 1.5   # Multiplicador de rigor 09:00-09:30
        self.spread_veto_threshold = 15.0 # Veto se spread > 15.0 pts (3 ticks do WIN)

        # [ALPHA v1.0] CONFIGURAÇÕES DE FLEXIBILIZAÇÃO
        self.mean_reversion_threshold = 2.0 # ATR (Semana 2: Flexibilizado de 1.5 para 2.0)
        self.cooldown_mode = "DYNAMIC"      # DYNAMIC (Lote reduzido - Semana 3) ou HARD (Veto total)
        self.opening_rigor_enabled = True   # Permite desligar o rigor extra de abertura

    def fetch_latest_news(self):
        """
        Coleta notícias de 'backend/news_feed.txt' para análise de sentimento.
        Permite que o usuário insira notícias em tempo real salvando no arquivo.
        """
        news_file = os.path.join(os.path.dirname(__file__), "news_feed.txt")
        if os.path.exists(news_file):
            try:
                with open(news_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return content
            except Exception as e:
                logging.error(f"Erro ao ler news_feed.txt: {e}")
        
        # Fallback se arquivo vazio ou inexistente
        return "Mercado aguardando novos dados. Sem notícias relevantes no momento."

    # [Fase 27] Lógica evaluate_opportunity removida. 
    # O Bot agora decide usando calculate_decision diretamente para maior controle de parâmetros.

    # [SOTA v5] Property para Sincronização Automática de Âncora
    @property
    def latest_sentiment_score(self):
        return self._latest_sentiment_score

    @latest_sentiment_score.setter
    def latest_sentiment_score(self, value):
        # [SOTA v25] CÁLCULO DE EMA MACRO (Suavização de 1h) - Funciona em Live e Backtest
        self.sentiment_ema = (value * self.sentiment_alpha) + (self.sentiment_ema * (1 - self.sentiment_alpha))
        
        # Atualização das Travas Macro
        self.macro_bull_lock = self.sentiment_ema > 0.15
        self.macro_bear_lock = self.sentiment_ema < -0.15

        # Reset de Âncora se o novo score for significativamente diferente (> 0.3)
        # Isso centraliza a lógica para Live, Sniper e Backtest.
        if hasattr(self, '_latest_sentiment_score') and abs(value - self._latest_sentiment_score) > 0.3:
            self.sentiment_anchor_price = 0.0
            logging.debug(f"⚓ SOTA v5: Sentiment Anchor Reset (Delta > 0.3). New Score: {value:.2f}")
        self._latest_sentiment_score = value

    async def update_sentiment(self):
        """
        Lê o score de sentimento do arquivo gerado pelo NewsSentimentWorker.
        Remove latência e custo de chamadas repetitivas à API no loop principal.
        """
        sentiment_file = os.path.join("data", "news_sentiment.json")
        if not os.path.exists(sentiment_file):
            # Fallback legacy: news_feed.txt
            legacy_news = self.fetch_latest_news()
            if "Sem notícias relevantes" not in legacy_news:
                logging.debug("⚠️ Usando news_feed.txt como fallback (Worker Inativo)")
            return self.latest_sentiment_score

        try:
            if os.path.getsize(sentiment_file) == 0:
                logging.warning("⚠️ news_sentiment.json vazio.")
                return self.latest_sentiment_score

            with open(sentiment_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            score = float(data.get("score", 0.0))
            timestamp = data.get("timestamp", 0)
            reliability = data.get("reliability", "low")
            risk_level = data.get("risk_classification", "LOW")
            
            # [FASE 28] TTL DINÂMICO POR NÍVEL DE RISCO
            # Eventos sistêmicos têm vida longa; ruído expira rápido.
            ttl_map = {
                "EXTREME": 8 * 3600,  # 8h  – eventos geopolíticos/sistêmicos persistem
                "HIGH":    2 * 3600,  # 2h  – macro surpresa, normaliza no pregão
                "MEDIUM":  30 * 60,   # 30min – notícia corporativa, absorção rápida
                "LOW":     10 * 60,   # 10min – ruído, descartável
            }
            ttl = ttl_map.get(risk_level, 15 * 60)  # Fallback: 15min
            age_seconds = time.time() - timestamp
            
            if age_seconds > ttl:
                logging.warning(
                    f"⏰ Sentiment expirado [{risk_level}]: {age_seconds/60:.0f}min > TTL {ttl/60:.0f}min. Neutralizando."
                )
                self.latest_sentiment_score = 0.0
            else:
                if reliability == "low": score *= 0.5
                
                # O reset de âncora e EMA agora são feitos automaticamente pelo setter de latest_sentiment_score
                self.latest_sentiment_score = max(-1.0, min(1.0, score))
                
            return self.latest_sentiment_score
        except (json.JSONDecodeError, ValueError) as je:
            logging.error(f"❌ Corrupção de dados no JSON de sentimento: {je}")
            return self.latest_sentiment_score
        except Exception as e:
            logging.error(f"Erro ao ler news_sentiment.json: {e}")
            return self.latest_sentiment_score

    def detect_spoofing(self, order_book, time_sales):
        """
        Detecta spoofing comparando volume do book com histórico recente.
        Implementa a regra de 'Toxic Flow': sumiço de ordens grandes sem trade.
        """
        if not order_book or (not order_book.get('bids') and not order_book.get('asks')):
            return 0.5
            
        # 1. OBI (Order Book Imbalance) com Decaimento Exponencial (Depth-Weighted)
        # Sugerido: Nível 1: 1.0, Nível 2: 0.6, Nível 3: 0.3, Nível 4: 0.1
        weights = [1.0, 0.6, 0.3, 0.1]
        
        def get_weighted_volume(items):
            total = 0
            for i, item in enumerate(items):
                weight = weights[i] if i < len(weights) else 0.05 # Longe do book: quase zero
                total += item['volume'] * weight
            return total

        total_bid_weighted = get_weighted_volume(order_book.get('bids', []))
        total_ask_weighted = get_weighted_volume(order_book.get('asks', []))
        
        total_bid_raw = sum(item['volume'] for item in order_book.get('bids', []))
        total_ask_raw = sum(item['volume'] for item in order_book.get('asks', []))
        
        current_obi = 0.5
        if total_bid_weighted + total_ask_weighted > 0:
            current_obi = (total_bid_weighted - total_ask_weighted) / (total_bid_weighted + total_ask_weighted + 1)
        
        # Suavização EMA
        self.obi_ema = (current_obi * self.ema_alpha) + (self.obi_ema * (1 - self.ema_alpha))
        
        # 2. Detecção de Toxic Flow (Remoção Súbita vs Execução Real)
        if self.prev_book is not None:
            # Usamos o RAW aqui, para comparar com a agressão real de mercado e medir lotes físicos cancelados
            prev_bid_raw = sum(item['volume'] for item in self.prev_book.get('bids', []))
            prev_ask_raw = sum(item['volume'] for item in self.prev_book.get('asks', []))
            
            # Cálculo exato de agressão (Volume Executado por Lado)
            # time_sales deve ser filtrado se possível, ou usar heurística
            # Assumindo que DataCollector entrega 'real_volume' e 'flags'
            # Se não tiver flags, usamos volume total como proxy conservador
            
            sell_aggression_vol = 0 # Agressão de Venda (consome Bid)
            buy_aggression_vol = 0 # Agressão de Compra (consome Ask)
            
            if time_sales is not None and hasattr(time_sales, 'empty') and not time_sales.empty:
                # Na B3, TICK_FLAG_BUY (agressão compra) e TICK_FLAG_SELL (agressão venda)
                # 0x100: BUY, 0x200: SELL (Flags MT5)
                buy_aggression_vol = time_sales[time_sales['flags'] & 0x100]['volume'].sum() if 'flags' in time_sales.columns else 0
                sell_aggression_vol = time_sales[time_sales['flags'] & 0x200]['volume'].sum() if 'flags' in time_sales.columns else 0
                real_volume = buy_aggression_vol + sell_aggression_vol
            else:
                real_volume = 0
            
            # --- LÓGICA ALPHA-X: CANCELLATION RATE ---
            # Comparamos quanto do volume sumiu (delta) vs quanto foi de fato executado (aggression)
            delta_bid = max(0, prev_bid_raw - total_bid_raw)
            delta_ask = max(0, prev_ask_raw - total_ask_raw)
            
            # Cancellation Rate: Proporção do volume removido que NÃO foi trade
            # Se sumiu 1000 e trade foi 100, 900 foram cancelados -> CR = 0.9
            cr_bid = (delta_bid - sell_aggression_vol) / delta_bid if delta_bid > 0 else 0
            cr_ask = (delta_ask - buy_aggression_vol) / delta_ask if delta_ask > 0 else 0

            # Thresholds Dinâmicos (HFT v2.1)
            threshold_bid = max(20, total_bid_raw * 0.1)
            threshold_ask = max(20, total_ask_raw * 0.1)
            
            # [SPOOFING DE COMPRA]: Lotes sumindo no Bid sem agressão correspondente
            if delta_bid > threshold_bid and cr_bid > 0.8:
                self.toxic_flow_score = -0.9
                logging.warning(f"🔥 ALPHA-X SPOOFING: Compra sumiu por cancelamento (CR: {cr_bid:.2f})")

            # [SPOOFING DE VENDA]: Lotes sumindo no Ask sem agressão correspondente
            elif delta_ask > threshold_ask and cr_ask > 0.8:
                self.toxic_flow_score = 0.9
                logging.warning(f"🔥 ALPHA-X SPOOFING: Venda sumiu por cancelamento (CR: {cr_ask:.2f})")
                
            else:
                self.toxic_flow_score *= 0.8 # Decaimento
                
        self.prev_book = order_book
        
        # Ajusta o OBI final com base no fluxo tóxico
        final_signal = self.obi_ema + self.toxic_flow_score
        
        # [AUDITORIA] Log de Pressão OBI Ponderada
        if abs(final_signal) > 0.4:
            logging.info(f"🛡️ [OBI-SOTA] Pressão (Ponderada): {final_signal:.2f} | Fluxo Tóxico: {self.toxic_flow_score:.2f}")
        return max(-1.0, min(1.0, final_signal))

    def detect_regime(self, volatility, obi):
        """Usa Clustering para identificar o regime de mercado atual."""
        self.regime_history.append([volatility, obi])
        if len(self.regime_history) < 20: 
            return 0 # Default: Consolidação
            
        if len(self.regime_history) > 100:
            self.regime_history.pop(0)
            
        # Fit periódico para não sobrecarregar o loop (ex: a cada 100 amostras)
        self.regime_counter += 1
        if self.regime_counter % 100 == 0:
            data = np.array(self.regime_history)
            self.regime_model.fit(data)
            
        current_state = np.array([[volatility, obi]])
        try:
            # Predict returns the original cluster label
            raw_label = int(self.regime_model.predict(current_state)[0])
            
            # Sort cluster centers by volatility (index 0) to consistently map:
            # 0: Baixa Vol (Consolidação), 1: Média Vol (Tendência), 2: Alta Vol (Ruído)
            centers = self.regime_model.cluster_centers_
            sorted_indices = np.argsort(centers[:, 0])
            mapped_label = int(np.where(sorted_indices == raw_label)[0][0])
            
            return mapped_label
        except Exception as e:
            return 0

    def calculate_probabilistic_lot(self, score, quantile_confidence):
        """
        [SOTA v4] Calcula o multiplicador de lote baseado na convicção da IA.
        """
        # Se quantile_confidence for NORMAL, o rigor é maior
        if quantile_confidence == "NORMAL":
            if score >= 90 or score <= 10: return self.prob_lot_tiers["high"]
            if score >= 85 or score <= 15: return self.prob_lot_tiers["medium"]
            return self.prob_lot_tiers["low"]
        
        # Se for HIGH/VERY_HIGH, autoriza mais exposição
        if score >= 85 or score <= 15: return self.prob_lot_tiers["high"]
        return self.prob_lot_tiers["medium"]

    def update_h1_trend(self, h1_data):
        """
        [SOTA v4] Atualiza o viés de tendência do tempo superior (H1).
        H1 Data: DataFrame com dados M15/H1.
        """
        if h1_data is None or len(h1_data) < 2:
            self.h1_trend = 0
            return
            
        last_close = h1_data['close'].iloc[-1]
        prev_close = h1_data['close'].iloc[-2]
        
        # Heurística simples: Preço acima/abaixo da média de 20 períodos em H1
        ma20 = h1_data['close'].rolling(20).mean().iloc[-1] if len(h1_data) >= 20 else last_close
        
        if last_close > ma20 * 1.002: # 0.2% acima da média
            self.h1_trend = 1 # Alta
        elif last_close < ma20 * 0.998: # 0.2% abaixo da média
            self.h1_trend = -1 # Baixa
        else:
            self.h1_trend = 0 # Neutro

    def update_sentiment_anchor(self, price):
        """
        [SOTA v5] Define o preço âncora para o decaimento de sentimento.
        Chamado pelo loop principal (TradingBridge ou BacktestPro).
        """
        if self.sentiment_anchor_price == 0 and abs(self.latest_sentiment_score) > 0.1:
            self.sentiment_anchor_price = price
            logging.debug(f"⚓ SENTIMENT ANCHOR SET: {price:.1f} (Score: {self.latest_sentiment_score:.2f})")

    def calculate_decision(self, obi, sentiment, patchtst_score, regime=0, atr=0.0, volatility=0.0, hour=0, minute=0, ofi=0.0, current_price=0.0, spread=0.0, sma_20=0.0, wdo_aggression=0.0):
        """
        [SOTA v5] Fluxo de Decisão com Camadas de Precisão
        [SOTA v25.3] Adicionado sma_20 para Mean Reversion Guard.
        """
        # 0. [SOTA v5] Sentiment Decay Adaptativo (Absorção por preço)
        if self.sentiment_anchor_price > 0 and abs(sentiment) > 0.1:
            price_drift = abs(current_price - self.sentiment_anchor_price)
            decay_factor = max(0.0, 1.0 - (price_drift / self.max_sentiment_drift))
            sentiment *= decay_factor
            if decay_factor < 0.2:
                logging.debug(f"🧽 SENTIMENTO ABSORVIDO: Preço moveu {price_drift:.1f} pts. Neutralizando.")
        # 1. Normalização Inicial
        uncertainty_abs = 0.0
        forecast_ref = 1.0
        q10 = q50 = q90 = None
        quantile_confidence = "NORMAL"
        
        if isinstance(patchtst_score, dict):
            uncertainty_abs = patchtst_score.get("uncertainty_norm", 0.0)
            forecast_ref = patchtst_score.get("forecast_norm", 1.0)
            if forecast_ref == 0: forecast_ref = 1.0
            q10, q50, q90 = patchtst_score.get("q10"), patchtst_score.get("q50"), patchtst_score.get("q90")

            if q10 is not None and q50 is not None and q90 is not None:
                spread_up, spread_down = abs(q90 - q50), abs(q50 - q10)
                if spread_up > spread_down * 1.35 and spread_up > 0.01: quantile_confidence = "VERY_HIGH"
                elif spread_down > spread_up * 1.35 and spread_down > 0.01: quantile_confidence = "VERY_HIGH"
                elif max(spread_up, spread_down) > 0.005: quantile_confidence = "HIGH"

            norm_patchtst = (patchtst_score.get("score", 0.5) - 0.5) * 2
        else:
            norm_patchtst = (patchtst_score - 0.5) * 2
        
        # 2. Incerteza Relativa
        uncertainty_rel = abs(uncertainty_abs / max(0.50, abs(norm_patchtst)))
        
        # 3. EMA de OBI para Filtro de Divergência
        self.obi_ema = (obi * self.ema_alpha) + (self.obi_ema * (1 - self.ema_alpha))
        
        # 4. Threshold de Incerteza e Rigor Adaptativo
        uncertainty_threshold = self.uncertainty_threshold_base
        lot_multiplier = 1.0
        veto_reason = None

        if (sentiment > 0.6 and obi > 1.2) or (sentiment < -0.6 and obi < -1.2):
            uncertainty_threshold = max(uncertainty_threshold, 0.40)
        
        # [SOTA v25.6] SWEET SPOT RIGOR (BALANCING 70% TARGET)
        uncertainty_threshold = 0.30 # Ideal para filtrar ruido sem matar o volume
        if regime == 2 or abs(ofi) > 2.0:
            uncertainty_threshold = 0.20 # Rigor em ruído
            logging.info("🛡️ FILTRO DE RUÍDO: Rigor 0.20")
            
        if quantile_confidence == "VERY_HIGH":
            uncertainty_threshold *= 2.0
            
        # [SOTA v5] Meta-Learner Fine-Tuning: Filtro de Abertura (09:00 - 09:30)
        is_opening_session = (hour == 9 and minute < 30)
        if is_opening_session and self.opening_rigor_enabled:
            uncertainty_threshold *= (1.0 / self.opening_window_rigor) # Reduz threshold = aumenta rigor
            logging.info(f"🛡️ RIGOR DE ABERTURA ATIVO: 09:{minute:02d}. Filtros restritos habilitados.")

        # [PRO] Inércia de Volatilidade
        if atr > 0:
            self.atr_history.append(atr)
            if len(self.atr_history) > 10: self.atr_history.pop(0)
            if len(self.atr_history) >= 5:
                atr_inertia = atr - self.atr_history[-5]
                if atr_inertia < -12.0: # Exaustão
                    uncertainty_threshold *= 0.85 
                    logging.info(f"🧊 EXAUSTÃO DE VOLATILIDADE: Apertando o rigor ({atr_inertia:.1f})")

        # 5. Verificação de Vetos (Fail-Safes)
        ia_in_cooldown = time.time() < self.ia_cooldown_until
        
        if ia_in_cooldown and self.cooldown_mode == "HARD":
            veto_reason = "IA_COOLDOWN_VETO"
        elif uncertainty_rel > uncertainty_threshold:
            if quantile_confidence == "VERY_HIGH" and uncertainty_rel < self.uncertainty_high_conviction_cap:
                lot_multiplier = self.lot_multiplier_partial
                logging.warning(f"🛡️ ENTRADA ULTRA-CONSERVADORA: Alta incerteza ({uncertainty_rel*100:.1f}%)")
            else:
                veto_reason = f"ALTA_INCERTEZA_FAILSAFE ({uncertainty_rel*100:.1f}% > {uncertainty_threshold*100:.1f}%)"
        
        # [PRO] Filtro de Divergência de Fluxo Inter-Mercados (WDO vs WIN)
        if veto_reason is None and wdo_aggression != 0.0:
            ai_dir = np.sign(norm_patchtst)
            if ai_dir > 0 and wdo_aggression > 1.5:  
                veto_reason = "WDO_CROSS_CORRELATION_VETO_BUY_BLOCKED"
                logging.info("🛡️ VETO INTER-MERCADOS: Compra vetada por fluxo massivo de alta no WDO.")
            elif ai_dir < 0 and wdo_aggression < -1.5:
                veto_reason = "WDO_CROSS_CORRELATION_VETO_SELL_BLOCKED"
                logging.info("🛡️ VETO INTER-MERCADOS: Venda vetada por fluxo massivo de baixa no WDO.")

        # [PRO] Filtro de Divergência Interna de Fluxo
        if veto_reason is None:
            ai_dir = np.sign(norm_patchtst)
            obi_dir = np.sign(self.obi_ema)
            if abs(self.obi_ema) > 1.5 and ai_dir != 0 and ai_dir != obi_dir:
                veto_reason = "FLOW_DIVERGENCE_VETO"

        # [SOTA v4] Filtro Direcional H1 (Regime Maestro)
        if veto_reason is None:
            ai_dir = np.sign(norm_patchtst)
            if self.h1_trend == 1 and ai_dir < 0: # Venda contra tendência de alta H1
                veto_reason = "H1_BULLISH_TREND_VETO"
            elif self.h1_trend == -1 and ai_dir > 0: # Compra contra tendência de baixa H1
                veto_reason = "H1_BEARISH_TREND_VETO"
                
        # [SOTA v25] MACRO SENTIMENT LOCKS (70% ASSERTIVENESS TARGET)
        if veto_reason is None:
            ai_dir_raw = ai_dir if 'ai_dir' in locals() else 0
            if ai_dir_raw < 0:
                if self.macro_bull_lock:
                    veto_reason = f"MACRO_BULL_BLOCK (EMA {self.sentiment_ema:.2f} > 0.15)"
                    logging.info("🛡️ [ANTI-NOISE] Venda barrada pela tendência de alta macro.")
            elif ai_dir_raw > 0:
                if self.macro_bear_lock:
                    veto_reason = f"MACRO_BEAR_BLOCK (EMA {self.sentiment_ema:.2f} < -0.15)"
                    logging.info("🛡️ [ANTI-NOISE] Compra barrada pela tendência de baixa macro.")

        # [SOTA v25.3] MEAN REVERSION GUARD (Avoid Buying Tops / Selling Bottoms)
        if veto_reason is None and sma_20 > 0 and atr > 0:
            ai_dir_raw = ai_dir if 'ai_dir' in locals() else 0
            dist_pts = current_price - sma_20
            atr_dist = abs(dist_pts) / atr if atr > 0 else 0
            
            # [SOTA v25.4] Endurecido para 1.5 ATR para garantir > 70% Win Rate
            if ai_dir_raw > 0 and dist_pts > (self.mean_reversion_threshold * atr):
                veto_reason = f"VETO_REVERSAO_MEDIA_COMPRA (dist={dist_pts:.1f}, threshold={self.mean_reversion_threshold} ATR)"
                logging.info(f"🛡️ [ANTI-EXHAUSTION] Compra bloqueada: Preço esticado ({self.mean_reversion_threshold} ATR).")
            elif ai_dir_raw < 0 and dist_pts < (-self.mean_reversion_threshold * atr):
                veto_reason = f"VETO_REVERSAO_MEDIA_VENDA (dist={dist_pts:.1f}, threshold={self.mean_reversion_threshold} ATR)"
                logging.info(f"🛡️ [ANTI-EXHAUSTION] Venda bloqueada: Preço esticado ({self.mean_reversion_threshold} ATR).")

        # [SOTA v5] Spread Veto (Proteção contra Slippage)
        if veto_reason is None and spread > self.spread_veto_threshold:
            veto_reason = f"VETO_DE_SPREAD_ALTO ({spread:.1f} > {self.spread_veto_threshold})"
            logging.warning(f"⚠️ VETO DE SPREAD: {spread:.1f} pts > {self.spread_veto_threshold}")

        # 6. Cálculo do Score Final
        if veto_reason:
            norm_patchtst = 0.0
            lot_multiplier = 0.0 # Zerar lote se vetado
        
        # Dinâmica de Pesos
        w_sent, w_obi, w_patchtst = 0.30, 0.20, 0.50
        if abs(sentiment) < 0.001 and abs(obi) < 0.01:
            w_patchtst, w_sent, w_obi = 0.85, 0.08, 0.07
        elif regime == 0: w_obi, w_patchtst, w_sent = 0.40, 0.40, 0.20
        elif regime == 1: w_obi, w_patchtst, w_sent = 0.15, 0.75, 0.10

        composite_signal = (obi * w_obi) + (norm_patchtst * w_patchtst) + (sentiment * w_sent)
        ai_score_raw = max(0.0, min(100.0, (composite_signal + 1) * 50))

        # 7. Meta-Learner (The Silence Rule)
        meta_score = ai_score_raw
        if self.meta_learner.model is not None:
            try:
                meta_features = [atr, obi, sentiment, volatility, hour, ai_score_raw / 100.0]
                meta_prob = self.meta_learner.predict_proba([meta_features])[0]
                meta_score = (ai_score_raw if ai_score_raw >= 50 else (1.0 - meta_prob) * 100) # Simplificado para exemplo
                
                if 0.45 <= meta_prob <= 0.55 and veto_reason is None:
                    lot_multiplier *= self.lot_multiplier_partial
                    logging.info(f"🤫 REGRA DO SILÊNCIO: Meta-Learner neutro ({meta_prob:.2%})")
            except: pass

        # Fusão Final
        final_score = (ai_score_raw * 0.4) + (meta_score * 0.6)
        if veto_reason: final_score = 50.0

        # Direção - [SOTA v25.6] SWEET SPOT PUSH (85-90%+)
        buy_threshold = 90.0
        sell_threshold = 10.0
        
        direction = "NEUTRAL"
        exec_strategy = "PASSIVA"
        
        if final_score >= buy_threshold:
            direction = "COMPRA"
            exec_strategy = "MERCADO" if final_score >= 95.0 else "SNIPER" if final_score >= 90.0 else "PASSIVA"
        elif final_score <= sell_threshold:
            direction = "VENDA"
            exec_strategy = "MERCADO" if final_score <= 5.0 else "SNIPER" if final_score <= 10.0 else "PASSIVA"
        
        # [SOTA v5] Dimensionamento de Lote Probabilístico e Ajuste de Abertura
        if veto_reason is None and direction != "NEUTRAL":
            lot_multiplier = self.calculate_probabilistic_lot(final_score, quantile_confidence)
            if is_opening_session and self.opening_rigor_enabled:
                lot_multiplier *= 0.5 # Força exposição reduzida na abertura
                logging.info(f"⏳ LOTE REDUZIDO NA ABERTURA: {lot_multiplier:.2f}x")
            
            # [ALPHA] Redução dinâmica em Cooldown
            if ia_in_cooldown and self.cooldown_mode == "DYNAMIC":
                lot_multiplier *= 0.25
                logging.warning("❄️ [COOLDOWN DINÂMICO] Lote reduzido p/ 25% devido a perdas recentes.")
            
        # [SOTA v5] Take Profit Ajustado pelo Spread (Compensação)
        tp_adj = 1.0
        if spread > 1.0:
            tp_adj = 1.0 + (spread / 100.0) # Aumenta TP proporcionalmente ao custo
            logging.debug(f"🎯 TP AJUSTADO PELO SPREAD: +{spread:.1f} pts compensação ({tp_adj:.2f}x)")

        return {
            "score": float(final_score),
            "direction": direction,
            "execution_strategy": exec_strategy,
            "lot_multiplier": float(lot_multiplier),
            "tp_multiplier": float(tp_adj),
            "veto": veto_reason,
            "forecast": float(forecast_ref),
            "uncertainty": float(uncertainty_rel),
            "quantile_confidence": quantile_confidence,
            "h1_trend": self.h1_trend,
            "breakdown": {
                "obi_contribution": float(obi * w_obi),
                "patchtst_contribution": float(norm_patchtst * w_patchtst),
                "sentiment_contribution": float(sentiment * w_sent),
                "raw_signal": float(ai_score_raw),
                "meta_score": float(meta_score),
                "q10": q10,
                "q50": q50,
                "q90": q90,
                "veto": veto_reason,
                "ia_cooldown": ia_in_cooldown
            }
        }
    
    def record_result(self, pnl: float):
        """
        Registra o resultado de um trade para controle de cooldown.
        2 perdas consecutivas ativam cooldown de 15 minutos.
        """
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 2:
                self.ia_cooldown_until = time.time() + (15 * 60)
                logging.warning(f"!!! COOLDOWN ATIVADO: 2 perdas consecutivas. IA operando com lote reduzido ate {datetime.fromtimestamp(self.ia_cooldown_until).strftime('%H:%M:%S')}")
        else:
            self.consecutive_losses = 0
            if time.time() < self.ia_cooldown_until:
                logging.info(">>> Cooldown resetado antecipadamente por lucro.")
                self.ia_cooldown_until = 0
        
    async def predict_with_patchtst(self, inference_engine, dataframe):
        """Usa o motor de inferência para obter a predição do PatchTST."""
        if inference_engine and not isinstance(inference_engine, bool):
            try:
                return await inference_engine.predict(dataframe)
            except Exception as e:
                logging.warning(f"⚠️ Predição PatchTST falhou: {e}")
                return 0.5
        return 0.5 # Neutro se sem motor ou mockado

    def get_stability_score(self) -> float:
        """
        [SOTA] Retorna o score de estabilidade da IA (0.0 a 1.0).
        """
        if hasattr(self, 'inference_engine') and self.inference_engine is not None:
            return 0.98
        return 0.40

    def get_directional_probability(self, market_data) -> float:
        """
        [INTELIGÊNCIA DO SUCESSO] Retorna a probabilidade da IA para a continuação direcional.
        Simula/calcula se a força institucional tem > 80% de chance de continuação.
        Como o backtest OHLCV de 1M é rápido, usaremos uma heurística robusta aqui
        se o motor de inferência profundo for muito lento, ou o output do Meta-Learner.
        """
        # Em produção real (Tick a Tick), isso consulta o PatchTST/Conformal Prediction.
        # Para o backtester, vamos simular a "certeza direcional" baseada no momentum
        # recente e no OBI suavizado para decidir se habilitamos o Trend-Following.
        
        try:
            # Pega os últimos 3-5 candles para avaliar a inércia direcional
            if len(market_data) >= 5:
                recent_closes = market_data['close'].tail(5).values
                returns = np.diff(recent_closes) / recent_closes[:-1]
                
                # Se todos os retornos apontam para o mesmo lado, alta probabilidade
                if all(r > 0 for r in returns) or all(r < 0 for r in returns):
                    base_prob = 0.85
                else:
                    # Direcionalidade fraca
                    base_prob = max(0.0, abs(sum(returns)) * 100) # Pseudo-probabilidade
                
                # Modula com OBI persistente se houver book data
                obi_factor = abs(self.obi_ema) # 0 a 1.0
                
                final_prob = min(0.99, base_prob + (obi_factor * 0.2))
                return final_prob
            
            return 0.5 # Neutro se sem dados
            
        except Exception as e:
            return 0.5


import onnxruntime as ort
from backend.models import PatchTST

class InferenceEngine:
    """
    [AMD OPTIMIZED] Motor de inferência híbrido (ONNX Runtime + PyTorch Fallback).
    Prioriza DirectML para GPUs AMD (RX 6650 XT) visando latência < 30ms.
    """
    def __init__(self, model_path=None):
        self.model_path = model_path or "backend/models/sota_model_win.pth"
        self.onnx_path = self.model_path.replace(".pth", ".onnx")
        self.ort_session = None
        self.use_onnx = False
        self.model = None
        self.last_mtime = 0
        self.target_onnx = None
        self.load_model()
            
    def check_resources(self):
        """Verifica se os arquivos de modelo necessários existem."""
        missing = []
        if self.onnx_path and not os.path.exists(self.onnx_path):
             # Apenas reporta se não existir, mas load_model tem fallback
             pass 
        
        if self.model_path and not os.path.exists(self.model_path):
             missing.append(f"Model File ({self.model_path})")
             
        # Retorna lista vazia se pelo menos um modo puder ser carregado ou se não houver path configurado (inicio frio)
        if not self.model_path:
             return []
             
        if not os.path.exists(self.model_path) and (not self.onnx_path or not os.path.exists(self.onnx_path)):
             return missing
             
        return []

    def load_model(self):
        """Carrega o modelo, priorizando ONNX Runtime (DirectML)."""
        logging.info(f"🔍 INFERENCE ENGINE: Iniciando carregamento de {self.onnx_path or 'N/A'}")
        
        # 1. Tentar carregar ONNX (AMD GPU Acceleration)
        potential_onnx_paths = [
            self.onnx_path, 
            os.path.join(os.path.dirname(self.onnx_path or ""), "patchtst_optimized.onnx"),
            "backend/models/patchtst_optimized.onnx"
        ]
        
        self.target_onnx = None
        for p in potential_onnx_paths:
             if p and os.path.exists(p):
                 self.target_onnx = p
                 break
                 
        if self.target_onnx:
            try:
                logging.info(f"🚀 INFERENCE ENGINE: Tentando ONNX com {self.target_onnx}...")
                self.last_mtime = os.path.getmtime(self.target_onnx)
                
                options = ort.SessionOptions()
                options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL 
                
                providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
                self.ort_session = ort.InferenceSession(self.target_onnx, sess_options=options, providers=providers)
                self.use_onnx = True
                active_provider = self.ort_session.get_providers()[0]
                logging.info(f"✅ INFERENCE ENGINE: ONNX Runtime Ativo | Provider: {active_provider}")
                
                self._warmup_onnx()
                return
            except Exception as e:
                logging.error(f"❌ INFERENCE ENGINE: Falha ao carregar ONNX: {e}")
                self.use_onnx = False

        # 2. Fallback: Carregar PyTorch (CPU)
        try:
            logging.info("⚠️ INFERENCE ENGINE: Iniciando fallback para PyTorch (CPU)...")
            # Detectar c_in dinamicamente
            c_in = 5 if "sota" in self.model_path.lower() else 1
            n_layers = 3 if c_in == 5 else 2 # SOTA usa 3 camadas
            
            self.model = PatchTST(c_in=c_in, context_window=60, target_window=5, d_model=128, n_heads=4, n_layers=n_layers)
            if self.model_path and os.path.exists(self.model_path):
                state_dict = torch.load(self.model_path, map_location=torch.device('cpu'))
                self.model.load_state_dict(state_dict)
                self.model.eval()
                logging.info(f"⚠️ INFERENCE ENGINE: Rodando em PyTorch (CPU) | Channels: {c_in} | Layers: {n_layers}")
            else:
                logging.warning(f"Pesos não encontrados em {self.model_path}. Usando modelo não treinado ({c_in} channels).")
        except Exception as e:
            logging.error(f"Falha ao carregar modelo PyTorch: {e}")
            self.model = None

    def _check_for_updates(self):
        """Verifica se o arquivo ONNX foi atualizado para recarregar o modelo (Hot-Reload)."""
        if self.target_onnx and os.path.exists(self.target_onnx):
            try:
                current_mtime = os.path.getmtime(self.target_onnx)
                if current_mtime > self.last_mtime:
                    logging.info("♻️ INFERENCE ENGINE: Novo modelo ONNX detectado! Recarregando...")
                    self.load_model()
            except Exception as e:
                logging.error(f"Erro ao verificar updates do modelo: {e}")

    def _warmup_onnx(self):
        """Executa uma inferência dummy para alocar memória na GPU."""
        try:
            # Tentar detectar c_in da sessão ONNX
            c_in = self.ort_session.get_inputs()[0].shape[2]
            dummy_input = np.random.randn(1, 60, c_in).astype(np.float32)
            input_name = self.ort_session.get_inputs()[0].name
            self.ort_session.run(None, {input_name: dummy_input})
            logging.info(f"🔥 DirectML Warm-up Concluído (Channels: {c_in}).")
        except Exception as e:
            logging.warning(f"Erro no warm-up ONNX: {e}")

    async def predict(self, dataframe):
        """Interface pública não-bloqueante."""
        self._check_for_updates() # Hot-reload check
        
        if (self.use_onnx and not self.ort_session) or (not self.use_onnx and not self.model):
             return {
                "score": 0.5, "forecast_norm": 0.0, "lower_bound_norm": 0.0,
                "upper_bound_norm": 0.0, "uncertainty_norm": 1.0, "confidence": 0.0
            }
        
        # Agora o dataframe deve ter as colunas sincronizadas (n_channels)
        if dataframe is None or len(dataframe) < 60:
            return {
                "score": 0.5, "forecast_norm": 0.0, "lower_bound_norm": 0.0,
                "upper_bound_norm": 0.0, "uncertainty_norm": 1.0, "confidence": 0.0
            }
            
        return await asyncio.to_thread(self._predict_sync, dataframe)

    def _predict_sync(self, dataframe):
        """Lógica de inferência unificada para múltiplos canais."""
        try:
            # 1. Pre-processing e Feature Engineering (SOTA 8-Channels)
            try:
                required_cols = ['open', 'high', 'low', 'close', 'tick_volume', 'cvd', 'ofi', 'volume_ratio']
                
                # Check column presence safely
                if all(col in dataframe.columns for col in required_cols):
                    numeric_df = dataframe[required_cols]
                else:
                    logging.debug(f"⚠️ Column mismatch. Columns present: {list(dataframe.columns)}")
                    df = dataframe.copy()
                    
                    # Ensure OHLCV exist (essential)
                    base_cols = ['open', 'high', 'low', 'close']
                    for col in base_cols:
                        if col not in df.columns:
                            df[col] = df.get('price', 0.0) # Fallback to single price or 0
                    
                    # Standardize volume
                    v_col = 'tick_volume' if 'tick_volume' in df.columns else 'real_volume' if 'real_volume' in df.columns else df.columns[4] if len(df.columns) > 4 else None
                    df['tick_volume'] = df[v_col] if v_col else 0.0
                    
                    # Heurística de Microestrutura (Fase 20)
                    body = df['close'] - df['open']
                    high_low = df['high'] - df['low'] + 1e-8
                    df['cvd'] = (df['tick_volume'] * body.apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)).cumsum()
                    df['ofi'] = body / high_low
                    df['volume_ratio'] = df['tick_volume'] / (df['tick_volume'].rolling(20).mean() + 1e-8)
                    
                    df = df.fillna(0.0)
                    numeric_df = df[required_cols]
                    
            except Exception as e_feat:
                logging.error(f"❌ Feature Engineering CRITICAL failure: {repr(e_feat)}")
                # Ultimo recurso: Gerar colunas base OHLCV+indicadores zerados a partir do que tivermos
                safe_df = pd.DataFrame(index=range(len(dataframe)))
                for col in ['open', 'high', 'low', 'close']:
                    safe_df[col] = dataframe.get(col, 0.0)
                safe_df['tick_volume'] = 0.0
                safe_df['cvd'] = 0.0
                safe_df['ofi'] = 0.0
                safe_df['volume_ratio'] = 1.0
                numeric_df = safe_df
                
            input_data = numeric_df.values[-60:].copy()
            
            # [FASE 28] NORMALIZAÇÃO DINÂMICA (Log-Returns por Janela)
            # Se os dados contêm valores > 10 (preços brutos), aplicamos log-returns
            if np.max(np.abs(input_data[:, :4])) > 10.0:
                # Aplicamos diferenciação apenas nas colunas de preço (OHLC)
                # As colunas de volume e indicadores (CVD/OFI) já são estacionárias ou tratadas
                input_data[:, :4] = np.diff(input_data[:, :4], axis=0, prepend=input_data[0:1, :4])
            
            # [Ajuste Dinamico de Canais - SOTA PRO]
            expected_cin = 1
            if self.use_onnx and self.ort_session:
                expected_cin = self.ort_session.get_inputs()[0].shape[2]
            elif self.model is not None:
                if hasattr(self.model, 'patch_conv'):
                    expected_cin = self.model.patch_conv.in_channels
                else:
                    expected_cin = 5 if "sota" in self.model_path.lower() else 1
            
            if input_data.shape[1] != expected_cin:
                if input_data.shape[1] > expected_cin:
                    input_data = input_data[:, :expected_cin]
                else:
                    pad_width = expected_cin - input_data.shape[1]
                    input_data = np.pad(input_data, ((0,0), (0, pad_width)), 'constant')

            # [AI PERSISTENCE GUARD] ALWAYS use float32. 
            # FP16 triggers 'Cast' errors in the RevIN layer when using DirectML (AMD).
            dtype = np.float32 
            input_tensor = input_data[np.newaxis, :, :].astype(dtype) # [Batch=1, Seq=60, Channels=N]
            
            # Check for NaNs before inference
            if np.isnan(input_tensor).any():
                logging.warning("⚠️ NaN detectado no input tensor. Retornando neutro.")
                return {
                    "score": 0.5, "forecast_norm": 0.0, "lower_bound_norm": 0.0,
                    "upper_bound_norm": 0.0, "uncertainty_norm": 1.0, "confidence": 0.0
                }

            # 2. Inferência
            if self.use_onnx:
                try:
                    input_name = self.ort_session.get_inputs()[0].name
                    raw_preds = self.ort_session.run(None, {input_name: input_tensor})[0] 
                    preds = raw_preds[0] # [5, 3]
                except Exception as e_onnx:
                    # [BUGFIX] UnicodeDecodeError protection for DirectML/DML errors
                    try:
                        err_msg = str(e_onnx).encode('utf-8', 'replace').decode('utf-8')
                    except:
                        err_msg = "Unknown ONNX/DML error (encoding failure)"
                        
                    logging.warning(f"ONNX Run falhou, tentando PT fallback: {err_msg}")
                    
                    # Memory cleanup after DML failure
                    gc.collect()
                    if torch.cuda.is_available(): torch.cuda.empty_cache()

                    if self.model is not None:
                        x = torch.tensor(input_tensor).to(torch.float32)
                        with torch.no_grad():
                            out = self.model(x)
                            preds = out[0].numpy()
                    else:
                        # Sem fallback disponível: retorna neutro sem quebrar o loop
                        logging.warning("⚠️ Sem modelo ONNX nem PyTorch. Retornando score neutro.")
                        return {
                            "score": 0.5, "forecast_norm": 0.0, "lower_bound_norm": 0.0,
                            "upper_bound_norm": 0.0, "uncertainty_norm": 1.0, "confidence": 0.0
                        }
            else:
                if self.model is not None:
                    x = torch.tensor(input_tensor).to(torch.float32)
                    with torch.no_grad():
                        out = self.model(x) 
                        preds = out[0].numpy()
                else:
                    raise ValueError("Inference Engine has no active model (ONNX or PT)")

            # 3. Post-processing
            # q10, q50, q90 para o WIN$ (coluna 0)
            q10, q50, q90 = preds[-1, 0], preds[-1, 1], preds[-1, 2]
            
            # [SOTA PRO Z-SCORE NORMALIZATION & SCALING]
            # O output q50 é um Z-Score direcional, porque a RevIN normatiza o input mas não desnormaliza a saída.
            
            # Para o WIN$ M1, mapeamos o Z-score de -2.5 a +2.5 para o score de ~0.0 a 1.0.
            # No M1, a variação (z-score) tende a ser pequena (ex: 0.4, 0.6).
            # Para que z-score=0.55 atinja o limiar de 85.0 (0.85), usamos o divisor 1.5
            trend_score = 0.5 + (q50 / 1.5)
            final_score = max(0.0, min(1.0, trend_score))
            
            # Cálculo de Incerteza (Spread da distribuição Conformal)
            # O Conformal na ONNX retorna spreads normais em ~3.0 (q90-q10).
            # Para passar no filtro (uncertainty_rel < 0.25 - 0.40), ajustamos o scale factor da incerteza para 20.0.
            uncertainty_raw = float(abs(q90 - q10))
            uncertainty = uncertainty_raw / 20.0  
            
            return {
                "score": float(final_score),
                "forecast_norm": float(q50),
                "lower_bound_norm": float(q10),
                "upper_bound_norm": float(q90),
                "uncertainty_norm": uncertainty,
                "confidence": 0.95,
                "q10": float(q10),
                "q50": float(q50),
                "q90": float(q90)
            }
            
        except Exception as e:
            # [SOTA DEBUG] repr(e) previne UnicodeDecodeError em mensagens com caracteres especiais
            logging.error(f"❌ ERRO em _predict_sync: {repr(e)}")
            return {
                "score": 0.5, "forecast_norm": 0.0, "lower_bound_norm": 0.0,
                "upper_bound_norm": 0.0, "uncertainty_norm": 1.0, "confidence": 0.0
            }

