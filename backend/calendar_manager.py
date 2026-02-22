from datetime import datetime, time

class CalendarManager:
    def __init__(self):
        # Calendário estático de eventos recorrentes de alto impacto (Simplificado para o MVP)
        # Em produção, isso viria de uma API de calendário econômico
        self.high_impact_events = [
            {"name": "Payroll EUA", "day_of_week": 4, "week_of_month": 1, "time": "09:30"}, # Primeira sexta-feira (4=sexta no python isoweekday?? não, 5)
            {"name": "Abertura NYSE", "daily": True, "time": "10:30"},
            {"name": "Vencimento Opções", "third_monday": True, "time": "10:00"}
        ]

    def is_volatility_expected(self, current_time=None):
        """Retorna True se houver um evento de volatilidade em até 15 minutos."""
        now = current_time or datetime.now()
        current_hm = now.strftime("%H:%M")
        
        # Lógica de proteção: 15 min antes e 15 min depois de eventos críticos
        # Para o MVP, focamos no horário de abertura do mercado americano (NYSE)
        # que causa muita volatilidade no WIN/WDO regularmente.
        
        nyse_open = time(10, 25) # 5 min antes da abertura
        nyse_peak = time(11, 00) # Até 30 min depois
        
        if nyse_open <= now.time() <= nyse_peak:
            return True, "ALTA VOLATILIDADE: Abertura NYSE"
            
        return False, "Mercado Estável"

    def get_market_bias(self, sentiment_score):
        """Combina sentimento com horário para sugerir um viés."""
        if sentiment_score > 0.3: return "BULLISH"
        if sentiment_score < -0.3: return "BEARISH"
        return "NEUTRAL"
