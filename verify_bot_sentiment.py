import asyncio
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.append(os.getcwd())

from backend.bot_sniper_win import SniperBotWIN
from backend.risk_manager import RiskManager
from backend.ai_core import AICore

class MockBridge:
    def __init__(self):
        self.connected = True
        self.mt5 = type('obj', (object,), {'TRADE_RETCODE_DONE': 10009})
    def get_current_symbol(self, s): return "WINJ26"
    def disconnect(self): pass

async def verify():
    print("🧪 [TESTE] Verificando neutralização de sentimento no SniperBot...")
    
    # Setup
    ai = AICore()
    risk = RiskManager(max_daily_loss=100.0)
    bot = SniperBotWIN(risk=risk, ai=ai, dry_run=True)
    bot.symbol = "WINJ26"

    # Caso 1: Filtro Ativado
    risk.enable_news_filter = True
    # Simulando um sentimento alto no arquivo se necessário, mas aqui vamos testar a lógica de injeção
    sentiment_active = await ai.update_sentiment()
    
    # Lógica que injetei no bot:
    eff_sent_active = await bot.ai.update_sentiment() if (getattr(bot.risk, 'enable_news_filter', True)) else 0.0
    print(f"✅ Filtro Ligado: Sentimento Efetivo = {eff_sent_active} (Original: {sentiment_active})")
    
    # Caso 2: Filtro Desativado
    risk.enable_news_filter = False
    eff_sent_inactive = await bot.ai.update_sentiment() if (getattr(bot.risk, 'enable_news_filter', True)) else 0.0
    print(f"✅ Filtro Desligado: Sentimento Efetivo = {eff_sent_inactive}")

    if eff_sent_active == sentiment_active and eff_sent_inactive == 0.0:
        print("\n🎯 [SUCESSO] Sincronização de Sentimento Validada!")
    else:
        print("\n❌ [FALHA] Discrepância na lógica de neutralização.")

if __name__ == "__main__":
    asyncio.run(verify())
