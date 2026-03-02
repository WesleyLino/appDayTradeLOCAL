from datetime import datetime, time, timedelta
import logging
import math
import numpy as np
import json
import os

# [ANTIVIBE-CODING] - Classe Cr??tica de Risco
class RiskManager:
    def __init__(self, max_daily_loss=600.00, daily_trade_limit=3, max_daily_loss_pct=0.60):
        self.max_daily_loss = max_daily_loss
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_trade_limit = daily_trade_limit 
        self.max_deviation = 5 
        self.allow_autonomous = True 
        self.dry_run = False # [REAL-EXECUTION-ACTIVE] - Ativa????o de ordens reais no MT5
        # [ANTIVIBE-CODING] - Limites de Perda Agressivos
        self.forbidden_hours = [
            (time(8, 55), time(9, 5)),   # Abertura
            (time(12, 0), time(13, 0)),  # Almo??o/Baixa liquidez
            (time(16, 55), time(18, 0))  # Fechamento
        ]
        
        # [SOTA] Trailing Stop Parameters (Default WIN Champion)
        self.trailing_trigger = 70.0  # Ativa com 70 pontos (Otimizado)
        self.trailing_lock = 50.0    # Trava 50 pontos iniciais
        self.trailing_step = 20.0    # Move a cada 20 pontos de avan??o
        
        # [URGENTE] Breakeven Parameters
        self.be_trigger = 50.0       # Ativa com 50 pontos de lucro (Otimizado)
        self.be_lock = 0.0           # Move para o pre??o de entrada (0.0 de lucro garantido)
        
        # [FASE 2] Gest??o de M??ltiplos Contratos e Sa??das Parciais
        self.base_volume = 2.0       # Lote de entrada padr??o (multi-lote para parciais)
        self.partial_volume = 1.0    # Lote a ser descarregado na primeira parcial
        self.partial_profit_points = 50.0 # Gatilho em pontos para executar a zeragem parcial
        
        # [FASE 2] Velocity Limit (Drawdown Acelerado no Tempo)
        self.velocity_time_limit_sec = 20.0     # Segundos m??ximos engatado negativamente
        self.velocity_drawdown_limit = -30.0    # Pontos negativos que ativam o timeout r??pido
        
        # [HFT ELITE] Alpha Fade (Decaimento de Ordem)
        self.alpha_fade_timeout = 10.0          # Segundos antes de cancelar ordem limite n??o executada
        
        # [FASE 28] DYNAMIC PARAMS CACHE
        self.dynamic_params = {} # Carregado via load_optimized_params

        # [PERFORMANCE METRICS]
        self.total_trades = 0
        self.wins = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.daily_profit = 0.0
        
        # [PRO] Blindagem de Calend??rio Econ??mico
        self.calendar_events = []
        self._load_economic_calendar()

    def _load_economic_calendar(self):
        """Carrega os dados de calend??rio econ??mico (3 estrelas) para ativar Veto de Liquidez (-3min a +3min)."""
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
                logging.info(f"???? CALEND??RIO ECON??MICO: {len(self.calendar_events)} alertas cr??ticos carregados para Blindagem Ativa.")
        except Exception as e:
            logging.error(f"Erro ao carregar economic_calendar.json: {e}")

    def is_time_allowed(self):
        """Verifica se o hor??rio atual ?? permitido para operar."""
        now = datetime.now().time()
        for start, end in self.forbidden_hours:
            if start <= now <= end:
                return False
                
        # [PRO] Blindagem de Calend??rio Econ??mico (Veto de Liquidez HFT)
        if hasattr(self, 'calendar_events'):
            for event in self.calendar_events:
                if event["start"] <= now <= event["end"]:
                    logging.warning(f"???? VETO DE CALEND??RIO ATIVO: Opera????o blindada devido a {event['event']}")
                    return False
                    
        return True

    def validate_environmental_risk(self, ping_ms, spread_points, max_ping=150.0, max_spread=15.0):
        """
        Avalia se a conectividade com a B3 est?? est??vel e se o mercado possui liquidez b??sica (N??o-Estressado).
        Bloqueia envios com l??gicas Anti-Slippage.
        """
        if ping_ms is not None and ping_ms > max_ping:
            return False, f"Ping Muito Alto/Lat??ncia Severa (B3): {ping_ms:.1f}ms (Aceit??vel: <= {max_ping}ms)"
            
        if spread_points is not None and spread_points > max_spread:
             return False, f"Spread Alargado (Vazio de Liquidez/Not??cia/Leil??o): {spread_points} pts (Aceit??vel: <= {max_spread} pts)"
             
        return True, "Ambiente (Ping/Spread) OK"

    def check_equity_kill_switch(self, current_equity, starting_equity):
        """
        O Bot??o de P??nico Incondicional.
        Puxa a leitura bruta de Equity (Capital L??quido com Ordens Flutuantes) e desliga a m??quina se exceder Max Daily Loss.
        """
        if current_equity <= 0 or starting_equity <= 0:
            return True, "Kill Switch: Ignorado (Sem dados de Equity base)"
            
        drawdown_value = starting_equity - current_equity
        if drawdown_value >= self.max_daily_loss:
            return False, f"KILL SWITCH ATIVADO: Drawdown Extremo (Flutuante). Perca Atual: R$ {drawdown_value:.2f} >= Limite Master: R$ {self.max_daily_loss:.2f}"
            
        return True, "Equity Seguro"

    def check_velocity_limit(self, current_profit_points, elapsed_seconds):
        """
        [FASE 2] Parede de Exaust??o.
        Se a opera????o entrou, negativou rapidamente e ficou amarrada no negativo por muito tempo, 
        aborta a opera????o precocemente antes do STOP CHEIO.
        """
        if elapsed_seconds > self.velocity_time_limit_sec and current_profit_points <= self.velocity_drawdown_limit:
            logging.warning(f"??? LIMITE DE VELOCIDADE EXCEDIDO: Opera????o amarrada em {current_profit_points} pts por {elapsed_seconds:.1f}s. Abortando cedo.")
            return True, "LIMITE_VELOCIDADE_DRAWDOWN"
            
        return False, "VELOCITY_OK"

    def calculate_psr(self, returns_list, benchmark_sr=0.0):
        """
        Calcula o Probabilistic Sharpe Ratio (PSR).
        Determina se a performance observada ?? estatisticamente significativa.
        """
        n = len(returns_list)
        if n < 30: # Amostra m??nima conforme econometria para converg??ncia
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
        
        # F??rmula de Bailey and L??pez de Prado
        v = (1 - skew * sr + (kurt / 4) * (sr**2))
        if v <= 0: return 0.0
        
        z = (sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(v)
        
        # CDF Normal Aproximada (ERF)
        psr = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        return psr

    def validate_reliability(self, returns_list):
        """
        Veto AlphaX: Bloqueia se a confiabilidade estat??stica (PSR) for < 95%.
        """
        if not returns_list: return True, 1.0
        
        psr = self.calculate_psr(returns_list)
        if psr < 0.95:
            return False, psr
        return True, psr

    def should_force_close(self):
        """Verifica se passou das 17:50 para encerramento compuls??rio."""
        now = datetime.now().time()
        return now >= time(17, 50)

    def validate_market_condition(self, symbol, regime, current_atr, avg_atr):
        """
        Valida se as condi????es de mercado s??o seguras para operar.
        Regras (Compliance com project_rules.json):
        1. Rejeita se Regime = 2 (RU??DO/ALTA VOLATILIDADE).
        2. Rejeita se Volatilidade (ATR) > 3x ATR M??dio (Circuit Breaker).
        3. Panic Threshold ajustado por ativo.
        """
        # Regra 1: Regime de Mercado (0=Indefinido, 1=Tend??ncia, 2=Ru??do)
        if regime == 2:
            return {
                "allowed": False,
                "reason": "Market Regime is NOISE/VOLATILE (2)"
            }

        # Regra 2: Circuit Breaker Din??mico (Relativo)
        if avg_atr > 0 and current_atr > (3 * avg_atr):
             return {
                "allowed": False,
                "reason": f"Circuit Breaker: ATR {current_atr:.1f} > 3x Avg {avg_atr:.1f}"
            }
            
        # Regra 3: Panic Threshold Absoluto (Fallback se m??dia estiver descalibrada)
        # WIN: ~150-300 pts ?? alto. 500 ?? extremo.
        # WDO: ~5-10 pts ?? alto. 20 ?? extremo.
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
        # Se macro_change_pct for 0.0 (n??o detectado), ignora o filtro
        if macro_change_pct == 0.0:
            return True, "Neutro (N/A)"

        if side == "buy" and macro_change_pct < -0.5:
             return False, f"Macro Bearish (S&P500 {macro_change_pct:.2f}%)"
             
        if side == "sell" and macro_change_pct > 0.5:
             return False, f"Macro Bullish (S&P500 {macro_change_pct:.2f}%)"
             
        return True, "Macro OK"

    def record_trade_result(self, pnl):
        """Atualiza as m??tricas de performance ap??s um trade."""
        self.total_trades += 1
        self.daily_profit += pnl
        if pnl > 0:
            self.wins += 1
            self.gross_profit += pnl
        else:
            self.gross_loss += abs(pnl)

    def get_performance_metrics(self):
        """Retorna m??tricas calculadas."""
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
        Verifica se o limite de perda di??ria foi atingido.
        total_profit: Soma do Lucro Realizado + Flutuante.
        """
        # Se total_profit for negativo e maior (em magnitude) que o limite
        if total_profit <= -self.max_daily_loss:
            return False, f"Daily loss limit reached: {total_profit:.2f} <= -{self.max_daily_loss:.2f}"
        return True, "OK"

    def check_aggressive_risk(self, daily_pnl, initial_balance=1000.0):
        """
        [AGRESSIVO] Verifica se o preju??zo do dia atingiu o limite percentual.
        Ignora a contagem de trades enquanto houver capital e sinal.
        """
        limit = initial_balance * self.max_daily_loss_pct
        if daily_pnl <= -limit:
            return False, f"Limite de perda agressivo atingido: R$ {abs(daily_pnl):.2f} (>= {int(self.max_daily_loss_pct*100)}%)"
        return True, "Risco OK"

    def check_trade_limit(self, current_trade_count):
        """
        Verifica se o limite de trades di??rios foi atingido.
        [AGRESSIVO] No modo 60%, este m??todo pode ser ignorado pelo bot.
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
             logging.error(f"CIRCUIT BREAKER: Volatilidade (ATR: {current_atr:.2f}) > 3x M??dia ({avg_atr:.2f})")
             return False
        return True

    def calculate_volatility_sizing(self, balance: float, current_atr: float, point_value: float = 0.20, risk_pct: float = 0.01) -> float:
        """
        [SOTA] Calcula o tamanho do lote baseado na volatilidade (Volatility Sizing).
        Objetivo: Equalizar o risco financeiro ($ em risco) independente da volatilidade.
        
        F??rmula: Lotes = (Saldo * Risco%) / (ATR * Valor_Ponto)
        
        Exemplo WIN: 
          Saldo=1000, Risco=1% ($10), ATR=100pts, ValorPonto=$0.20
          Stop Financeiro Oculto ??? 1 ATR
          Lotes = 10 / (100 * 0.20) = 10 / 20 = 0.5 (Arredonda para 1 min)
          
        Args:
            balance: Saldo atual da conta.
            current_atr: Volatilidade atual (em pontos).
            point_value: Valor financeiro por ponto (WIN=0.20, WDO=10.0).
            risk_pct: % do saldo a arriscar por trade (Default 1%).
            
        Returns:
            float: Quantidade de lotes sugerida (n??o arredondada inteira, tratar no caller).
        """
        if current_atr <= 0 or point_value <= 0:
            return 1.0 # Fallback conservador
            
        risk_amount = balance * risk_pct
        volatility_cost = current_atr * point_value
        
        if volatility_cost == 0: return 1.0
        
        suggested_lots = risk_amount / volatility_cost
        return float(suggested_lots)

    def load_optimized_params(self, symbol, json_path):
        """Carrega par??metros otimizados (SL, TP, etc) de um arquivo JSON (Suporta V22 Golden)."""
        import json
        import os
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    
                    # Suporte ao formato v22_locked_params.json (Golden)
                    if "strategy_params" in raw_data:
                        params = raw_data["strategy_params"]
                        logging.info(f"??????? RISK: Detectada estrutura GOLDEN V22 para {symbol}.")
                    else:
                        # Fallback para o formato do optimizer.py
                        params = raw_data.get("params", raw_data)
                    
                    # Mapeamento robusto de nomes
                    mapped_params = {
                        "sl": params.get("sl_dist", params.get("sl", 150.0)),
                        "tp": params.get("tp_dist", params.get("tp", 400.0)),
                        "rsi_period": params.get("rsi_period"),
                        "vol_spike_mult": params.get("vol_spike_mult"),
                        "trailing_trigger": params.get("trailing_trigger"),
                        "trailing_lock": params.get("trailing_lock")
                    }
                    
                    # Atualiza os par??metros internos da classe se os campos existirem no JSON
                    if mapped_params["trailing_trigger"]: self.trailing_trigger = float(mapped_params["trailing_trigger"])
                    if mapped_params["trailing_lock"]: self.trailing_lock = float(mapped_params["trailing_lock"])
                    
                    self.dynamic_params[symbol] = mapped_params
                    logging.info(f"??? RISK: Par??metros para {symbol} mapeados e aplicados: {mapped_params}")
                    return True
            except Exception as e:
                logging.error(f"??? RISK: Erro ao carregar par??metros de {json_path}: {e}")
        return False


    def get_order_params(self, symbol, type, price, volume, current_atr=None, regime=None, tp_multiplier=1.0):
        """
        Retorna par??metros calculados para envio de ordem OCO (One Cancels Other).
        Detecta automaticamente se ?? WIN ou WDO para definir stops.
        Agora suporta alvos din??micos baseados no ATR e Regime para adapta????o ?? volatilidade.
        [SOTA v5] Suporta tp_multiplier para compensa????o de spread.
        """
        import MetaTrader5 as mt5
        
        # Defini????o de Stops por Ativo (Padr??o Day Trade)
        # PRIORIDADE 1: Alvos Din??micos baseados em ATR (Se dispon??vel)
        if current_atr and current_atr > 0:
            # Multiplicadores baseados na recalibra????o vencedora de 23/02
            # [PRO-MAX] Ajuste por Regime
            tp_mult = 1.0 
            sl_mult = 1.3

            if regime == 1: # Tend??ncia Clara: Buscar alvos maiores
                tp_mult = 1.5
                logging.info("???? REGIME TEND??NCIA: Alvo TP expandido (1.5x ATR)")
            elif regime == 0: # Indefinido/Lateral: Alvos Curtos
                tp_mult = 0.8
                logging.info("?????? REGIME LATERAL: Alvo TP reduzido (0.8x ATR)")
            
            sl_points = float(current_atr * sl_mult)
            tp_points = float(current_atr * tp_mult)
            
        # PRIORIDADE 2: Par??metros Otimizados dinamicamente via JSON
        elif symbol in self.dynamic_params:
            d_params = self.dynamic_params[symbol]
            sl_points = float(d_params.get("sl", 130.0))
            tp_points = float(d_params.get("tp", 100.0))
            logging.info(f"???? RISK: Usando par??metros OTIMIZADOS para {symbol}: SL={sl_points}, TP={tp_points}")
        elif "WDO" in symbol or "DOL" in symbol:
            sl_points = 5.0   # 5 pontos no D??lar
            tp_points = 10.0  # 10 pontos no D??lar
        elif "WIN" in symbol or "IND" in symbol:
            sl_points = 130.0 # 130 pontos no ??ndice
            tp_points = 100.0 # 100 pontos no ??ndice (Target Recalibrado)
        else:
            sl_points = 0.0
            tp_points = 0.0

        # [SOTA v5] Aplica????o do Multiplicador de Precis??o (Spread-Adjusted)
        if tp_multiplier != 1.0 and tp_points > 0:
            old_tp = tp_points
            tp_points *= tp_multiplier
            logging.info(f"???? SOTA v5 PRECISION: TP Adjusted by Spread Component: {old_tp:.1f} -> {tp_points:.1f} (Mult: {tp_multiplier:.3f})")

        # Limites de seguran??a (Sanity Check)
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

            # --- HFT DEFENSIVE MATH: QUANTIZAR PRE??O (B3 TICK SIZE) ---
            sl = self._quantize_price(symbol, sl)
            tp = self._quantize_price(symbol, tp)
            # ----------------------------------------------------------

            # --- HFT ANTI-VIOLINADA (FASE 5b) ---
            # Ajuste fino para n??o deixar pedra em n??mero redondo
            sl = self._apply_anti_violinada(symbol, sl, side)
            tp = self._apply_anti_violinada(symbol, tp, side)
            # ------------------------------------

        return {
            "action": mt5.TRADE_ACTION_PENDING, # Usar ordens LIMIT conforme Master Plan
            "symbol": "", # Ser?? preenchido no main.py
            "type": type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "volume": float(volume),
            "deviation": self.max_deviation,
            "magic": 123456,
            "comment": "QuantumTrade B3 OCO",
            "type_time": mt5.ORDER_TIME_DAY, # Ordem v??lida at?? o final do dia (Day Trade)
            "type_filling": mt5.ORDER_FILLING_RETURN, # Permite execu????o parcial (Limit Orders na B3)
        }
    def _quantize_price(self, symbol, price):
        """
        Garante que o pre??o seja um m??ltiplo do tick size (B3).
        WIN: 5 pontos | WDO: 0.5 pontos
        """
        if price <= 0: return 0.0
        
        if "WDO" in symbol or "DOL" in symbol:
            tick_size = 0.5
        elif "WIN" in symbol or "IND" in symbol:
            tick_size = 5.0
        else:
            return price # Outros ativos

        # Arredonda para o m??ltiplo mais pr??ximo
        return round(price / tick_size) * tick_size

    def _apply_anti_violinada(self, symbol, price, side):
        """
        Ajusta o pre??o de Stop/TP para evitar n??meros redondos (Violinada).
        Evita colocar ordens exatas em 'XX.000' ou 'XX.500'.
        Desloca 5 pts (WIN) ou 0.5 pts (WDO) para 'esconder' a ordem.
        """
        if price <= 0: return price
        
        try:
            is_wdo = "WDO" in symbol or "DOL" in symbol
            
            # Par??metros de arredondamento (HFT v2.1: Defensive Math)
            if is_wdo:
                round_interval = 10.0
                offset = 0.5
            else:
                round_interval = 100.0
                offset = 15.0
            
            # PROTE????O: Se por algum motivo o pre??o for muito pequeno para o intervalo
            if price < round_interval:
                return price

            # Verificar proximidade com n??mero redondo
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
                
                # Garantir que ap??s o offset, o pre??o continue quantizado (IMPORTANT??SSIMO)
                new_price = self._quantize_price(symbol, new_price)
                
                logging.info(f"??????? ANTI-VIOLINADA: Ajustando {price} -> {new_price} ({symbol})")
                return new_price
            
            return price
        except Exception as e:
            logging.error(f"Erro Cr??tico Anti-Violinada: {e}")
            return price
