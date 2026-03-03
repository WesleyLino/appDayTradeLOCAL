from datetime import datetime, time, timedelta
import logging
import math
import numpy as np
import json
import os

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
        
        # [FASE 2] Gestão de Múltiplos Contratos e Saídas Parciais
        self.base_volume = 2.0       # Lote de entrada padrão (multi-lote para parciais)
        self.partial_volume = 1.0    # Lote a ser descarregado na primeira parcial
        self.partial_profit_points = 50.0 # Gatilho em pontos para executar a zeragem parcial
        
        # [FASE 2] Velocity Limit (Drawdown Acelerado no Tempo)
        self.velocity_time_limit_sec = 20.0     # Segundos máximos engatado negativamente
        self.velocity_drawdown_limit = -30.0    # Pontos negativos que ativam o timeout rápido
        
        # [HFT ELITE] Alpha Fade (Decaimento de Ordem)
        self.alpha_fade_timeout = 10.0          # Segundos antes de cancelar ordem limite não executada
        
        # [FASE 2] Time-Based Stop (Inatividade Tática)
        self.max_trade_duration_min = 15.0      # Minutos máximos para uma operação 'preguiçosa'
        
        # [FASE 2] Quarter-Kelly (Ajuste de Expectativa)
        self.kelly_fraction = 0.25              # Quarter-Kelly (Segurança HFT)
        
        # [FASE 28] DYNAMIC PARAMS CACHE
        self.dynamic_params = {} # Carregado via load_optimized_params

        # [PERFORMANCE METRICS]
        self.total_trades = 0
        self.wins = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.daily_profit = 0.0
        
        # [PRO] Blindagem de Calendário Econômico
        self.calendar_events = []
        self._load_economic_calendar()

    def _load_economic_calendar(self):
        """Carrega os dados de calendário econômico (3 estrelas) para ativar Veto de Liquidez (-3min a +3min)."""
        try:
            cal_path = os.path.join(os.getcwd(), "data", "economic_calendar.json")
            if os.path.exists(cal_path):
                with open(cal_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        if item.get("impact", 0) >= 3:
                            evt_time = datetime.strptime(item["time"], "%H:%M").time()
                            t_start = (datetime.combine(datetime.today(), evt_time) - timedelta(minutes=3)).time()
                            t_end = (datetime.combine(datetime.today(), evt_time) + timedelta(minutes=3)).time()
                            self.calendar_events.append({"start": t_start, "end": t_end, "event": item["event"]})
                logging.info(f"📅 CALENDÁRIO ECONÔMICO: {len(self.calendar_events)} alertas críticos carregados para Blindagem Ativa.")
        except Exception as e:
            logging.error(f"Erro ao carregar economic_calendar.json: {e}")

    def is_time_allowed(self):
        """Verifica se o horário atual é permitido para operar."""
        now = datetime.now().time()
        for start, end in self.forbidden_hours:
            if start <= now <= end:
                return False
                
        # [PRO] Blindagem de Calendário Econômico (Veto de Liquidez HFT)
        if hasattr(self, 'calendar_events'):
            for event in self.calendar_events:
                if event["start"] <= now <= event["end"]:
                    logging.warning(f"🛑 VETO DE CALENDÁRIO ATIVO: Operação blindada devido a {event['event']}")
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

    def check_velocity_limit(self, current_profit_points, elapsed_seconds):
        """
        [FASE 2] Parede de Exaustão.
        Se a operação entrou, negativou rapidamente e ficou amarrada no negativo por muito tempo, 
        aborta a operação precocemente antes do STOP CHEIO.
        """
        if elapsed_seconds > self.velocity_time_limit_sec and current_profit_points <= self.velocity_drawdown_limit:
            logging.warning(f"⏳ LIMITE DE VELOCIDADE EXCEDIDO: Operação amarrada em {current_profit_points} pts por {elapsed_seconds:.1f}s. Abortando cedo.")
            return True, "LIMITE_VELOCIDADE_DRAWDOWN"
            
        return False, "VELOCITY_OK"

    def check_time_stop(self, elapsed_seconds, current_profit_points):
        """
        [FASE 2] Time-Based Stop.
        Se a operação exceder o tempo máximo e não estiver com lucro expressivo, encerra.
        Garante rotação de capital e evita 'ficar pendurado' em mercados mortos.
        """
        max_sec = self.max_trade_duration_min * 60
        if elapsed_seconds > max_sec:
            if current_profit_points < 20: # Se estiver no prejuízo ou lucro pífio
                logging.info(f"⏱️ [TIME-STOP] Operação excedeu {self.max_trade_duration_min}min sem tração. Encerrando.")
                return True
        return False

    def calculate_quarter_kelly(self, balance, win_rate_pct, profit_factor, risk_per_trade_points=150.0, point_value=0.20):
        """
        [HFT ELITE] Calcula Volume via Quarter-Kelly (0.25 f*).
        Fórmula: f* = (p(b+1)-1)/b
        Onde: p = probabilidade (win_rate), b = odds (profit_factor)
        """
        p = win_rate_pct / 100.0
        b = max(0.5, profit_factor)
        edge = (p * (b + 1)) - 1
        f_star = edge / b
        target_fraction = max(0.01, f_star * self.kelly_fraction)
        target_fraction = min(0.05, target_fraction) # Max 5% arriscado
        risk_amount = balance * target_fraction
        volume = risk_amount / (risk_per_trade_points * point_value)
        return max(1.0, float(volume))

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
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    raw_data = json.load(f)
                    params = raw_data.get("params", raw_data)
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
        Retorna parâmetros calculados para envio de ordem OCO.
        [SOTA v5] Suporta tp_multiplier e alvos baseados em ATR/Regime.
        """
        import MetaTrader5 as mt5
        
        if current_atr and current_atr > 0:
            tp_mult = 1.0 
            sl_mult = 1.3
            if regime == 1: tp_mult = 1.5
            elif regime == 0: tp_mult = 0.8
            sl_points = float(current_atr * sl_mult)
            tp_points = float(current_atr * tp_mult)
        elif symbol in self.dynamic_params:
            d_params = self.dynamic_params[symbol]
            sl_points = float(d_params.get("sl", 130.0))
            tp_points = float(d_params.get("tp", 100.0))
        elif "WDO" in symbol or "DOL" in symbol:
            sl_points = 5.0
            tp_points = 10.0
        elif "WIN" in symbol or "IND" in symbol:
            sl_points = 130.0
            tp_points = 100.0
        else:
            sl_points = 0.0
            tp_points = 0.0

        if tp_multiplier != 1.0 and tp_points > 0:
            tp_points *= tp_multiplier

        # Limites de segurança
        if "WIN" in symbol:
            sl_points = max(100.0, min(300.0, sl_points))
            tp_points = max(100.0, min(400.0, tp_points))
        elif "WDO" in symbol or "DOL" in symbol:
            sl_points = max(3.0, min(15.0, sl_points))
            tp_points = max(5.0, min(30.0, tp_points))

        sl, tp = 0.0, 0.0
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

            sl = self._quantize_price(symbol, sl)
            tp = self._quantize_price(symbol, tp)
            sl = self._apply_anti_violinada(symbol, sl, side)
            tp = self._apply_anti_violinada(symbol, tp, side)

        return {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": "",
            "type": type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "volume": float(volume),
            "deviation": self.max_deviation,
            "magic": 123456,
            "comment": "QuantumTrade B3 OCO",
            "type_time": mt5.ORDER_TIME_DAY,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

    def _quantize_price(self, symbol, price):
        if price <= 0: return 0.0
        tick_size = 0.5 if ("WDO" in symbol or "DOL" in symbol) else 5.0 if ("WIN" in symbol or "IND" in symbol) else 0.01
        return round(price / tick_size) * tick_size if tick_size > 0 else price

    def _apply_anti_violinada(self, symbol, price, side):
        if price <= 0: return price
        try:
            is_wdo = "WDO" in symbol or "DOL" in symbol
            round_interval = 10.0 if is_wdo else 100.0
            offset = 0.5 if is_wdo else 15.0
            if price < round_interval: return price
            remainder = price % round_interval
            danger_zone = round_interval * 0.1
            if remainder == 0 or remainder < danger_zone or remainder > (round_interval - danger_zone):
                new_price = price - offset if side == "buy" else price + offset if side == "sell" else price
                return self._quantize_price(symbol, new_price)
            return price
        except: return price
