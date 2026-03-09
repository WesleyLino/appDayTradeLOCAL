from datetime import datetime, time, timedelta
import logging
import math
import numpy as np
import json
import os

# [ANTIVIBE-CODING] - Classe Crítica de Risco
class RiskManager:
    def __init__(self, max_daily_loss=100.00, daily_trade_limit=999, max_daily_loss_pct=0.20, initial_balance=500.0):
        self.max_daily_loss = max_daily_loss
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_trade_limit = daily_trade_limit # v52.1 - MODO ILIMITADO
        self.initial_balance = initial_balance
        self.max_deviation = 5 
        self.allow_autonomous = True 
        self.dry_run = False # [REAL-EXECUTION-ACTIVE] - Ativação de ordens reais no MT5
        # [ANTIVIBE-CODING] - Limites de Perda Agressivos
        self.forbidden_hours = [
            (time(8, 55), time(9, 10)),  # Abertura (Aguarda formação das 10 primeiras velas de M1 para cálculo de volatilidade)
            (time(12, 0), time(13, 0)),  # Almoço/Baixa liquidez
            (time(16, 55), time(18, 0))  # Fechamento
        ]
        
        # [SOTA] Parâmetros de Trailing Stop (Campeão WIN Padrão)
        self.trailing_trigger = 70.0  # Ativa com 70 pontos (Otimizado)
        self.trailing_lock = 50.0    # Trava 50 pontos iniciais
        self.trailing_step = 20.0    # Move a cada 20 pontos de avanço
        
        # [v52.1] Breakeven Ultra-Rápido
        self.be_trigger = 25.0       # Ativa com 25 pontos de lucro (Garante o zero rápido)
        self.be_lock = 0.0           # Move para o preço de entrada
        
        # [v52.0] Scaling Out (Saída Parcial HFT)
        self.base_volume = 2.0       # 2 contratos para permitir parcial
        self.partial_volume = 1.0    # Zera 1 contrato na parcial
        self.partial_profit_points = 30.0 # [v52.1] Lucro travado cedo para maior assertividade
        
        # [FASE 2] Velocity Limit (Drawdown Acelerado no Tempo)
        self.velocity_time_limit_sec = 20.0     # Segundos máximos engatado negativamente
        self.velocity_drawdown_limit = -30.0    # Pontos negativos que ativam o timeout rápido
        
        # [HFT ELITE] Alpha Fade (Decaimento de Ordem)
        self.alpha_fade_timeout = 10.0          # Segundos antes de cancelar ordem limite não executada
        
        # [v52.0] Alpha Decay (Fuga por Inatividade)
        self.max_trade_duration_min = 3.0       # 3 minutos (3 candles M1) sem evolução = Sai a mercado
        
        # [v50.1] TIME-DECAYING TP
        self.tp_decay_per_min = 0.05            # Decaimento de 5% por minuto
        
        # [v50.1] TRAILING ESTRANGULADOR (VENDA)
        self.sell_trailing_step_atr = 0.3        # Passo de 0.3 ATR para vendas (Paranoia Institucional)
        
        # [FASE 2] Quarter-Kelly (Ajuste de Expectativa)
        self.kelly_fraction = 0.25              # Quarter-Kelly (Segurança HFT)

        # [NOVO] Switches de Controle Manual do Frontend
        self.enable_news_filter = False
        # [ANTIVIBE-CODING] - Filtros de Proteção Institucional
        self.enable_calendar_filter = True
        self.enable_macro_filter = True
        
        # [FASE 28] DYNAMIC PARAMS CACHE
        self.dynamic_params = {} # Carregado via load_optimized_params

        # [MÉTRICAS DE PERFORMANCE]
        self.total_trades = 0
        self.wins = 0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.daily_profit = 0.0
        
        # [PRO] Blindagem de Calendário Econômico
        self.calendar_events = []
        self._load_economic_calendar()

        # [MELHORIA-CALENDARIO] Estado de Momentum Pós-Evento
        self.post_event_momentum = False        # True durante os 10 min após fim de um veto
        self.post_event_momentum_until = None   # datetime de expiração do modo momentum
        self.post_event_name = ""               # Nome do evento que originou o momentum

    def _load_economic_calendar(self):
        """Carrega dados de calendário econômico (impacto >= 3) para Veto de Liquidez.

        Campos suportados em economic_calendar.json:
          - time         (obrigatório) HH:MM do evento
          - impact       (obrigatório) 1-3, só eventos com 3 são carregados
          - event        (obrigatório) nome do evento
          - date         (opcional)  YYYY-MM-DD — se presente, o veto só é ativado nesta data
          - window_minutes (opcional) minutos de veto antes/depois (padrão: 3)
        """
        try:
            cal_path = os.path.join(os.getcwd(), "data", "economic_calendar.json")
            if not os.path.exists(cal_path):
                return

            today_str = datetime.today().strftime("%Y-%m-%d")
            loaded = 0

            with open(cal_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                if item.get("impact", 0) < 3:
                    continue

                # [MELHORIA-1] Suporte a datas específicas — ignora eventos de outros dias
                event_date = item.get("date")
                if event_date and event_date != today_str:
                    logging.debug(f"📅 Evento '{item['event']}' ignorado (data: {event_date} ≠ hoje: {today_str})")
                    continue

                # [MELHORIA-4] Janela de veto configurável por evento (padrão: 3 min)
                window = int(item.get("window_minutes", 3))

                evt_time = datetime.strptime(item["time"], "%H:%M").time()
                evt_dt   = datetime.combine(datetime.today(), evt_time)
                t_start  = (evt_dt - timedelta(minutes=window)).time()
                t_end    = (evt_dt + timedelta(minutes=window)).time()

                self.calendar_events.append({
                    "start":          t_start,
                    "end":            t_end,
                    "momentum_end":   (evt_dt + timedelta(minutes=window + 10)).time(),  # [MELHORIA-2]
                    "event":          item["event"],
                })
                loaded += 1

            logging.info(f"📅 CALENDÁRIO ECONÔMICO: {loaded} alertas críticos carregados para Blindagem Ativa.")

            # [ALERTA DE EXPIRAÇÃO] Avisa quando todos os eventos cadastrados já expiraram
            if loaded == 0 and data:
                all_dates = [
                    item.get("date") for item in data
                    if item.get("impact", 0) >= 3 and item.get("date")
                ]
                if all_dates:
                    ultima = max(all_dates)
                    logging.critical(
                        f"🚨 [CALENDÁRIO EXPIRADO] Todos os {len(all_dates)} eventos cadastrados "
                        f"já passaram! Último evento: {ultima}. "
                        f"AÇÃO NECESSÁRIA: Acrescente novas datas em 'data/economic_calendar.json' "
                        f"e reinicie o backend."
                    )

        except Exception as e:
            logging.error(f"Erro ao carregar economic_calendar.json: {e}")

    def calculate_dynamic_tp(self, base_tp, current_atr):
        """
        [V22.2] ALVO DINÂMICO (TP) POR VOLATILIDADE.
        Reduz o Take Profit em 15% se a volatilidade (ATR) estiver acima de 120.
        Objetivo: Garantir o lucro no bolso em mercados rápidos antes da reversão.
        """
        if current_atr > 120.0:
            new_tp = base_tp * 0.85
            logging.info(f"🎯 [ALVO DINÂMICO] ATR {current_atr:.1f} > 120. Ajustando TP: {base_tp} -> {new_tp:.1f} (-15%)")
            return float(new_tp)
        return float(base_tp)

    def check_gap_safety(self, opening_price, prev_close):
        """
        [V22.2] FILTRO DE GAP DE ABERTURA.
        Veta operações se o Gap de abertura for superior a 800 pontos.
        """
        gap_size = abs(opening_price - prev_close)
        if gap_size > 800.0:
            logging.warning(f"⚠️ [FILTRO DE GAP] Abertura com gap de {gap_size:.1f} pts (> 800). Risco de anomalia detectado.")
            return False, f"Gap Excessivo ({gap_size:.1f} pts)"
        return True, "Gap Seguro"

    def is_time_allowed(self):
        """Verifica se o horário atual é permitido para operar.

        Retorna:
          - False:  horário proibido (forbidden_hours) ou veto de calendário ativo
          - True:   operação liberada

        Efeitos colaterais:
          - self.post_event_momentum: True durante os 10 min pós-evento [MELHORIA-2]
        """
        now = datetime.now().time()
        now_dt = datetime.now()

        # --- Horários proibidos fixos ---
        for start, end in self.forbidden_hours:
            if start <= now <= end:
                self.post_event_momentum = False
                return False

        # --- [PRO] Blindagem de Calendário Econômico ---
        if hasattr(self, 'calendar_events') and hasattr(self, 'enable_calendar_filter') and self.enable_calendar_filter:
            for event in self.calendar_events:

                # Janela de Veto Total (pré + pós evento)
                if event["start"] <= now <= event["end"]:
                    logging.warning(
                        f"🛑 VETO DE CALENDÁRIO ATIVO: Operação blindada devido a {event['event']}"
                    )
                    self.post_event_momentum = False
                    return False

                # [MELHORIA-2] Janela de Momentum Pós-Evento (10 min após fim do veto)
                if event["end"] < now <= event.get("momentum_end", event["end"]):
                    if not self.post_event_momentum:
                        logging.info(
                            f"🚀 [MOMENTUM PÓS-EVENTO] Janela de 10 min ativa após '{event['event']}'. "
                            "Threshold relaxado para 65%."
                        )
                    self.post_event_momentum = True
                    self.post_event_name = event["event"]
                    return True  # Libera — com threshold especial

        # Fora de qualquer janela de evento
        self.post_event_momentum = False
        return True

    def is_direction_allowed(self, direction: str, sentiment_score: float) -> bool:
        """[MELHORIA-3] Veto Direcional — bloqueia apenas o lado contrário ao sentimento.

        Chamado quando o sistema está em Veto de Calendário ou regime de risco alto.

        Args:
            direction:       "BUY" ou "SELL"
            sentiment_score: float entre -1.0 e +1.0 (do NewsSentimentWorker)

        Returns:
            True  → direção permitida pelo sentimento
            False → direção vetada (lado contrário ao sentimento)
        """
        # Se o usuário desativou manualmente o filtro de notícias, libera as operações incondicionalmente desta barreira
        if hasattr(self, 'enable_news_filter') and not self.enable_news_filter:
            return True

        if sentiment_score > 0.5:
            # Mercado com viés BULLISH forte → bloqueia VENDA
            if direction == "SELL":
                logging.warning(
                    f"⛔ [VETO DIRECIONAL] VENDA bloqueada: sentimento BULLISH ({sentiment_score:.2f})"
                )
                return False
            return True

        if sentiment_score < -0.5:
            # Mercado com viés BEARISH forte → bloqueia COMPRA
            if direction == "BUY":
                logging.warning(
                    f"⛔ [VETO DIRECIONAL] COMPRA bloqueada: sentimento BEARISH ({sentiment_score:.2f})"
                )
                return False
            return True

        # Sentimento neutro (-0.5 a +0.5) → bloqueia ambos os lados
        logging.info(
            f"⛔ [VETO DIRECIONAL] Sentimento neutro ({sentiment_score:.2f}). "
            f"Operação {direction} suspensa."
        )
        return False

    def is_macro_allowed(self, direction: str, synthetic_idx: float) -> bool:
        """[ANTIVIBE-CODING] Veto Macro via Blue Chips/S&P 500.
        
        Bloqueia operações se o mercado global estiver fortemente contra a direção.
        Respeita o switch de controle manual do Dashboard.
        """
        if not getattr(self, 'enable_macro_filter', True):
            return True

        # Se Blue Chips estão fortemente contra, aplica veto preventivo
        if direction == "BUY" and synthetic_idx < -0.2:
            logging.warning(f"🛑 [VETO MACRO] COMPRA bloqueada: Blue Chips caindo forte ({synthetic_idx:.2f}%)")
            return False
        elif direction == "SELL" and synthetic_idx > 0.2:
            logging.warning(f"🛑 [VETO MACRO] VENDA bloqueada: Blue Chips subindo forte ({synthetic_idx:.2f}%)")
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
            return True, "LIMITE_VELOCIDADE_PERDA"
            
        return False, "VELOCIDADE_OK"

    def check_time_stop(self, elapsed_seconds, current_profit_points, current_atr=None):
        """
        [v50 - MASTER] Time-Based Stop Elástico.
        Se a operação entrou e em 3-5 minutos não explodiu a favor, encerra.
        Fundamento: Se o Alpha não se pagou rápido, a premissa de microestrutura evaporou.
        """
        # Limiar de tempo dinâmico: Se ATR está alto (mercado rápido), o tempo é menor (180s = 3min)
        # Se ATR está baixo (mercado lento), tolera até 300s (5min).
        max_time = 180 if (current_atr and current_atr > 300) else 300
        
        if elapsed_seconds >= max_time:
            # Se não atingiu pelo menos o alvo de breakeven, sai para liberar margem
            if current_profit_points < self.be_trigger:
                logging.warning(f"⏰ [TIME-STOP MASTER] {max_time}s atingidos. PnL {current_profit_points:.1f} abaixo do gatilho {self.be_trigger}. Abortando.")
                return True
        return False

    def allow_pyramiding(self, current_profit_points, signal_strength, current_volume, 
                         symbol=None, profit_threshold=None, signal_threshold=None, max_volume=None):
        """
        [v50 - MASTER] Piramidação Matemática (Scaling In).
        Suporta injeção de parâmetros dinâmicos via self.dynamic_params.
        """
        # Fallback para parâmetros dinâmicos se disponíveis
        d_params = self.dynamic_params.get(symbol, {}) if symbol else {}
        
        trigger = profit_threshold if profit_threshold is not None else d_params.get("pyramid_profit_threshold", self.be_trigger)
        sig_threshold = signal_threshold if signal_threshold is not None else d_params.get("pyramid_signal_threshold", 1.2)
        max_vol = max_volume if max_volume is not None else d_params.get("pyramid_max_volume", 3)
        
        if current_profit_points >= trigger and abs(signal_strength) >= sig_threshold:
            if current_volume < max_vol:
                logging.info(f"💎 [PIRAMIDAÇÃO DINÂMICA] Autorizada! Lucro {current_profit_points:.1f} | Fluxo: {signal_strength:.2f} | Vol Atual: {current_volume}")
                return True
        return False

    def apply_time_decay_to_tp(self, original_tp_dist, elapsed_seconds):
        """
        [v50.1] Alvo com Decaimento Temporal (Time-Decaying TP).
        Reduz o alvo à medida que o tempo passa para mitigar exposição excessiva.
        """
        if elapsed_seconds < 60: return original_tp_dist
        
        minutes = elapsed_seconds / 60.0
        # Reduz 5% por minuto transcorrido
        decay_factor = max(0.2, 1.0 - (minutes * self.tp_decay_per_min))
        
        new_tp = original_tp_dist * decay_factor
        if decay_factor < 0.95:
             logging.debug(f"⏳ [DECAIMENTO TEMPORAL] Alvo reduzido: {original_tp_dist:.1f} -> {new_tp:.1f} (Decay: {decay_factor:.2%})")
        return float(new_tp)

    def check_scaling_out(self, symbol, ticket, current_profit_points, current_volume):
        """
        [v50 - MASTER] Saída Parcial (Scaling Out) / Take Profit Fracionado.
        Se atingiu o primeiro alvo e tem mais de 1 lote, encerra a parcial para garantir lucro.
        """
        if current_profit_points >= self.partial_profit_points and current_volume > self.partial_volume:
            logging.info(f"🎯 [PARCIAL MASTER] Gatilho atingido: {current_profit_points:.1f} pts. Reduzindo {self.partial_volume} lotes.")
            return True, self.partial_volume
        return False, 0.0

    def get_dynamic_trailing_params(self, current_atr, side="buy"):
        """
        [v50.1] Trailing Stop Dinâmico Assimétrico.
        - Compra: Segue a EMA 9 (Aprox 1 ATR).
        - Venda: Estrangulador Paranoico (Passo Curto baseado em ATR).
        """
        if not current_atr or current_atr <= 0:
            return self.trailing_trigger, self.trailing_lock, self.trailing_step
            
        if side == "sell":
            # [v50.1] Lógica de Venda: Estrangulamento Rápido
            trigger = current_atr * 0.7  # Ativa mais cedo (0.7 ATR)
            lock = current_atr * 0.3     # Trava 0.3 ATR
            step = current_atr * self.sell_trailing_step_atr # Passo curto (0.3 ATR)
            return float(trigger), float(lock), float(step)
            
        # Padrão Institucional para Compra: 1.5x ATR
        trigger = current_atr * 1.5
        lock = current_atr * 0.8
        step = current_atr * 0.4
        
        return float(trigger), float(lock), float(step)

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
        if psr < 0.80: # [RELAXADO] De 95% para 80% (Mais autonomia estatística)
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
        # [RELAXADO] Permitir operação em Ruído (Pois a IA já penaliza o score internamente)
        if regime == 2 and not getattr(self, 'force_noise_veto', False):
            logging.debug("⚠️ Regime de Ruído Detectado, permitindo operação cautelosa.")
            # Retornamos True para allowed, mas a IA terá score menor
            # A lógica continua para verificar outras condições
        elif regime == 2: # Se force_noise_veto for True, ainda bloqueia
            return {
                "allowed": False,
                "reason": "Regime de Mercado: RUÍDO/VOLÁTIL (2)"
            }

        # Regra 2: Circuit Breaker Dinâmico (Relativo)
        if avg_atr > 0 and current_atr > (5 * avg_atr): # [RELAXADO] De 3x para 5x
            return {
                "allowed": False,
                "reason": f"Circuit Breaker: ATR {current_atr:.1f} > 5x Média {avg_atr:.1f}"
            }
            
        # Regra 3: Panic Threshold Absoluto (Fallback se média estiver descalibrada)
        # WIN: ~150-300 pts é alto. 500 é extremo.
        # WDO: ~5-10 pts é alto. 20 é extremo.
        panic_threshold = 500.0 if ("WIN" in symbol or "IND" in symbol) else 20.0
        
        if current_atr > panic_threshold:
             return {
                "allowed": False,
                "reason": f"Volatilidade Extrema ({current_atr:.1f} > {panic_threshold})"
            }

        return {"allowed": True, "reason": "Condição de Mercado OK"}

    def check_macro_filter(self, side, macro_change_pct):
        """
        Filtro Macro (HFT Impact):
        Bloqueia COMPRA se S&P500 cair > 0.5% (Bearish Global).
        Bloqueia VENDA se S&P500 subir > 0.5% (Bullish Global).
        """
        # Se o usuário desativou manualmente o filtro Macro pela UI
        if hasattr(self, 'enable_macro_filter') and not self.enable_macro_filter:
            return True, "Macro Ignorado (Manual)"

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
            return False, f"Limite de perda diária atingido: {total_profit:.2f} <= -{self.max_daily_loss:.2f}"
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
            return False, f"Limite de trades diários atingido: {current_trade_count} / {self.daily_trade_limit}"
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
                        "vol_spike_mult": params.get("vol_spike_mult"),
                        "pyramid_profit_threshold": params.get("pyramid_profit_threshold"),
                        "pyramid_signal_threshold": params.get("pyramid_signal_threshold"),
                        "pyramid_max_volume": params.get("pyramid_max_volume")
                    }
                    self.dynamic_params[symbol] = mapped_params
                    logging.info(f"✅ RISCO: Parâmetros para {symbol} mapeados: {mapped_params}")
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
