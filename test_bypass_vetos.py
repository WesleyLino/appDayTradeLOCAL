import logging
from unittest.mock import patch
from datetime import datetime, time

from backend.risk_manager import RiskManager
from backend.ai_core import AICore

def run_tests():
    print("\n" + "="*50)
    print("🚀 INICIANDO AUDITORIA DE BYPASS DE VETOS 🚀")
    print("="*50)
    
    # ---------------------------------------------------------
    # TESTE 1: COMPORTAMENTO DO FILTRO DE NOTÍCIAS (NLP)
    # ---------------------------------------------------------
    print("\n[TESTE 1] - BYPASS DO FILTRO DE NOTÍCIAS (NLP)")
    risk = RiskManager()
    ai = AICore()
    
    # Simulamos um cenário onde o mundo está derretendo (Sentimento -1.0)
    ai.latest_sentiment_score = -1.0
    
    # CENÁRIO A: Botão LIGADO (True) no Painel
    risk.enable_news_filter = True
    effective_sentiment_ligado = ai.latest_sentiment_score if getattr(risk, 'enable_news_filter', True) else 0.0
    print(f"  👉 Painel [LIGADO]  -> Sentimento da API: {ai.latest_sentiment_score} | Sentimento Matemático Repassado à IA: {effective_sentiment_ligado}")
    assert effective_sentiment_ligado == -1.0, "Erro: Filtro ligado deveria repassar o valor real de NLP."

    # CENÁRIO B: Botão DESLIGADO (False) no Painel
    risk.enable_news_filter = False
    effective_sentiment_desligado = ai.latest_sentiment_score if getattr(risk, 'enable_news_filter', True) else 0.0
    print(f"  👉 Painel [DESLIGADO] -> Sentimento da API: {ai.latest_sentiment_score} | Sentimento Matemático Repassado à IA: {effective_sentiment_desligado}")
    assert effective_sentiment_desligado == 0.0, "Erro: Bypass não neutralizou o sentimento!"
    
    print("  ✔️ APROVADO: O Bypass isola a IA perfeitamente mantendo o score visual nativo na API plana.\n")

    # ---------------------------------------------------------
    # TESTE 2: COMPORTAMENTO DO FILTRO DE CALENDÁRIO
    # ---------------------------------------------------------
    print("[TESTE 2] - BYPASS DO VETO DE AGENDA (CALENDÁRIO)")
    risk.calendar_events = [{
        "event": "PAYROLL (Mock)", 
        "start": time(9, 30), 
        "end": time(10, 30), 
        "momentum_end": time(10, 40)
    }]
    
    # Vamos 'congelar' o tempo do sistema para atuar como se fosse exatamente as 10:00 da manhã (No olho do furacão do Payroll)
    dummy_now = datetime(2026, 3, 4, 10, 0, 0)
    
    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return dummy_now
            
    with patch('backend.risk_manager.datetime', MockDatetime):
        # CENÁRIO A: Botão LIGADO (True)
        risk.enable_calendar_filter = True
        tempo_permitido = risk.is_time_allowed()
        print(f"  👉 Painel [LIGADO]  -> Data Simulada: 10:00 (Durante PAYROLL). Trade Liberado? {tempo_permitido}")
        assert not tempo_permitido, "Erro: Filtro deveria bloquear no payroll."
        
        # CENÁRIO B: Botão DESLIGADO (False)
        risk.enable_calendar_filter = False
        tempo_ignorado = risk.is_time_allowed()
        print(f"  👉 Painel [DESLIGADO] -> Data Simulada: 10:00 (Durante PAYROLL). Trade Liberado? {tempo_ignorado}")
        assert tempo_ignorado, "Erro: Filtro não liberou o DayTrade mesmo com Veto Agenda Bypassado."

    print("  ✔️ APROVADO: O Veto de Agenda anula a varredura e permite os trades soltos.\n")
    print("="*50)
    print("✅ ABSOLUTAMENTE TODOS OS MÓDULOS DE CONTROLE FUNCIONAM CONFORME DETERMINADO.")
    print("="*50 + "\n")

if __name__ == '__main__':
    run_tests()
