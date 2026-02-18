import google.generativeai as genai
import os
import logging
import numpy as np
import asyncio
import json
from backend.microstructure import MicrostructureAnalyzer # HFT v2.0
from backend.news_collector import NewsCollector # Plano Diretor 2.0
from backend.meta_learner import MetaLearner # HFT v2.0 Meta-Learner
from sklearn.cluster import KMeans # Keep KMeans for regime_model
from dotenv import load_dotenv
import torch # Import necessário para InferenceEngine

load_dotenv()

# Configuração da API Google Gemini
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    logging.warning("GOOGLE_API_KEY não encontrada no .env. AI de Sentimento desabilitada.")

class AICore:
    def __init__(self):
        # [FASE 1] Gemini 2.5 Flash com Zero-Hallucination Config
        if api_key:
            generation_config = {
                "temperature": 0.0,        # Zero criatividade (determinístico)
                "top_p": 0.1,             # Apenas respostas mais prováveis
                "response_mime_type": "application/json"  # Força saída JSON
            }
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash',
                generation_config=generation_config
            )
        else:
            self.model = None
        self.latest_sentiment_score = 0.0
        self.obi_ema = 0.5 # Valor inicial neutro
        self.ema_alpha = 0.2 # Fator de suavização (aproximadamente 1s em loops de 100ms)
        self.regime_model = KMeans(n_clusters=3, n_init=10) # 0: Baixa Vol, 1: Tendência, 2: Ruído
        self.regime_history = []
        self.regime_counter = 0
        self.prev_book = None
        self.toxic_flow_score = 0.0
        self.last_news_update = 0
        self.micro_analyzer = MicrostructureAnalyzer()
        self.meta_learner = MetaLearner() # Inicializa Meta-Learner
        self.news_collector = NewsCollector(max_age_minutes=30) # Plano Diretor 2.0

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

    async def update_sentiment(self):
        """
        Consulta o Gemini para obter o score de sentimento (-1 a 1) com reliability scoring.
        Versão Full-Stack Quant: Persona Engenheiro de Risco + Refresh 30s.
        """
        if not self.model:
            return 0.0
            
        now = asyncio.get_event_loop().time()
        # [MODO SNIPER] Atualizar a cada 30 segundos (antes era 300)
        if now - self.last_news_update < 30 and self.latest_sentiment_score != 0:
            return self.latest_sentiment_score

        # [PLANO DIRETOR 2.0] Usar NewsCollector ao invés de news_feed.txt
        news_headlines = await self.news_collector.get_pulse_async()
        
        # Se nenhuma notícia fresca/relevante, retornar neutro
        if not news_headlines:
            logging.debug("📰 Sem notícias frescas/relevantes. Mantendo NEUTRO.")
            self.latest_sentiment_score = 0.0
            self.last_news_update = now
            return 0.0
        
        # [FASE 3] Prompt 'Engenheiro de Risco'
        prompt = f"""
ATUE COMO UM ENGENHEIRO DE RISCO SÊNIOR PARA UMA MESA DE HFT.

OBJETIVO: Detectar ASSIMETRIAS DE RISCO baseadas em FATOS.
Sua missão NÃO é prever o futuro, mas sim classificar o RISCO IMEDIATO.

FONTE DE DADOS:
{news_headlines}

PROTOCOLO DE ANÁLISE (RIGOR MILITAR):
1. SEPARAÇÃO FATO vs RUÍDO: Ignore opiniões de analistas. Foque em DADOS (Payroll, IPCA, Selic, Fusões).
2. CLASSIFICAÇÃO DE RISCO:
   - "EXTREME": Evento sistêmico (ex: Guerra, Quebra de Banco, Circuit Breaker).
   - "HIGH": Dado macro muito acima/abaixo do esperado, mudança de juros não precificada.
   - "MEDIUM": Notícia corporativa relevante (Blue Chips), falas de Banco Central.
   - "LOW": Ruído normal de mercado.
3. SENTIMENTO MATEMÁTICO:
   - -1.0 (Pânico/Venda) a +1.0 (Euforia/Compra).

SAÍDA OBRIGATÓRIA (JSON):
{{ "score": 0.0, "reliability": "high/medium/low", "risk_classification": "EXTREME/HIGH/MEDIUM/LOW", "fact_check": "resumo do fato" }}
"""
        
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            
            # Parsing JSON
            data = json.loads(response.text)
            score = float(data.get("score", 0.0))
            reliability = data.get("reliability", "low")
            risk_class = data.get("risk_classification", "LOW")
            fact_check = data.get("fact_check", "N/A")
            
            # [FILTRO DE ROBUSTEZ] Se IA não tem certeza ou risco é baixo demais para trade de notícia, moderar score
            if reliability == "low":
                self.latest_sentiment_score = 0.0
                self.last_news_update = now
                return 0.0
            
            # Clamp de segurança
            score = max(-1.0, min(1.0, score))
            
            self.latest_sentiment_score = score
            self.last_news_update = now
            logging.info(f"✅ Risk Engine: {score:.2f} | Class: {risk_class} | {fact_check[:60]}...")
            return score
            
        except Exception as e:
            logging.error(f"❌ Erro na IA (Falha de Grounding): {e}")
            return 0.0  # Neutro em caso de erro (segurança)

    def detect_spoofing(self, order_book, time_sales):
        """
        Detecta spoofing comparando volume do book com histórico recente.
        Implementa a regra de 'Toxic Flow': sumiço de ordens grandes sem trade.
        """
        if not order_book or (not order_book.get('bids') and not order_book.get('asks')):
            return 0.5
            
        # 1. OBI (Order Book Imbalance) básico
        total_bid = sum(item['volume'] for item in order_book.get('bids', []))
        total_ask = sum(item['volume'] for item in order_book.get('asks', []))
        
        current_obi = 0.5
        if total_bid + total_ask > 0:
            current_obi = (total_bid - total_ask) / (total_bid + total_ask)
        
        # Suavização EMA
        self.obi_ema = (current_obi * self.ema_alpha) + (self.obi_ema * (1 - self.ema_alpha))
        
        # 2. Detecção de Toxic Flow (Remoção Súbita vs Execução Real)
        if self.prev_book is not None:
            # Cálculo correto com base na estrutura dict {"bids": [], "asks": []}
            prev_bid = sum(item['volume'] for item in self.prev_book.get('bids', []))
            prev_ask = sum(item['volume'] for item in self.prev_book.get('asks', []))
            
            # Cálculo exato de agressão (Volume Executado por Lado)
            # time_sales deve ser filtrado se possível, ou usar heurística
            # Assumindo que DataCollector entrega 'real_volume' e 'flags'
            # Se não tiver flags, usamos volume total como proxy conservador
            
            sell_aggression_vol = 0 # Agressão de Venda (consome Bid)
            buy_aggression_vol = 0 # Agressão de Compra (consome Ask)
            
            if time_sales is not None and not time_sales.empty:
                # Na B3, TICK_FLAG_BUY (agressão compra) e TICK_FLAG_SELL (agressão venda)
                # 0x100: BUY, 0x200: SELL (Flags MT5)
                buy_aggression_vol = time_sales[time_sales['flags'] & 0x100]['volume'].sum() if 'flags' in time_sales.columns else 0
                sell_aggression_vol = time_sales[time_sales['flags'] & 0x200]['volume'].sum() if 'flags' in time_sales.columns else 0
                real_volume = buy_aggression_vol + sell_aggression_vol
            else:
                real_volume = 0
            
            # --- LÓGICA ALPHA-X: CANCELLATION RATE ---
            # Comparamos quanto do volume sumiu (delta) vs quanto foi de fato executado (aggression)
            delta_bid = max(0, prev_bid - total_bid)
            delta_ask = max(0, prev_ask - total_ask)
            
            # Cancellation Rate: Proporção do volume removido que NÃO foi trade
            # Se sumiu 1000 e trade foi 100, 900 foram cancelados -> CR = 0.9
            cr_bid = (delta_bid - sell_aggression_vol) / delta_bid if delta_bid > 0 else 0
            cr_ask = (delta_ask - buy_aggression_vol) / delta_ask if delta_ask > 0 else 0

            # Thresholds Dinâmicos (HFT v2.1)
            threshold_bid = max(20, total_bid * 0.1)
            threshold_ask = max(20, total_ask * 0.1)
            
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
            return int(self.regime_model.predict(current_state)[0])
        except:
            return 0

    def calculate_decision(self, obi, sentiment, patchtst_score, regime=0, atr=0.0, volatility=0.0, hour=0):
        """
        Calcula a decisão final de trading baseada em múltiplos fatores ponderados.
        
        Args:
            obi: Order Book Imbalance (-1.0 a 1.0)
            sentiment: Análise de Notícias (-1.0 a 1.0)
            patchtst_score: Predição de Preço (0.0 a 1.0, onde >0.5 é Alta)
            regime: Regime de mercado (0: Baixa Vol, 1: Tendência, 2: Ruído)
            atr: Average True Range (para Meta-Learner)
            volatility: Volatilidade (para Meta-Learner)
            hour: Hora do dia (para Meta-Learner)
            
        Returns:
            dict: {
                "score": float (0-100),
                "direction": str ("BUY" | "SELL" | "NEUTRAL"),
                "breakdown": dict (detalhes do cálculo)
            }
        """
        # 1. Normalização de Inputs para Range (-1.0 a 1.0)
        # OBI já é -1 a 1
        # Sentiment já é -1 a 1
        
        # PatchTST vem 0.0 a 1.0 (0.5 é neutro).
        uncertainty_width = 0.0
        if isinstance(patchtst_score, dict):
            uncertainty_width = patchtst_score.get("uncertainty", 0.0)
            norm_patchtst = (patchtst_score.get("score", 0.5) - 0.5) * 2
        else:
            norm_patchtst = (patchtst_score - 0.5) * 2 
        
        # 2. Pesos Dinâmicos (HFT v2.1: AlphaX - Transformer First)
        # O modelo Transformer (PatchTST) é o âncora contextual principal.
        w_patchtst = 0.50
        w_obi = 0.30
        w_sent = 0.20

        # [VETO POR INCERTEZA] Se PatchTST estiver muito incerto, anular peso
        if uncertainty_width > 0.15:
            logging.warning(f"CONFORMAL VETO: PatchTST incerto ({uncertainty_width:.4f}).")
            w_patchtst = 0.0
            w_obi = 0.70 # Backup para Microestrutura (OBI)
            w_sent = 0.30
        elif regime == 0: # Consolidação / Ruído -> Equilíbrio Fluxo/Predição
            w_obi = 0.50
            w_patchtst = 0.30
            w_sent = 0.20
        elif regime == 1: # Tendência Clara -> Maximizar Transformer
            w_obi = 0.20
            w_patchtst = 0.70
            w_sent = 0.10
        
        # 3. Cálculo do Sinal Composto (AI_Score Bruto)
        composite_signal = (obi * w_obi) + (norm_patchtst * w_patchtst) + (sentiment * w_sent)
        
        # 4. Score Final (Magnitude Absoluta 0-100)
        # Convert composite_signal (-1 to 1) to a 0-100 scale
        ai_score_raw = (composite_signal + 1) * 50
        ai_score_raw = max(0.0, min(100.0, ai_score_raw))

        # --- HFT v2.0: Meta-Learner (XGBoost) para refinar a decisão ---
        # Features esperadas: [ATR, OBI, Sentiment, Volatility, Hour, AI_Score_Raw]
        meta_features = [atr, obi, sentiment, volatility, hour, ai_score_raw]
        
        # [HFT v2.1] Sanitize inputs: substituir NaN ou Inf por 0.0 para evitar crash no XGBoost
        meta_features = [x if np.isfinite(x) else 0.0 for x in meta_features]
        
        # [HFT v2.1] Fallback se o modelo não estiver treinado/carregado
        try:
            meta_proba = self.meta_learner.predict_proba(meta_features) # Returns probability 0.0-1.0
        except Exception as e:
            logging.warning(f"Meta-Learner fallback: Usando raw signal (Motive: {e})")
            meta_proba = ai_score_raw / 100.0
        
        # Converter probabilidade para score (0-100)
        meta_score = meta_proba * 100.0

        # A decisão final é baseada no meta_score
        final_score = meta_score
        
        # 5. Direção
        direction = "NEUTRAL"
        if final_score > 55: # Limiar para BUY (ajustável)
            direction = "BUY"
        elif final_score < 45: # Limiar para SELL (ajustável)
            direction = "SELL"
            
        return {
            "score": final_score,
            "direction": direction,
            "breakdown": {
                "obi_contribution": obi * w_obi,
                "patchtst_contribution": norm_patchtst * w_patchtst,
                "sentiment_contribution": sentiment * w_sent,
                "raw_signal": composite_signal,
                "ai_score_raw": ai_score_raw,
                "meta_score": meta_score
            }
        }
        
    async def predict_with_patchtst(self, inference_engine, dataframe):
        """Usa o motor de inferência para obter a predição do PatchTST."""
        if inference_engine:
            return await inference_engine.predict(dataframe)
        return 0.5 # Neutro se sem motor

from backend.models import PatchTST, PointQuantileLoss, ConformalPrediction

class InferenceEngine:
    """Motor de inferência isolado para carregar pesos .pth"""
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.model = None
        if model_path:
            self.load_model()

    def check_resources(self):
        """Verifica se os arquivos necessários existem."""
        missing = []
        if self.model_path and not os.path.exists(self.model_path):
            missing.append(f"Pesos do Modelo ({self.model_path})")
        
        # Verificar news_feed.txt também (embora seja do AICore, podemos checar aqui ou no main)
        return missing

    def load_model(self):
        """Carrega a arquitetura e os pesos do modelo PyTorch."""
        try:
            # Configuração precisa bater com train_model.py
            self.model = PatchTST(seq_len=60, d_model=128, n_heads=4, num_layers=2)
            if self.model_path and os.path.exists(self.model_path):
                state_dict = torch.load(self.model_path, map_location=torch.device('cpu'))
                self.model.load_state_dict(state_dict)
                self.model.eval()
                logging.info(f"Pesos do PatchTST carregados de: {self.model_path}")
            else:
                logging.warning(f"Pesos não encontrados em {self.model_path}. Usando modelo não treinado.")
        except Exception as e:
            logging.error(f"Falha ao carregar modelo: {e}")
            self.model = None
            
        # Inicializa Conformal Prediction (Calibração zerada por padrão)
        self.cp = ConformalPrediction(alpha=0.1)

    async def predict(self, dataframe):
        """Executa a inferência real usando o modelo PatchTST (Non-blocking wrapper)."""
        if self.model is None or dataframe is None or len(dataframe) < 60:
            return 0.5 # Neutro
            
        return await asyncio.to_thread(self._predict_sync, dataframe)

    def _predict_sync(self, dataframe):
        """Lógica síncrona de inferência (CPU-bound)."""
        try:
            # 1. Extrair fechamentos e converter para tensor
            data = dataframe['close'].values[-60:]
            
            # 2. Normalização Z-Score (Simple)
            mean = data.mean()
            std = data.std() + 1e-8
            norm_data = (data - mean) / std
            
            # 3. Model forward pass
            x = torch.tensor(norm_data, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
            with torch.no_grad():
                preds = self.model(x).squeeze(0).numpy() # Shape [3] (q10, q50, q90)
                
            # Converter predição central (q50) para score de tendência
            last_val = norm_data[-1]
            q10, q50, q90 = preds
            
            # --- Aplicação da Conformal Prediction ---
            # Calibra o intervalo com o q_hat (se calibrado)
            lower_bound, upper_bound = self.cp.predict_interval(q10, q90)
            
            # Score de tendência baseado no quantil central
            # Se q50 > last_val -> Alta
            trend_score = 0.5 + (q50 - last_val) * 2
            
            # Incerteza Robusta: Largura do intervalo calibrado
            # Se o intervalo [lower, upper] for muito largo, incerteza é alta
            uncertainty_width = upper_bound - lower_bound
            
            # Penalidade de confiança baseada na largura (ajustar sensibilidade conforme dados)
            # Ex: Se largura > 2 desvios padrão, confiança cai muito
            confidence = 1.0 / (1.0 + uncertainty_width)
            
            # CORREÇÃO: Confiança deve puxar o score para 0.5 (Neutro), não para 0.0
            # Se Confiança = 1.0 -> final = trend
            # Se Confiança = 0.0 -> final = 0.5
            final_score = 0.5 + (trend_score - 0.5) * confidence
            
            return {
                "score": float(final_score),
                "uncertainty": float(uncertainty_width)
            }
            
            return max(0.0, min(1.0, final_score))
            
        except Exception as e:
            logging.error(f"Erro na inferência PatchTST: {e}")
            return 0.5

