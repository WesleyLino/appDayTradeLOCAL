import requests
import re
import logging

logging.basicConfig(level=logging.INFO)

class NewsCollector:
    def __init__(self):
        # Fontes de notícias financeiras (Exemplo: RSS do InfoMoney ou Investing)
        self.sources = [
            "https://www.infomoney.com.br/mercados/feed/",
            "https://br.investing.com/rss/news_25.rss"
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def get_latest_headlines(self, limit=10):
        """Coleta manchetes das fontes configuradas com timeout reduzido."""
        all_headlines = []
        
        for url in self.sources:
            try:
                # [Otimização] Timeout reduzido para 3s para evitar engasgos no loop
                response = requests.get(url, headers=self.headers, timeout=3)
                if response.status_code == 200:
                    # Regex simples para extrair <title> de itens no RSS
                    titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', response.text)
                    # Se não houver CDATA, tenta título normal
                    if not titles:
                        titles = re.findall(r'<title>(.*?)</title>', response.text)
                    
                    # Filtra títulos irrelevantes (geralmente o primeiro é o nome do site)
                    if titles: titles = titles[1:]
                    
                    all_headlines.extend(titles[:limit])
            except Exception:
                # Silencioso para não poluir o terminal, logado apenas se necessário
                pass
        
        # Remover duplicatas e limpar strings
        unique_headlines = list(set([h.strip() for h in all_headlines if len(h) > 10]))
        if unique_headlines:
            logging.info(f"📰 Coletadas {len(unique_headlines)} manchetes financeiras.")
        return unique_headlines[:limit]

if __name__ == "__main__":
    collector = NewsCollector()
    news = collector.get_latest_headlines()
    for i, h in enumerate(news):
        print(f"{i+1}. {h}")
