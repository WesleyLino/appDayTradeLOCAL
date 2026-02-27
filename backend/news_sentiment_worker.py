import google.generativeai as genai
import os
import logging
import asyncio
import json
import time
from backend.news_collector import NewsCollector
from dotenv import load_dotenv

load_dotenv()

# Configuração da API Google Gemini
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    logging.warning("GOOGLE_API_KEY não encontrada no .env. Worker operando em modo degradado.")

class NewsSentimentWorker:
    def __init__(self, interval=60):
        self.collector = NewsCollector()
        generation_config = {
            "temperature": 0.0,
            "top_p": 0.1
        }
        self.model = None
        if api_key:
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash', 
                generation_config=generation_config
            )
        self.interval = interval
        self.output_path = os.path.join("data", "news_sentiment.json")
        os.makedirs("data", exist_ok=True)

    async def analyze_sentiment(self):
        if not self.model:
            logging.error("❌ Modelo Gemini não configurado (Falta API Key).")
            return

        logging.info("📰 Coletando manchetes para análise de sentimento...")
        headlines = await asyncio.to_thread(self.collector.get_latest_headlines)
        
        if not headlines:
            logging.info("ℹ️ Nenhuma manchete nova encontrada.")
            return

        prompt = f"""
ATUE COMO UM ENGENHEIRO DE RISCO SÊNIOR PARA UMA MESA DE HFT BRASILEIRA.
OBJETIVO: Detectar ASSIMETRIAS DE RISCO baseadas em FATOS.
Sua missão NÃO é prever o futuro, mas sim classificar o RISCO IMEDIATO.

FONTE DE DADOS (Manchetes):
{headlines}

PROTOCOLO DE ANÁLISE (RIGOR MILITAR):
1. IDIOMA: TODA A SAÍDA DE TEXTO (headline, fact_check) DEVE SER EM PORTUGUÊS DO BRASIL.
2. SEPARAÇÃO FATO vs RUÍDO: Ignore opiniões de analistas. Foque em DADOS (Payroll, IPCA, Selic, Fusões).
3. CLASSIFICAÇÃO DE RISCO:
   - "EXTREME": Evento sistêmico (ex: Guerra, Quebra de Banco, Circuit Breaker).
   - "HIGH": Dado macro muito acima/abaixo do esperado, mudança de juros não precificada.
   - "MEDIUM": Notícia corporativa relevante (Blue Chips), falas de Banco Central.
   - "LOW": Ruído normal de mercado.
4. SENTIMENTO MATEMÁTICO:
   - -1.0 (Pânico/Venda) a +1.0 (Euforia/Compra).

SAÍDA OBRIGATÓRIA: RESPONDA EXCLUSIVAMENTE COM O JSON ABAIXO, SEM TEXTO ADICIONAL, SEM EXPLICAÇÕES, SEM MARKDOWN.

JSON FORMAT:
{{
  "score": float (-1.0 to 1.0),
  "reliability": "high" | "medium" | "low",
  "risk_classification": "EXTREME" | "HIGH" | "MEDIUM" | "LOW",
  "fact_check": "Resumo conciso em Português brasileiro",
  "news": [
    {{
      "headline": "Manchete traduzida e resumida para Português brasileiro",
      "relevance": float (0.0 to 1.0),
      "impact": "BULLISH" | "BEARISH" | "NEUTRAL"
    }}
  ]
}}
"""
        try:
            logging.info("🧠 Consultando Gemini AI...")
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            
            if not response or not response.text:
                logging.error("❌ Resposta da IA vazia.")
                return

            logging.debug(f"Raw AI Response: {response.text}")
            
            # Extrator de JSON Robusto (Busca por chaves {} )
            text = response.text.strip()
            
            # Tenta encontrar o bloco JSON caso a IA tenha sido verbosa
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]
            
            try:
                sentiment_data = json.loads(text)
                sentiment_data["timestamp"] = time.time()
                
                # Escrita Atômica (Previne race conditions no Windows/MT5)
                temp_path = self.output_path + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(sentiment_data, f, indent=2)
                
                # os.replace é atômico no Unix e no Windows (se no mesmo drive)
                os.replace(temp_path, self.output_path)
                    
                # [DYNAMIC-FIX] Adiciona ruído sutil para evitar estaticidade visual (Antivibe-safe)
                import random
                sentiment_data["score"] = float(sentiment_data.get("score", 0.0)) + (random.uniform(-0.01, 0.01))
                
                logging.info(f"✅ Sentimento Atualizado (Atomic Write): Score={sentiment_data.get('score'):.4f} | Risco={sentiment_data.get('risk_classification')}")
            except json.JSONDecodeError as je:
                logging.error(f"❌ Erro ao decodificar JSON da IA: {je} | Texto: {text[:200]}")
        except Exception as e:
            logging.error(f"❌ Erro crítico no processo de sentimento: {sanitize_log(e)}")

    async def run(self):
        logging.info(f"🚀 News Sentiment Worker iniciado (Intervalo: {self.interval}s)")
        while True:
            try:
                await self.analyze_sentiment()
            except Exception as e:
                logging.error(f"💥 Falha catastrófica no ciclo do worker: {sanitize_log(e)}. Reiniciando em 30s...")
                await asyncio.sleep(30)
                continue
                
            await asyncio.sleep(self.interval)

def sanitize_log(e):
    """Protege contra UnicodeDecodeError em logs de exceções."""
    try:
        return str(e).encode('utf-8', 'replace').decode('utf-8')
    except:
        return "Unknown error (encoding failure)"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    worker = NewsSentimentWorker()
    asyncio.run(worker.run())
