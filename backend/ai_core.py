import google.generativeai as genai
import os
import logging
import torch
import torch.nn as nn
from sklearn.cluster import KMeans
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# Configuração da API Google Gemini
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    logging.warning("GOOGLE_API_KEY não encontrada no .env. AI de Sentimento desabilitada.")

class AICore:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-pro') if api_key else None
        self.latest_sentiment_score = 0.0
        self.obi_ema = 0.5 # Valor inicial neutro
        self.ema_alpha = 0.2 # Fator de suavização (aproximadamente 1s em loops de 100ms)
        self.regime_model = KMeans(n_clusters=3, n_init=10) # 0: Baixa Vol, 1: Tendência, 2: Ruído
        self.regime_history = []
        self.regime_counter = 0
        self.prev_book = None
        self.toxic_flow_score = 0.0
        self.last_news_update = 0

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
        """Consulta o Gemini para obter o score de sentimento (-1 a 1)."""
        if not self.model:
            return 0.0
            
        now = time.time()
        # Atualizar apenas a cada 5 minutos para otimizar API
        if now - self.last_news_update < 300 and self.latest_sentiment_score != 0:
            return self.latest_sentiment_score

        news_headlines = self.fetch_latest_news()
        prompt = (
            f"Analise o sentimento destas manchetes para o mercado financeiro B3. "
            f"Responda apenas com um número entre -1 (extremo pânico/queda) e 1 (extrema euforia/alta). "
            f"Manchetes: {news_headlines}"
        )
        
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            score = float(response.text.strip())
            self.latest_sentiment_score = score
            self.last_news_update = now
            return score
        except Exception as e:
            logging.error(f"Erro ao consultar Gemini: {e}")
            return self.latest_sentiment_score

    def detect_spoofing(self, order_book, time_sales):
        """
        Detecta spoofing comparando volume do book com histórico recente.
        Implementa a regra de 'Toxic Flow': sumiço de ordens grandes sem trade.
        """
        if not order_book:
            return 0.5
            
        # 1. OBI (Order Book Imbalance) básico
        total_bid = sum(item['volume'] for item in order_book if item['type'] == 0)
        total_ask = sum(item['volume'] for item in order_book if item['type'] == 1)
        
        current_obi = 0.5
        if total_bid + total_ask > 0:
            current_obi = (total_bid - total_ask) / (total_bid + total_ask)
        
        # Suavização EMA
        self.obi_ema = (current_obi * self.ema_alpha) + (self.obi_ema * (1 - self.ema_alpha))
        
        # 2. Detecção de Toxic Flow (Remoção Súbita)
        if self.prev_book is not None:
            prev_bid = sum(item['volume'] for item in self.prev_book if item['type'] == 0)
            prev_ask = sum(item['volume'] for item in self.prev_book if item['type'] == 1)
            
            # Se sumiu mais de 50 lotes de um lado e o volume real não subiu proporcionalmente
            real_volume = time_sales['volume'].sum() if time_sales is not None and not time_sales.empty else 0
            
            # Queda súbita no BID sem agressão de venda proporcional -> Spoofing de Compra
            if (prev_bid - total_bid) > 50 and real_volume < 20:
                self.toxic_flow_score = -0.5 # Sinal de "pressão falsa" na compra
            # Queda súbita no ASK sem agressão de compra proporcional -> Spoofing de Venda
            elif (prev_ask - total_ask) > 50 and real_volume < 20:
                self.toxic_flow_score = 0.5 # Sinal de "pressão falsa" na venda
            else:
                self.toxic_flow_score *= 0.8 # Decaimento gradual do alerta
                
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

    def calculate_decision(self, obi, sentiment, patchtst_score):
        """
        Calcula a decisão final de trading baseada em múltiplos fatores ponderados.
        
        Args:
            obi: Order Book Imbalance (-1.0 a 1.0)
            sentiment: Análise de Notícias (-1.0 a 1.0)
            patchtst_score: Predição de Preço (0.0 a 1.0, onde >0.5 é Alta)
            
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
        
        # PatchTST vem 0.0 a 1.0 (0.5 é neutro). Converter para -1 a 1.
        # Ex: 0.8 -> 0.6 (Alta), 0.2 -> -0.6 (Baixa)
        norm_patchtst = (patchtst_score - 0.5) * 2 
        
        # 2. Pesos (Conforme Master Plan)
        w_obi = 0.40      # 40% Microestrutura (Fluxo Imediato)
        w_patchtst = 0.40 # 40% Preditivo (Tendência Futura)
        w_sent = 0.20     # 20% Sentimento (Contexto Macro)
        
        # 3. Cálculo do Sinal Composto
        composite_signal = (obi * w_obi) + (norm_patchtst * w_patchtst) + (sentiment * w_sent)
        
        # 4. Score Final (Magnitude Absoluta 0-100)
        final_score = abs(composite_signal) * 100
        
        # 5. Direção
        direction = "NEUTRAL"
        if final_score > 10: # Banda morta mínima para evitar ruído zero
            direction = "BUY" if composite_signal > 0 else "SELL"
            
        return {
            "score": final_score,
            "direction": direction,
            "breakdown": {
                "obi_contribution": obi * w_obi,
                "patchtst_contribution": norm_patchtst * w_patchtst,
                "sentiment_contribution": sentiment * w_sent,
                "raw_signal": composite_signal
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
            
            return max(0.0, min(1.0, final_score))
            
        except Exception as e:
            logging.error(f"Erro na inferência PatchTST: {e}")
            return 0.5

    def detect_spoofing(self, order_book, time_and_sales):
        """
        Detecção Heurística de Spoofing (Phase 6 - Microestrutura Avançada).
        Identifica ordens grandes que são canceladas antes de execução.
        
        Args:
            order_book: dict {'bids': [], 'asks': []}
            time_and_sales: list [{'price':, 'volume':, 'type':}]
            
        Returns:
            float: Score de Spoofing (0.0 a 1.0). > 0.7 indica alta probabilidade de manipulação.
        """
        # Placeholder para implementação futura com dados de L2 reais
        # Lógica: Monitorar delta de volume no Book vs Volume executado no T&S
        return 0.0
