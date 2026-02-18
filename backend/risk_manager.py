from datetime import datetime, time
import logging
import math
import numpy as np

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

    def calculate_psr(self, returns_list, benchmark_sr=0.0):
        """
        Calcula o Probabilistic Sharpe Ratio (PSR).
        Determina se a performance observada é estatisticamente significativa.
        """
        n = len(returns_list)
        if n < 30: # Amostra mínima conforme econometria para convergência
            return 1.0 # Neutro
            
        returns = np.array(returns_list)
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        
        if std_ret == 0: return 0.0
        
        sr = mean_ret / std_ret
        
        # Momentos (Skewness e Kurtosis)
        diffs = returns - mean_ret
        m2 = np.mean(diffs**2)
        m3 = np.mean(diffs**3)
        m4 = np.mean(diffs**4)
        
        skew = m3 / (m2**1.5) if m2 > 0 else 0
        kurt = m4 / (m2**2) - 3 if m2 > 0 else 0 # Excess Kurtosis
        
        # Fórmula de Bailey and López de Prado
        v = (1 - skew * sr + (kurt / 4) * (sr**2))
        if v <= 0: return 0.0
        
        z = (sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(v)
        
        # CDF Normal Aproximada (ERF)
        psr = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        return psr

    def validate_reliability(self, returns_list):
        """
        Veto AlphaX: Bloqueia se a confiabilidade estatística (PSR) for < 95%.
        """
        if not returns_list: return True, 1.0
        
        psr = self.calculate_psr(returns_list)
        if psr < 0.95:
            return False, psr
        return True, psr

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

    def check_macro_filter(self, side, macro_change_pct):
        """
        Filtro Macro (HFT Impact):
        Bloqueia COMPRA se S&P500 cair > 0.5% (Bearish Global).
        Bloqueia VENDA se S&P500 subir > 0.5% (Bullish Global).
        """
        # Se macro_change_pct for 0.0 (não detectado), ignora o filtro
        if macro_change_pct == 0.0:
            return True, "Neutro (N/A)"

        if side == "buy" and macro_change_pct < -0.5:
             return False, f"Macro Bearish (S&P500 {macro_change_pct:.2f}%)"
             
        if side == "sell" and macro_change_pct > 0.5:
             return False, f"Macro Bullish (S&P500 {macro_change_pct:.2f}%)"
             
        return True, "Macro OK"

    def check_daily_loss(self, total_profit):
        """
        Verifica se o limite de perda diária foi atingido.
        total_profit: Soma do Lucro Realizado + Flutuante.
        """
        # Se total_profit for negativo e maior (em magnitude) que o limite
        if total_profit <= -self.max_daily_loss:
            return False, f"Daily loss limit reached: {total_profit:.2f} <= -{self.max_daily_loss:.2f}"
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
                side = "buy"
                sl = price - sl_points
                tp = price + tp_points
            elif type in (mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP):
                side = "sell"
                sl = price + sl_points
                tp = price - tp_points
            else:
                side = "neutral"

            # --- HFT ANTI-VIOLINADA (FASE 5b) ---
            # Ajuste fino para não deixar pedra em número redondo
            sl = self._apply_anti_violinada(symbol, sl, side)
            tp = self._apply_anti_violinada(symbol, tp, side)
            # ------------------------------------

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
    def _apply_anti_violinada(self, symbol, price, side):
        """
        Ajusta o preço de Stop/TP para evitar números redondos (Violinada).
        Evita colocar ordens exatas em 'XX.000' ou 'XX.500'.
        Desloca 5 pts (WIN) ou 0.5 pts (WDO) para 'esconder' a ordem.
        """
        if price <= 0: return price
        
        try:
            is_wdo = "WDO" in symbol or "DOL" in symbol
            
            # Parâmetros de arredondamento (HFT v2.1: Defensive Math)
            if is_wdo:
                round_interval = 10.0
                offset = 0.5
            else:
                round_interval = 100.0
                offset = 15.0
            
            # PROTEÇÃO: Se por algum motivo o preço for muito pequeno para o intervalo
            if price < round_interval:
                return price

            # Verificar proximidade com número redondo
            remainder = price % round_interval
            
            # Margem de "ZONA DE PERIGO" (10% do intervalo)
            danger_zone = round_interval * 0.1
            
            if remainder == 0 or remainder < danger_zone or remainder > (round_interval - danger_zone):
                # Deslocar para longe (Anti-Violinada)
                if side == "buy": # SL abaixo, afastar para baixo
                    new_price = price - offset
                elif side == "sell": # SL acima, afastar para cima
                    new_price = price + offset
                else:
                    new_price = price
                
                logging.info(f"🛡️ ANTI-VIOLINADA: Ajustando {price} -> {new_price} ({symbol})")
                return new_price
            
            return price
        except Exception as e:
            logging.error(f"Erro Crítico Anti-Violinada: {e}")
            return price
