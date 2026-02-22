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
        self.news_collector = NewsCollector() # Plano Diretor 2.0
        self.inference_engine = None # Injetado pelo main.py
        self.sentiment_lock = asyncio.Lock() # Lock para evitar chamadas paralelas ao Gemini

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
        
        # 2. Previsão SOTA com Incerteza (Multi-Ativo)
        if not self.inference_engine:
            return None
            
        forecast_result = await self.inference_engine.predict(market_data)
        if isinstance(forecast_result, float): # Fallback neutro
            return None

        # 3. Veto por Incerteza (Conformal Prediction / Quantile Space)
        # Se os dados estiverem normalizados, usamos os bounds normais
        uncertainty = forecast_result.get('uncertainty_norm', 1.0)
        forecast_move = abs(forecast_result.get('forecast_norm', 0.0))
        
        if forecast_move < (uncertainty * 0.3): # Limite de ruído mais agressivo
            logging.info(f"⛔ Trade Vetado pelo SOTA: Movimento projetado ({forecast_move:.2f}) menor que incerteza ({uncertainty:.2f}).")
            return None 
            
        return {
            "signal": "BUY" if forecast_result['forecast_norm'] > 0 else "SELL",
            "confidence": forecast_result['confidence'],
            "reason": f"SOTA Forecast Norm: {forecast_result['forecast_norm']:.2f} (Uncertainty: {uncertainty:.2f})"
        }

    async def update_sentiment(self):
        """
        Consulta o Gemini para obter o score de sentimento (-1 a 1) com reliability scoring.
        Versão Full-Stack Quant: Persona Engenheiro de Risco + Cache 60s + Lock.
        """
        if not self.model:
            return 0.0
            
        now = asyncio.get_event_loop().time()
        # [MODO SNIPER] Atualizar a cada 60 segundos para evitar estouro de cota (429)
        if now - self.last_news_update < 60:
            return self.latest_sentiment_score

        async with self.sentiment_lock:
            # Re-check após adquirir o lock (Double-Check Pattern)
            if now - self.last_news_update < 60:
                return self.latest_sentiment_score

            # [PLANO DIRETOR 2.0] Usar NewsCollector ao invés de news_feed.txt
            news_headlines = await asyncio.to_thread(self.news_collector.get_latest_headlines)
            
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
                
                # Feedback de Robustez
                if reliability == "low":
                    score *= 0.5 # Reduz impacto de análise duvidosa
                
                self.latest_sentiment_score = max(-1.0, min(1.0, score))
                self.last_news_update = now
                logging.info(f"🤖 Monitor de Risco: Score={self.latest_sentiment_score:.2f} ({reliability.upper()}) | Risco: {risk_class}")
                return self.latest_sentiment_score
            except Exception as e:
                if "429" in str(e):
                    logging.warning("⚠️ Cota da API Gemini excedida (429). Usando último score conhecido.")
                    return self.latest_sentiment_score
                logging.error(f"❌ Erro na IA (Falha de Grounding): {e}")
                return self.latest_sentiment_score

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
            current_obi = (total_bid - total_ask) / (total_bid + total_ask + 1)
        
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
            uncertainty_abs = patchtst_score.get("uncertainty_norm", 0.0)
            forecast_ref = patchtst_score.get("forecast_norm", 1.0)
            if forecast_ref == 0: forecast_ref = 1.0
            
            norm_patchtst = (patchtst_score.get("score", 0.5) - 0.5) * 2
        else:
            norm_patchtst = (patchtst_score - 0.5) * 2 
        
        # [HFT v2.1 FIX] Calcular incerteza relativa (%)
        uncertainty_rel = abs(uncertainty_abs / forecast_ref)

        # [VETO POR INCERTEZA] Se PatchTST estiver muito incerto (>5% range relativo), VETO total.
        if uncertainty_rel > 0.05: 
            logging.warning(f"CONFORMAL VETO: Incerteza Alta ({uncertainty_rel*100:.2f}%). Abortando decisão.")
            return {
                "score": 50.0,
                "direction": "NEUTRAL",
                "forecast": float(forecast_ref),
                "breakdown": {
                    "veto": "HIGH_UNCERTAINTY",
                    "uncertainty_rel": uncertainty_rel
                }
            }
        
        # 2. Pesos Dinâmicos (Restauração Macro: IA Proativa)
        w_sent = 0.40
        w_obi = 0.30
        w_patchtst = 0.30

        if regime == 0: # Consolidação / Ruído -> Equilíbrio Fluxo/Predição
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
        if self.meta_learner.model is None:
            # Fallback direto se não houver modelo carregado
            meta_proba = ai_score_raw / 100.0
        else:
            try:
                meta_proba = self.meta_learner.predict_proba(meta_features) # Returns probability 0.0-1.0
            except Exception as e:
                logging.warning(f"Meta-Learner fallback: Usando raw signal (Motive: {e})")
                meta_proba = ai_score_raw / 100.0
        
        # Converter probabilidade para score (0-100)
        meta_score = meta_proba * 100.0

        # A decisão final é uma média ponderada entre o Sinal Bruto (Macro) e o Meta-Learner
        # Isso garante que o sentimento IA (notícias/bluechips) não seja silenciado pelo modelo estatístico.
        final_score = (ai_score_raw * 0.4) + (meta_score * 0.6)
        
        # 5. Direção (Thresholds SOTA v3.1 - Precisão Absoluta)
        # Exigimos 85% de confluência para modo autônomo.
        direction = "NEUTRAL"
        if final_score >= 85: 
            direction = "BUY"
        elif final_score <= 15: 
            direction = "SELL"
            
        return {
            "score": final_score,
            "direction": direction,
            "forecast": float(forecast_ref),
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
        self.model_path = model_path # Caminho do .pth (Legacy/Training)
        self.onnx_path = model_path.replace(".pth", "_optimized.onnx") if model_path else None
        self.use_onnx = False
        self.ort_session = None
        self.model = None # PyTorch fallback
        
        if model_path:
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
        potential_onnx_paths = [self.onnx_path, os.path.join(os.path.dirname(self.onnx_path or ""), "patchtst_optimized.onnx")]
        
        target_onnx = None
        for p in potential_onnx_paths:
             if p and os.path.exists(p):
                 target_onnx = p
                 break
                 
        if target_onnx:
            try:
                logging.info(f"🚀 INFERENCE ENGINE: Tentando ONNX com {target_onnx}...")
                options = ort.SessionOptions()
                options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL 
                
                providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
                self.ort_session = ort.InferenceSession(target_onnx, sess_options=options, providers=providers)
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
            # 1. Pre-processing: O dataframe já vem normalizado da bridge
            input_data = dataframe.values[-60:]
            
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
                    logging.warning(f"ONNX Run falhou, tentando PT fallback: {repr(e_onnx)}")
                    x = torch.tensor(input_tensor).to(torch.float32)
                    with torch.no_grad():
                        out = self.model(x) 
                        preds = out[0].numpy()
            else:
                x = torch.tensor(input_tensor).to(torch.float32)
                with torch.no_grad():
                    out = self.model(x) 
                    preds = out[0].numpy()

            # 3. Post-processing
            # q10, q50, q90 para o WIN$ (coluna 0)
            q10, q50, q90 = preds[-1, 0], preds[-1, 1], preds[-1, 2]
            
            trend_score = 0.5 + (q50 - input_data[-1, 0]) * 2
            final_score = max(0.0, min(1.0, trend_score))
            
            return {
                "score": float(final_score),
                "forecast_norm": float(q50),
                "lower_bound_norm": float(q10),
                "upper_bound_norm": float(q90),
                "uncertainty_norm": float(q90 - q10),
                "confidence": 0.95
            }
            
        except Exception as e:
            # [SOTA DEBUG] Expondo o erro real para o logger e para o terminal
            print(f"❌ FATAL ERROR IN _predict_sync: {repr(e)}")
            raise e

