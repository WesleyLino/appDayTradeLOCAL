from datetime import datetime, time
import logging
import math
import numpy as np

# [ANTIVIBE-CODING] - Classe Crítica de Risco
class RiskManager:
    def __init__(self, max_daily_loss=600.00, daily_trade_limit=3, max_daily_loss_pct=0.60):
        self.max_daily_loss = max_daily_loss
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_trade_limit = daily_trade_limit 
        self.max_deviation = 5 
        self.allow_autonomous = True 
        self.dry_run = False # [REAL-EXECUTION-ACTIVE] - Ativação de ordens reais no MT5
        # [ANTIVIBE-CODING] - Limites de Perda Agressivos
        self.forbidden_hours = [
            (time(8, 55), time(9, 5)),   # Abertura
            (time(12, 0), time(13, 0)),  # Almoço/Baixa liquidez
            (time(16, 55), time(18, 0))  # Fechamento
        ]
        
        # [SOTA] Trailing Stop Parameters (Default WIN Champion)
        self.trailing_trigger = 70.0  # Ativa com 70 pontos (Otimizado)
        self.trailing_lock = 50.0    # Trava 50 pontos iniciais
        self.trailing_step = 20.0    # Move a cada 20 pontos de avanço
        
        # [URGENTE] Breakeven Parameters
        self.be_trigger = 50.0       # Ativa com 50 pontos de lucro (Otimizado)
        self.be_lock = 0.0           # Move para o preço de entrada (0.0 de lucro garantido)
        
        # [FASE 28] DYNAMIC PARAMS CACHE
        self.dynamic_params = {} # Carregado via load_optimized_params

        # [PERFORMANCE METRICS]
        self.total_trades = 0
        self.wins = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.daily_profit = 0.0

    def is_time_allowed(self):
        """Verifica se o horário atual é permitido para operar."""
        now = datetime.now().time()
        for start, end in self.forbidden_hours:
            if start <= now <= end:
                return False
        return True

    def validate_environmental_risk(self, ping_ms, spread_points, max_ping=150.0, max_spread=15.0):
        """
        Avalia se a conectividade com a B3 está estável e se o mercado possui liquidez básica (Não-Estressado).
        Bloqueia envios com lógicas Anti-Slippage.
        """
        if ping_ms is not None and ping_ms > max_ping:
            return False, f"Ping Muito Alto/Latência Severa (B3): {ping_ms:.1f}ms (Aceitável: <= {max_ping}ms)"
            
        if spread_points is not None and spread_points > max_spread:
             return False, f"Spread Alargado (Vazio de Liquidez/Notícia/Leilão): {spread_points} pts (Aceitável: <= {max_spread} pts)"
             
        return True, "Ambiente (Ping/Spread) OK"

    def check_equity_kill_switch(self, current_equity, starting_equity):
        """
        O Botão de Pânico Incondicional.
        Puxa a leitura bruta de Equity (Capital Líquido com Ordens Flutuantes) e desliga a máquina se exceder Max Daily Loss.
        """
        if current_equity <= 0 or starting_equity <= 0:
            return True, "Kill Switch: Ignorado (Sem dados de Equity base)"
            
        drawdown_value = starting_equity - current_equity
        if drawdown_value >= self.max_daily_loss:
            return False, f"KILL SWITCH ATIVADO: Drawdown Extremo (Flutuante). Perca Atual: R$ {drawdown_value:.2f} >= Limite Master: R$ {self.max_daily_loss:.2f}"
            
        return True, "Equity Seguro"

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

    def record_trade_result(self, pnl):
        """Atualiza as métricas de performance após um trade."""
        self.total_trades += 1
        self.daily_profit += pnl
        if pnl > 0:
            self.wins += 1
            self.gross_profit += pnl
        else:
            self.gross_loss += abs(pnl)

    def get_performance_metrics(self):
        """Retorna métricas calculadas."""
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0
        profit_factor = (self.gross_profit / self.gross_loss) if self.gross_loss > 0 else (self.gross_profit if self.total_trades > 0 else 0.0)
        return {
            "total_trades": self.total_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "net_profit": round(self.daily_profit, 2)
        }

    def check_daily_loss(self, total_profit):
        """
        Verifica se o limite de perda diária foi atingido.
        total_profit: Soma do Lucro Realizado + Flutuante.
        """
        # Se total_profit for negativo e maior (em magnitude) que o limite
        if total_profit <= -self.max_daily_loss:
            return False, f"Daily loss limit reached: {total_profit:.2f} <= -{self.max_daily_loss:.2f}"
        return True, "OK"

    def check_aggressive_risk(self, daily_pnl, initial_balance=1000.0):
        """
        [AGRESSIVO] Verifica se o prejuízo do dia atingiu o limite percentual.
        Ignora a contagem de trades enquanto houver capital e sinal.
        """
        limit = initial_balance * self.max_daily_loss_pct
        if daily_pnl <= -limit:
            return False, f"Limite de perda agressivo atingido: R$ {abs(daily_pnl):.2f} (>= {int(self.max_daily_loss_pct*100)}%)"
        return True, "Risco OK"

    def check_trade_limit(self, current_trade_count):
        """
        Verifica se o limite de trades diários foi atingido.
        [AGRESSIVO] No modo 60%, este método pode ser ignorado pelo bot.
        """
        if current_trade_count >= self.daily_trade_limit:
            return False, f"Daily trade limit reached: {current_trade_count} / {self.daily_trade_limit}"
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

    def calculate_volatility_sizing(self, balance: float, current_atr: float, point_value: float = 0.20, risk_pct: float = 0.01) -> float:
        """
        [SOTA] Calcula o tamanho do lote baseado na volatilidade (Volatility Sizing).
        Objetivo: Equalizar o risco financeiro ($ em risco) independente da volatilidade.
        
        Fórmula: Lotes = (Saldo * Risco%) / (ATR * Valor_Ponto)
        
        Exemplo WIN: 
          Saldo=1000, Risco=1% ($10), ATR=100pts, ValorPonto=$0.20
          Stop Financeiro Oculto ≈ 1 ATR
          Lotes = 10 / (100 * 0.20) = 10 / 20 = 0.5 (Arredonda para 1 min)
          
        Args:
            balance: Saldo atual da conta.
            current_atr: Volatilidade atual (em pontos).
            point_value: Valor financeiro por ponto (WIN=0.20, WDO=10.0).
            risk_pct: % do saldo a arriscar por trade (Default 1%).
            
        Returns:
            float: Quantidade de lotes sugerida (não arredondada inteira, tratar no caller).
        """
        if current_atr <= 0 or point_value <= 0:
            return 1.0 # Fallback conservador
            
        risk_amount = balance * risk_pct
        volatility_cost = current_atr * point_value
        
        if volatility_cost == 0: return 1.0
        
        suggested_lots = risk_amount / volatility_cost
        return float(suggested_lots)

    def load_optimized_params(self, symbol, json_path):
        """Carrega parâmetros otimizados (SL, TP, etc) de um arquivo JSON."""
        import json
        import os
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    raw_data = json.load(f)
                    # O optimizer.py salva no formato {"params": {...}, "profit_factor": ...}
                    params = raw_data.get("params", raw_data)
                    
                    # Mapeamento de nomes do optimizer para nomes do SniperBot
                    mapped_params = {
                        "sl": params.get("sl_dist", params.get("sl")),
                        "tp": params.get("tp_dist", params.get("tp")),
                        "rsi_period": params.get("rsi_period"),
                        "vol_spike_mult": params.get("vol_spike_mult")
                    }
                    
                    self.dynamic_params[symbol] = mapped_params
                    logging.info(f"✅ RISK: Parâmetros para {symbol} mapeados: {mapped_params}")
                    return True
            except Exception as e:
                logging.error(f"❌ RISK: Erro ao carregar parâmetros de {json_path}: {e}")
        return False


    def get_order_params(self, symbol, type, price, volume, current_atr=None, regime=None, tp_multiplier=1.0):
        """
        Retorna parâmetros calculados para envio de ordem OCO (One Cancels Other).
        Detecta automaticamente se é WIN ou WDO para definir stops.
        Agora suporta alvos dinâmicos baseados no ATR e Regime para adaptação à volatilidade.
        [SOTA v5] Suporta tp_multiplier para compensação de spread.
        """
        import MetaTrader5 as mt5
        
        # Definição de Stops por Ativo (Padrão Day Trade)
        # PRIORIDADE 1: Alvos Dinâmicos baseados em ATR (Se disponível)
        if current_atr and current_atr > 0:
            # Multiplicadores baseados na recalibração vencedora de 23/02
            # [PRO-MAX] Ajuste por Regime
            tp_mult = 1.0 
            sl_mult = 1.3

            if regime == 1: # Tendência Clara: Buscar alvos maiores
                tp_mult = 1.5
                logging.info("📈 REGIME TENDÊNCIA: Alvo TP expandido (1.5x ATR)")
            elif regime == 0: # Indefinido/Lateral: Alvos Curtos
                tp_mult = 0.8
                logging.info("⚖️ REGIME LATERAL: Alvo TP reduzido (0.8x ATR)")
            
            sl_points = float(current_atr * sl_mult)
            tp_points = float(current_atr * tp_mult)
            
        # PRIORIDADE 2: Parâmetros Otimizados dinamicamente via JSON
        elif symbol in self.dynamic_params:
            d_params = self.dynamic_params[symbol]
            sl_points = float(d_params.get("sl", 130.0))
            tp_points = float(d_params.get("tp", 100.0))
            logging.info(f"🎯 RISK: Usando parâmetros OTIMIZADOS para {symbol}: SL={sl_points}, TP={tp_points}")
        elif "WDO" in symbol or "DOL" in symbol:
            sl_points = 5.0   # 5 pontos no Dólar
            tp_points = 10.0  # 10 pontos no Dólar
        elif "WIN" in symbol or "IND" in symbol:
            sl_points = 130.0 # 130 pontos no Índice
            tp_points = 100.0 # 100 pontos no Índice (Target Recalibrado)
        else:
            sl_points = 0.0
            tp_points = 0.0

        # [SOTA v5] Aplicação do Multiplicador de Precisão (Spread-Adjusted)
        if tp_multiplier != 1.0 and tp_points > 0:
            old_tp = tp_points
            tp_points *= tp_multiplier
            logging.info(f"🎯 SOTA v5 PRECISION: TP Adjusted by Spread Component: {old_tp:.1f} -> {tp_points:.1f} (Mult: {tp_multiplier:.3f})")

        # Limites de segurança (Sanity Check)
        if "WIN" in symbol:
            sl_points = max(100.0, min(300.0, sl_points))
            tp_points = max(100.0, min(400.0, tp_points))
        elif "WDO" in symbol or "DOL" in symbol:
            sl_points = max(3.0, min(15.0, sl_points))
            tp_points = max(5.0, min(30.0, tp_points))

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

            # --- HFT DEFENSIVE MATH: QUANTIZAR PREÇO (B3 TICK SIZE) ---
            sl = self._quantize_price(symbol, sl)
            tp = self._quantize_price(symbol, tp)
            # ----------------------------------------------------------

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
    def _quantize_price(self, symbol, price):
        """
        Garante que o preço seja um múltiplo do tick size (B3).
        WIN: 5 pontos | WDO: 0.5 pontos
        """
        if price <= 0: return 0.0
        
        if "WDO" in symbol or "DOL" in symbol:
            tick_size = 0.5
        elif "WIN" in symbol or "IND" in symbol:
            tick_size = 5.0
        else:
            return price # Outros ativos

        # Arredonda para o múltiplo mais próximo
        return round(price / tick_size) * tick_size

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
                
                # Garantir que após o offset, o preço continue quantizado (IMPORTANTÍSSIMO)
                new_price = self._quantize_price(symbol, new_price)
                
                logging.info(f"🛡️ ANTI-VIOLINADA: Ajustando {price} -> {new_price} ({symbol})")
                return new_price
            
            return price
        except Exception as e:
            logging.error(f"Erro Crítico Anti-Violinada: {e}")
            return price
