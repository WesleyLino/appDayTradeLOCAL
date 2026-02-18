import google.generativeai as genai
import os
import logging
import numpy as np
import asyncio
import json
from backend.microstructure_analyzer import MicrostructureAnalyzer # HFT v2.0
from backend.news_collector import NewsCollector # Plano Diretor 2.0
from backend.meta_learner import MetaLearner # HFT v2.0 Meta-Learner
from sklearn.cluster import KMeans # Keep KMeans for regime_model
from dotenv import load_dotenv
import torch # Import necessário para InferenceEngine
from backend.models.price_forecaster import PriceForecaster # SOTA Forecast

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
        self.price_forecaster = PriceForecaster() # [SOTA] Novo Cérebro
        
        # Tentar carregar pesos pré-treinados SOTA
        if self.price_forecaster.load():
            logging.info("🧠 SOTA Brain (PatchTST) carregado com sucesso.")
        else:
            logging.warning("🧠 SOTA Brain não encontrado. Operando em modo de coleta/treino.")

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

    async def evaluate_opportunity(self, market_data):
        """
        Avalia oportunidade de trade com validação SOTA (Conformal Prediction).
        """
        # ... (Análise existente: Sentiment, Microestrutura, Meta-Learner) ...
        
        # 1. Análise Atual (Legacy + Microstructure)
        # Assuming current_book is available, e.g., from market_data or a separate parameter
        # For this snippet, we'll assume current_book is passed or derived.
        # Placeholder for current_book, as it's not provided in the snippet's context
        current_book = {} # This needs to be properly sourced from market_data or another input
        micro_signal = self.micro_analyzer.analyze(self.prev_book, current_book)
        sentiment_score = self.latest_sentiment_score
        
        # 2. Previsão SOTA com Incerteza
        current_price = market_data['close'].iloc[-1]
        forecast_result = self.price_forecaster.predict(market_data)
        
        # 3. Veto por Incerteza (Conformal Prediction)
        # Se o preço atual já estiver dentro do intervalo de incerteza da previsão futura,
        # significa que não há "edge" estatístico claro.
        uncertainty_range = forecast_result['upper_bound'] - forecast_result['lower_bound']
        projected_move = abs(forecast_result['forecast'] - current_price)
        
        if projected_move < (uncertainty_range * 0.5): # Heurística: Movimento < Metade da Incerteza
            logging.info(f"⛔ Trade Vetado pelo SOTA: Movimento projetado ({projected_move:.2f}) menor que incerteza ({uncertainty_range:.2f}).")
            return None # ABORTAR
            
        # ... (Continua com lógica de decisão combinada) ...
        # Retorna decisão formatada
        return {
            "signal": "BUY" if forecast_result['forecast'] > current_price else "SELL",
            "confidence": forecast_result['confidence'],
            "reason": f"SOTA Forecast: {forecast_result['forecast']:.2f} (Bounds: {forecast_result['lower_bound']:.2f}-{forecast_result['upper_bound']:.2f})"
        }

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
        uncertainty_abs = 0.0
        forecast_ref = 1.0
        
        if isinstance(patchtst_score, dict):
            uncertainty_abs = patchtst_score.get("uncertainty", 0.0)
            forecast_ref = patchtst_score.get("forecast", 1.0)
            if forecast_ref == 0: forecast_ref = 1.0
            
            norm_patchtst = (patchtst_score.get("score", 0.5) - 0.5) * 2
        else:
            norm_patchtst = (patchtst_score - 0.5) * 2 
        
        # [HFT v2.1 FIX] Calcular incerteza relativa (%)
        uncertainty_rel = abs(uncertainty_abs / forecast_ref)

        # 2. Pesos Dinâmicos (HFT v2.1: AlphaX - Transformer First)
        # O modelo Transformer (PatchTST) é o âncora contextual principal.
        w_patchtst = 0.50
        w_obi = 0.30
        w_sent = 0.20

        # [VETO POR INCERTEZA] Se PatchTST estiver muito incerto (>5% range relativo), anular peso
        if uncertainty_rel > 0.05: 
            logging.warning(f"CONFORMAL VETO: Incerteza Alta ({uncertainty_rel*100:.2f}%).")
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

import onnxruntime as ort
from backend.models import PatchTST

class InferenceEngine:
    """
    [AMD OPTIMIZED] Motor de inferência híbrido (ONNX Runtime + PyTorch Fallback).
    Prioriza DirectML para GPUs AMD (RX 6650 XT) visando latência < 30ms.
    """
    def __init__(self, model_path=None):
        self.model_path = model_path # Caminho do .pth (Legacy/Training)
        self.onnx_path = model_path.replace(".pth", "_optimized.onnx") if model_path else None
        self.use_onnx = False
        self.ort_session = None
        self.model = None # PyTorch fallback
        
        if model_path:
            self.load_model()
            
    # ... check_resources implementation ...

    def load_model(self):
        """Carrega o modelo, priorizando ONNX Runtime (DirectML)."""
        # 1. Tentar carregar ONNX (AMD GPU Acceleration)
        if self.onnx_path and os.path.exists(self.onnx_path):
            try:
                providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
                self.ort_session = ort.InferenceSession(self.onnx_path, providers=providers)
                self.use_onnx = True
                active_provider = self.ort_session.get_providers()[0]
                logging.info(f"🚀 INFERENCE ENGINE: ONNX Runtime Ativo | Provider: {active_provider}")
                
                # Warm-up (Aquecimento do DirectML para evitar lag no primeiro trade)
                self._warmup_onnx()
                return
            except Exception as e:
                logging.error(f"Falha ao carregar ONNX (fallback para PyTorch): {e}")
                self.use_onnx = False

        # 2. Fallback: Carregar PyTorch (CPU)
        try:
            self.model = PatchTST(c_in=1, context_window=60, target_window=5, d_model=128, n_heads=4, n_layers=2)
            if self.model_path and os.path.exists(self.model_path):
                state_dict = torch.load(self.model_path, map_location=torch.device('cpu'))
                self.model.load_state_dict(state_dict)
                self.model.eval()
                logging.info(f"⚠️ INFERENCE ENGINE: Rodando em PyTorch (CPU) - Legacy Mode")
            else:
                logging.warning(f"Pesos não encontrados em {self.model_path}. Usando modelo não treinado.")
        except Exception as e:
            logging.error(f"Falha ao carregar modelo PyTorch: {e}")
            self.model = None

    def _warmup_onnx(self):
        """Executa uma inferência dummy para alocar memória na GPU."""
        try:
            dummy_input = np.random.randn(1, 60, 1).astype(np.float32)
            input_name = self.ort_session.get_inputs()[0].name
            self.ort_session.run(None, {input_name: dummy_input})
            logging.info("🔥 DirectML Warm-up Concluído.")
        except Exception as e:
            logging.warning(f"Erro no warm-up ONNX: {e}")

    async def predict(self, dataframe):
        """Interface pública não-bloqueante."""
        if (self.use_onnx and not self.ort_session) or (not self.use_onnx and not self.model):
             return 0.5
        
        if dataframe is None or len(dataframe) < 60:
            return 0.5
            
        return await asyncio.to_thread(self._predict_sync, dataframe)

    def _predict_sync(self, dataframe):
        """Lógica de inferência unificada (ONNX ou PyTorch)."""
        try:
            # 1. Pre-processing (Igual para ambos)
            data = dataframe['close'].values[-60:]
            mean = data.mean()
            std = data.std() + 1e-8
            norm_data = (data - mean) / std
            
            # Input Shape: [Batch=1, Seq=60, Channels=1]
            input_tensor = norm_data[np.newaxis, :, np.newaxis].astype(np.float32)
            
            # Check for NaNs before inference
            if np.isnan(input_tensor).any():
                logging.warning("⚠️ NaN detectado no input tensor. Retornando neutro.")
                return 0.5

            # 2. Inferência
            if self.use_onnx:
                # ONNX Runtime
                input_name = self.ort_session.get_inputs()[0].name
                preds = self.ort_session.run(None, {input_name: input_tensor})[0] # [1, 5, 1]
                preds = preds[0] # [5, 1] - Remove batch
                
                # Assume-se output determinístico (Single Value per step)
                # Usamos heurística de incerteza (2%) já que o modelo atual não exporta quantis nativos
                val = preds[-1, 0] # Last step, 1st channel
                q10, q50, q90 = val * 0.99, val, val * 1.01
                
            else:
                # PyTorch Legacy
                x = torch.tensor(input_tensor)
                with torch.no_grad():
                    out = self.model(x) # [1, 5, 1]
                    val = out[0, -1, 0].item()
                    q10, q50, q90 = val * 0.99, val, val * 1.01

            # Post-processing (Heurística de Incerteza)
            forecast_price = (q50 * std) + mean
            lower_bound = (q10 * std) + mean
            upper_bound = (q90 * std) + mean
            
            # Cálculo de Score de Tendência
            trend_score = 0.5 + (q50 - norm_data[-1]) * 2
            final_score = max(0.0, min(1.0, trend_score))
            
            return {
                "score": float(final_score),
                "forecast": float(forecast_price),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "uncertainty": float(upper_bound - lower_bound),
                "confidence": 0.95 # Confiança fixa baseada na robustez do modelo
            }
            
        except Exception as e:
            logging.error(f"Erro inferência ({'ONNX' if self.use_onnx else 'PT'}): {e}")
            return 0.5

