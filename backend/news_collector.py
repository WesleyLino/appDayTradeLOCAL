"""
NewsCollector - Sistema Multi-Fonte para Notícias Financeiras
Implementa redundância, filtros de frescura (<30min) e relevância (keywords).
"""

import feedparser
import asyncio
import logging
from datetime import datetime, timedelta
import pytz

# Fontes RSS Redundantes
RSS_SOURCES = [
    "https://br.investing.com/rss/news_25.rss",      # IBOV Geral
    "https://br.investing.com/rss/stock_Market.rss", # Mercado de Ações
]

# Keywords de Alto Impacto (Filtro de Relevância)
HIGH_IMPACT_KEYWORDS = [
    "ipca", "selic", "copom", "payroll", "fomc", "fed", "pib", 
    "petrobras", "vale", "banco central", "inflação", "inflacao", "discurso",
    "ibovespa", "dólar", "dolar", "commodities", "juros", "taxa",
    "dividendos", "lucro", "prejuízo", "prejuizo", "desemprego",
    "fiscal", "arcabouço", "meta", "superávit", "déficit", "fazenda", "haddad"
]

class NewsCollector:
    """
    Coletor de notícias com redundância e filtros de qualidade.
    
    Features:
    - Múltiplas fontes RSS
    - Filtro de duplicidade (títulos únicos)
    - Filtro de frescura (<30 minutos)
    - Filtro de relevância (keywords de alto impacto)
    """
    
    def __init__(self, max_age_minutes=30):
        """
        Args:
            max_age_minutes: Idade máxima da notícia em minutos (default: 30)
        """
        self.last_headlines = []
        self.tz = pytz.timezone('America/Sao_Paulo')
        self.max_age_minutes = max_age_minutes
        logging.info(f"📰 NewsCollector inicializado (Max age: {max_age_minutes} min)")

    def _clean_html(self, text):
        """Remove tags HTML e caracteres desnecessários."""
        return text.replace("&nbsp;", " ").replace("Investing.com", "").strip()

    def _is_fresh(self, entry):
        """
        Verifica se a notícia tem menos de max_age_minutes.
        
        Args:
            entry: Entrada do feedparser
            
        Returns:
            bool: True se notícia é fresca (<30 min)
        """
        if not hasattr(entry, 'published_parsed'):
            logging.debug(f"Notícia sem timestamp descartada: {entry.get('title', 'N/A')[:50]}")
            return False
        
        try:
            # Converter timestamp do RSS para datetime
            pub_time = datetime(*entry.published_parsed[:6])
            pub_time = self.tz.localize(pub_time)
            now = datetime.now(self.tz)
            
            age_minutes = (now - pub_time).total_seconds() / 60
            
            if age_minutes > self.max_age_minutes:
                logging.debug(f"Notícia antiga ({age_minutes:.1f} min): {entry.title[:50]}...")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Erro ao verificar frescura: {e}")
            return False

    def _is_relevant(self, title):
        """
        Verifica se o título contém keywords de alto impacto.
        
        Args:
            title: Título da notícia
            
        Returns:
            bool: True se contém keyword relevante
        """
        title_lower = title.lower()
        for keyword in HIGH_IMPACT_KEYWORDS:
            if keyword in title_lower:
                return True
        return False

    def fetch_market_pulse(self):
        """
        Busca notícias de múltiplas fontes com filtros aplicados.
        
        Returns:
            str ou None: String formatada com top 10 headlines ou None se nenhuma relevante
        """
        aggregated_news = []
        seen_titles = set()
        
        logging.info("🔄 Iniciando coleta multi-fonte...")
        
        for url in RSS_SOURCES:
            try:
                logging.debug(f"Lendo RSS: {url}")
                feed = feedparser.parse(url)
                
                if not feed.entries:
                    logging.warning(f"Feed vazio: {url}")
                    continue
                
                for entry in feed.entries[:10]:  # Top 10 por fonte
                    title = entry.title
                    title_clean = title.lower().strip()
                    
                    # Filtro 1: Duplicidade
                    if title_clean in seen_titles:
                        logging.debug(f"Duplicata descartada: {title[:50]}...")
                        continue
                    seen_titles.add(title_clean)
                    
                    # Filtro 2: Frescura (<30 min)
                    if not self._is_fresh(entry):
                        continue
                    
                    # Filtro 3: Relevância (Keywords)
                    if not self._is_relevant(title):
                        logging.debug(f"Irrelevante: {title[:50]}...")
                        continue
                    
                    # Passou todos os filtros
                    clean_title = self._clean_html(title)
                    aggregated_news.append(f"- {clean_title}")
                    logging.info(f"✅ Válida: {clean_title[:70]}...")
                    
            except Exception as e:
                logging.error(f"❌ Erro ao ler RSS {url}: {e}")
        
        # Retorna Top 10 consolidadas ou None
        if not aggregated_news:
            logging.info("⚠️ Nenhuma notícia fresca e relevante encontrada.")
            return None
        
        result = "\n".join(aggregated_news[:10])
        logging.info(f"📊 Total: {len(aggregated_news[:10])} headlines válidas")
        return result

    async def get_pulse_async(self):
        """
        Versão async do fetch_market_pulse para integração com asyncio.
        
        Returns:
            str ou None: Headlines formatadas ou None
        """
        return await asyncio.to_thread(self.fetch_market_pulse)


# Função auxiliar para testes rápidos
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    collector = NewsCollector()
    headlines = collector.fetch_market_pulse()
    
    if headlines:
        print("\n" + "="*60)
        print("HEADLINES COLETADAS:")
        print("="*60)
        print(headlines)
        print("="*60)
    else:
        print("⚠️ Nenhuma headline encontrada.")
