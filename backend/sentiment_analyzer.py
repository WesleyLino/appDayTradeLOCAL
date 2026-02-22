import google.generativeai as genai
import os
import logging
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class SentimentAnalyzer:
    def __init__(self, api_key=None):
        # Tenta pegar do ambiente ou do parâmetro
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = "gemini-1.5-pro"
        self.is_configured = False
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.is_configured = True
                logging.info("✅ Gemini 1.5 Pro configurado com sucesso para análise de sentimento.")
            except Exception as e:
                logging.error(f"Erro ao configurar Gemini: {e}")
        else:
            logging.warning("⚠️ GEMINI_API_KEY não encontrada. O modo de sentimento rodará em modo MOCK.")

    async def analyze_sentiment(self, headlines):
        """
        Analisa uma lista de manchetes e retorna um score de -1 a +1.
        headlines: Lista de strings (manchetes).
        """
        if not headlines: return 0.0
        
        if not self.is_configured:
            # Mock para testes se não houver API Key
            logging.info("Modo MOCK: Simulando análise de sentimento.")
            return 0.15 # Neutro-positivo simbólico
            
        prompt = f"""
        Você é um analista sênior de mesa de trading da B3 (Brasil).
        Analise as seguintes manchetes financeiras e atribua um SCORE de sentimento para o mercado brasileiro (Ibovespa/Dólar).
        
        REGRAS:
        - Score entre -1.0 (Extremamente Pessimista/Bearish) e +1.0 (Extremamente Otimista/Bullish).
        - 0.0 é Neutro.
        - Considere impactos macroeconômicos (EUA, China), política fiscal do Brasil e commodities (Vale/Petro).
        
        MANCHETES:
        {chr(10).join(f"- {h}" for h in headlines)}
        
        RETORNE APENAS O NÚMERO DO SCORE (EX: 0.45). SEM EXPLICAÇÕES.
        """
        
        try:
            # Execução assíncrona para não travar o loop de trading
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            score_str = response.text.strip()
            # Tentar limpar qualquer texto se o modelo falhar em retornar apenas o número
            score = float(''.join(c for c in score_str if c in "0123456789.-"))
            logging.info(f"🧠 Gemini Sentiment Score: {score}")
            return max(-1.0, min(1.0, score))
        except Exception as e:
            logging.error(f"Erro na análise do Gemini: {e}")
            return 0.0

if __name__ == "__main__":
    # Teste rápido
    async def test():
        analyzer = SentimentAnalyzer()
        headlines = [
            "Inflação nos EUA vem abaixo do esperado, aumentando chances de corte de juros.",
            "Petróleo sobe 3% com tensões no Oriente Médio.",
            "Ibovespa fecha em alta com força de mineradoras e bancos."
        ]
        score = await analyzer.analyze_sentiment(headlines)
        print(f"Teste Score: {score}")
        
    asyncio.run(test())
