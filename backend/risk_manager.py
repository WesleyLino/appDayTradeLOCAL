from datetime import datetime, time
import logging

class RiskManager:
    def __init__(self, max_daily_loss=200.00):
        self.max_daily_loss = max_daily_loss
        self.max_deviation = 5 # Pontos de slippage permitidos (B3)
        self.forbidden_hours = [
            (time(8, 55), time(9, 5)),   # Abertura
            (time(12, 0), time(13, 0)),  # Almoço/Baixa liquidez
            (time(16, 55), time(18, 0))  # Fechamento
        ]

    def is_time_allowed(self):
        """Verifica se o horário atual é permitido para operar."""
        now = datetime.now().time()
        for start, end in self.forbidden_hours:
            if start <= now <= end:
                return False
        return True

    def should_force_close(self):
        """Verifica se passou das 17:50 para encerramento compulsório."""
        now = datetime.now().time()
        return now >= time(17, 50)

    def validate_market_condition(self, symbol, regime, current_atr, avg_atr):
        """
        Valida se as condições de mercado são seguras para operar.
        Regras (Compliance com project_rules.json):
        1. Rejeita se Regime = 2 (RUÍDO/ALTA VOLATILIDADE).
        2. Rejeita se Volatilidade (ATR) > 3x ATR Médio (Circuit Breaker).
        3. Panic Threshold ajustado por ativo.
        """
        # Regra 1: Regime de Mercado (0=Indefinido, 1=Tendência, 2=Ruído)
        if regime == 2:
            return {
                "allowed": False,
                "reason": "Market Regime is NOISE/VOLATILE (2)"
            }

        # Regra 2: Circuit Breaker Dinâmico (Relativo)
        if avg_atr > 0 and current_atr > (3 * avg_atr):
             return {
                "allowed": False,
                "reason": f"Circuit Breaker: ATR {current_atr:.1f} > 3x Avg {avg_atr:.1f}"
            }
            
        # Regra 3: Panic Threshold Absoluto (Fallback se média estiver descalibrada)
        # WIN: ~150-300 pts é alto. 500 é extremo.
        # WDO: ~5-10 pts é alto. 20 é extremo.
        panic_threshold = 500.0 if ("WIN" in symbol or "IND" in symbol) else 20.0
        
        if current_atr > panic_threshold:
             return {
                "allowed": False,
                "reason": f"Extreme Volatility ({current_atr:.1f} > {panic_threshold})"
            }

        return {"allowed": True, "reason": "Market Condition OK"}

    def check_daily_loss(self, current_balance, start_balance):
        loss = start_balance - current_balance
        if loss >= self.max_daily_loss:
            return False, f"Daily loss limit reached: {loss} >= {self.max_daily_loss}"
        return True, "OK"

    def validate_volatility(self, current_atr, avg_atr):
        """
        Implementa o Circuit Breaker baseado em volatilidade.
        Regra do Master Plan: Parar se volatilidade > 3x ATR_MEDIO.
        """
        if avg_atr <= 0 or current_atr <= 0:
            return True
            
        if current_atr > 3 * avg_atr:
             logging.error(f"CIRCUIT BREAKER: Volatilidade (ATR: {current_atr:.2f}) > 3x Média ({avg_atr:.2f})")
             return False
        return True

    def get_order_params(self, symbol, type, price, volume):
        """
        Retorna parâmetros calculados para envio de ordem OCO (One Cancels Other).
        Detecta automaticamente se é WIN ou WDO para definir stops.
        """
        import MetaTrader5 as mt5
        
        # Definição de Stops por Ativo (Padrão Day Trade)
        if "WDO" in symbol or "DOL" in symbol:
            sl_points = 5.0   # 5 pontos no Dólar (R$ 50,00)
            tp_points = 10.0  # 10 pontos no Dólar (R$ 100,00)
        elif "WIN" in symbol or "IND" in symbol:
            sl_points = 150.0 # 150 pontos no Índice (R$ 30,00)
            tp_points = 300.0 # 300 pontos no Índice (R$ 60,00)
        else:
            sl_points = 0.0
            tp_points = 0.0

        sl = 0.0
        tp = 0.0
        
        if sl_points > 0:
            if type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP):
                sl = price - sl_points
                tp = price + tp_points
            elif type in (mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP):
                sl = price + sl_points
                tp = price - tp_points

        return {
            "action": mt5.TRADE_ACTION_PENDING, # Usar ordens LIMIT conforme Master Plan
            "symbol": "", # Será preenchido no main.py
            "type": type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "volume": float(volume),
            "deviation": self.max_deviation,
            "magic": 123456,
            "comment": "QuantumTrade B3 OCO",
            "type_time": mt5.ORDER_TIME_DAY, # Ordem válida até o final do dia (Day Trade)
            "type_filling": mt5.ORDER_FILLING_RETURN, # Permite execução parcial (Limit Orders na B3)
        }
