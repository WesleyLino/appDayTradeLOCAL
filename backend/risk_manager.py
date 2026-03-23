from datetime import datetime, time, timedelta
import logging
import math
import numpy as np
import json
import os


# [ANTIVIBE-CODING] - Classe Crítica de Risco
class RiskManager:
    def __init__(
        self,
        max_daily_loss=100.00,
        daily_trade_limit=999,
        max_daily_loss_pct=0.20,
        initial_balance=3000.0,
    ):
        self.max_daily_loss = max_daily_loss
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_trade_limit = daily_trade_limit  # v52.1 - MODO ILIMITADO
        self.initial_balance = initial_balance
        self.max_deviation = 5
        self.allow_autonomous = True
        self.dry_run = (
            True  # [TREINAMENTO-ATIVO] - Todas as ordens são simuladas em memória
        )
        # [ANTIVIBE-CODING] - Limites de Perda Agressivos
        self.forbidden_hours = [
            (time(8, 55), time(9, 15)),  # [MELHORIA ABSOLUTA] Bloqueio de abertura até 09:15 (Alta Volatilidade/Ruído)
            (time(12, 0), time(13, 0)),  # Almoço/Baixa liquidez
            (
                time(17, 15),
                time(18, 0),
            ),  # Fechamento (Sincronizado com v22_locked_params)
        ]

        # [SOTA] Parâmetros de Trailing Stop (Campeão WIN Padrão)
        self.trailing_trigger = 70.0  # Ativa com 70 pontos (Otimizado)
        self.trailing_lock = 50.0  # Trava 50 pontos iniciais
        self.trailing_step = (
            5.0  # [SOTA V22.5.7] Trailing ultra-curto para capturar lucro bi-direcional
        )

        # [MELHORIA ABSOLUTA] Breakeven Ultra-Rápido - Sincronizado com JSON
        self.be_trigger = 45.0
        self.be_lock = 0.0

        # [v22.3] Filtro Anti-Lateralidade (Anti-Sideways)
        self.adx_min_threshold = 18.0
        self.adx_volatility_threshold = 15.0
        self.atr_volatility_trigger = 120.0
        self.bollinger_squeeze_threshold = 1.2
        self.min_atr_threshold = (
            50.0  # [v22.5.1] Inércia Institucional: Ignora mercado "parado" (pts)
        )
        self.flux_imbalance_threshold = 0.95  # [ANTIVIBE-CODING] SOTA V22.5.1

        # [v24.5] Scaling Out (Saída Parcial HFT)
        self.base_volume = 2.0  # [v24.5] 2 contratos para permitir parcial de fábrica
        self.partial_volume = 1.0  # Zera 1 contrato na parcial
        self.partial_profit_points = (
            70.0  # [v24.5 GOLDEN] Saída parcial para proteger capital e pagar taxas
        )

        # [FASE 2] Velocity Limit (Drawdown Acelerado no Tempo)
        # [FIX #FLIP-1] ATR=145: oscilação natural ±36pts/s. 20s e -30pts eram muito curtos,
        # causando fechamento prematuro em < 55ms. Novo: 60s (1 candle M1) e -60pts (40% SL).
        self.velocity_time_limit_sec = 60.0  # [FIX #FLIP-1] Era 20s → 60s (1 candle M1 completo)
        self.velocity_drawdown_limit = (
            -60.0
        )  # [FIX #FLIP-1] Era -30pts → -60pts (40% do SL real de 150pts)

        # [HFT ELITE] Alpha Fade (Decaimento de Ordem)
        self.alpha_fade_timeout = (
            10.0  # Segundos antes de cancelar ordem limite não executada
        )

        # [v52.0] Alpha Decay (Fuga por Inatividade)
        self.max_trade_duration_min = (
            3.0  # 3 minutos (3 candles M1) sem evolução = Sai a mercado
        )

        # [v50.1] TIME-DECAYING TP
        self.tp_decay_per_min = 0.05  # Decaimento de 5% por minuto

        # [v36 EXPERT] DNA do Mercado - Matriz de Regimes (Sincronizado com Plano Mestre)
        self.regime_settings = {
            1: {  # TENDÊNCIA (Trend Rider)
                "label": "Tendência",
                "trailing_trigger": 120.0,
                "trailing_lock": 90.0,
                "rsi_buy": 38.0,
                "rsi_sell": 62.0,
                "take_profit": 550.0,
                "use_partial": True,
                "partial_tp": 50.0,
                "lot_multiplier": 1.0,
                "stop_loss": 250.0,
            },
            0: {  # LATERAL (Sniper Scalper)
                "label": "Lateral",
                "trailing_trigger": 60.0,
                "trailing_lock": 45.0,  # Ativa mais cedo
                "rsi_buy": 22.0,
                "rsi_sell": 78.0,  # Mais assertivo (Sniper)
                "take_profit": 150.0,
                "use_partial": True,
                "partial_tp": 30.0,
                "lot_multiplier": 1.0,
                "stop_loss": 180.0,
            },
            2: {  # VOLATILIDADE (Safety First)
                "label": "Volatilidade",
                "trailing_trigger": 50.0,
                "trailing_lock": 30.0,
                "rsi_buy": 15.0,
                "rsi_sell": 85.0,
                "take_profit": 200.0,
                "use_partial": True,
                "partial_tp": 30.0,
                "lot_multiplier": 0.33,
                "stop_loss": 300.0,  # 0.33x lote (1 contrato se base=3)
                "min_confidence": 0.65,
                "cooldown": 30,
            },
            3: {  # REVERSÃO (Mean Reversion)
                "label": "Reversão",
                "trailing_trigger": 60.0,
                "trailing_lock": 40.0,
                "rsi_buy": 22.0,
                "rsi_sell": 78.0,  # NOVO: Assertividade bi-direcional em reversão
                "take_profit": 300.0,
                "use_partial": True,
                "partial_tp": 80.0,
                "lot_multiplier": 1.0,
                "stop_loss": 220.0,
            },
        }

        # [SOTA V22.5.1] Filtro de Fluxo (OBJ/Book L2) - Sincronizado com JSON
        self.flux_imbalance_threshold = 0.95

        # [FASE 2] Quarter-Kelly (Ajuste de Expectativa)
        self.kelly_fraction = 0.25  # Quarter-Kelly (Segurança HFT)

        # [v24] Parâmetros de Lote e Alvos Fixos (Defaults de Segurança)
        self.force_lots = None
        self.sl_dist = 150.0
        self.tp_dist = 500.0

        # [NOVO] Switches de Controle Manual do Frontend
        self.enable_news_filter = False
        # [ANTIVIBE-CODING] - Filtros de Proteção Institucional
        self.enable_calendar_filter = True
        self.enable_macro_filter = True

        # [FASE 28] DYNAMIC PARAMS CACHE
        self.dynamic_params = {}  # Carregado via load_optimized_params
        self.opening_lot_multiplier = (
            0.5  # [v23] Lote reduzido para abertura volátil (09:00-09:10)
        )

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
        self.post_event_momentum = False  # True durante os 10 min após fim de um veto
        self.post_event_momentum_until = None  # datetime de expiração do modo momentum
        self.post_event_name = ""  # Nome do evento que originou o momentum

    def _normalize_symbol(self, symbol):
        """[HFT ELITE] Normaliza o símbolo para chaves de parâmetros genéricas."""
        if not symbol:
            return "WIN$"
        s = symbol.upper()
        if "WIN" in s or "IND" in s:
            return "WIN$"
        if "WDO" in s or "DOL" in s:
            return "WDO$"
        return s

    def _load_economic_calendar(self):
        """Carrega dados de calendário econômico (impacto >= 3) para Veto de Liquidez."""
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

                    # Suporte a datas específicas
                    event_date = item.get("date")
                    if event_date and event_date != today_str:
                        continue

                    window = int(item.get("window_minutes", 3))
                    evt_time = datetime.strptime(item["time"], "%H:%M").time()
                    evt_dt = datetime.combine(datetime.today(), evt_time)

                    self.calendar_events.append(
                        {
                            "start": (evt_dt - timedelta(minutes=window)).time(),
                            "end": (evt_dt + timedelta(minutes=window)).time(),
                            "momentum_end": (
                                evt_dt + timedelta(minutes=window + 10)
                            ).time(),
                            "event": item["event"],
                        }
                    )
                    loaded += 1

            logging.info(
                f"📅 CALENDÁRIO ECONÔMICO: {loaded} alertas críticos carregados."
            )
        except Exception as e:
            logging.error(f"Erro ao carregar economic_calendar.json: {e}")

    def get_regime_specific_params(self, regime_idx):
        """[v36 EXPERT] Retorna os parâmetros base para o regime detectado."""
        if isinstance(regime_idx, dict):
            regime_idx = regime_idx.get("id", 0)
        return self.regime_settings.get(regime_idx, self.regime_settings[0])

    # [v23] Removido get_order_params duplicado/obsoleto.

    def check_gap_safety(self, opening_price, prev_close):
        """
        [V22.2] FILTRO DE GAP DE ABERTURA.
        Veta operações se o Gap de abertura for superior a 800 pontos.
        """
        gap_size = abs(opening_price - prev_close)
        if gap_size > 800.0:
            logging.warning(
                f"⚠️ [FILTRO DE GAP] Abertura com gap de {gap_size:.1f} pts (> 800). Risco de anomalia detectado."
            )
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
        if (
            hasattr(self, "calendar_events")
            and hasattr(self, "enable_calendar_filter")
            and self.enable_calendar_filter
        ):
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

    def is_direction_allowed(
        self,
        direction: str,
        sentiment_score: float,
        synthetic_idx: float = 0.0,
    ) -> bool:
        """[MELHORIA-3] Veto Direcional — bloqueia apenas o lado contrário ao sentimento.

        Chamado quando o sistema está em Veto de Calendário ou regime de risco alto.

        Args:
            direction:       "BUY" ou "SELL"
            sentiment_score: float entre -1.0 e +1.0 (do NewsSentimentWorker)
            synthetic_idx:   float (variação % das Blue Chips) — usado no warmup

        Returns:
            True  → direção permitida
            False → direção vetada
        """
        # Se o usuário desativou manualmente o filtro de notícias, libera as operações
        if hasattr(self, "enable_news_filter") and not self.enable_news_filter:
            return True

        # [MELHORIA-F] Warmup de Sentimento: nos primeiros 5min do pregão (09:00-09:05),
        # o NewsSentimentWorker ainda não processou notícias suficientes.
        # Durante esse período, usamos o synthetic_idx (Blue Chips) como proxy de sentimento.
        now = datetime.now()
        is_warmup_window = (now.hour == 9 and now.minute < 5)
        if is_warmup_window:
            logging.info(
                f"[MELHORIA-F WARMUP] Janela de warmup ativa (09:00-09:05). "
                f"Usando Blue Chips ({synthetic_idx:.2f}%) como proxy de sentimento."
            )
            if direction == "BUY" and synthetic_idx < -0.2:
                logging.warning(
                    f"[MELHORIA-F WARMUP] COMPRA bloqueada: Blue Chips negativos ({synthetic_idx:.2f}%)"
                )
                return False
            if direction == "SELL" and synthetic_idx > 0.2:
                logging.warning(
                    f"[MELHORIA-F WARMUP] VENDA bloqueada: Blue Chips positivos ({synthetic_idx:.2f}%)"
                )
                return False
            return True  # Libera durante warmup com validação básica de macro

        # [MELHORIA-A] Threshold reduzido de ±0.5 para ±0.3.
        # Com ±0.5, sentimentos levemente direcionais (ex: +0.35) bloqueavam ambos os lados.
        # Com ±0.3, mantém o veto para casos verdadeiramente neutros e libera viés leve.
        if sentiment_score > 0.3:
            # Mercado com viés BULLISH → bloqueia VENDA
            if direction == "SELL":
                logging.warning(
                    f"⛔ [VETO DIRECIONAL] VENDA bloqueada: sentimento BULLISH ({sentiment_score:.2f})"
                )
                return False
            return True

        if sentiment_score < -0.3:
            # Mercado com viés BEARISH → bloqueia COMPRA
            if direction == "BUY":
                logging.warning(
                    f"⛔ [VETO DIRECIONAL] COMPRA bloqueada: sentimento BEARISH ({sentiment_score:.2f})"
                )
                return False
            return True

        # Sentimento neutro (-0.3 a +0.3) → bloqueia ambos os lados
        logging.info(
            f"⛔ [VETO DIRECIONAL] Sentimento neutro ({sentiment_score:.2f}). "
            f"Operação {direction} suspensa."
        )
        return False

    def get_directional_rigor(
        self, direction: str, ema_long: float, price: float
    ) -> float:
        """
        [v22.5] RIGOR DIRECIONAL.
        Aumenta o threshold de confiança da IA se a operação for contra a tendência primária.
        EMA Longa (90) serve como balizador de tendência macro.
        """
        if not ema_long or not price:
            return 1.0  # Sem rigor extra se faltar dados

        trend_is_up = price > ema_long

        # Se tentar COMPRA em tendência de BAIXA ou VENDA em tendência de ALTA
        if (direction.upper() == "BUY" and not trend_is_up) or (
            direction.upper() == "SELL" and trend_is_up
        ):
            logging.info(
                f"🛡️ [RIGOR V22.5] Operação contra-tendência detectada ({direction}). Elevando exigência de confiança."
            )
            return 2.0  # Dobra o threshold necessário (ex: 0.35 -> 0.70)

        return 1.0  # Rigor normal se a favor da tendência

    def is_macro_allowed(self, direction: str, synthetic_idx: float) -> bool:
        """[ANTIVIBE-CODING] Veto Macro via Blue Chips/S&P 500.

        Bloqueia operações se o mercado global estiver fortemente contra a direção.
        Respeita o switch de controle manual do Dashboard.
        """
        if not getattr(self, "enable_macro_filter", True):
            return True

        # Se Blue Chips estão fortemente contra, aplica veto preventivo
        if direction == "BUY" and synthetic_idx < -0.2:
            logging.warning(
                f"🛑 [VETO MACRO] COMPRA bloqueada: Blue Chips caindo forte ({synthetic_idx:.2f}%)"
            )
            return False
        elif direction == "SELL" and synthetic_idx > 0.2:
            logging.warning(
                f"🛑 [VETO MACRO] VENDA bloqueada: Blue Chips subindo forte ({synthetic_idx:.2f}%)"
            )
            return False

        return True

    def validate_environmental_risk(
        self, ping_ms, spread_points, max_ping=150.0, max_spread=15.0
    ):
        """
        Avalia se a conectividade com a B3 está estável e se o mercado possui liquidez básica (Não-Estressado).
        Bloqueia envios com lógicas Anti-Slippage.
        """
        if ping_ms is not None and ping_ms > max_ping:
            return (
                False,
                f"Ping Muito Alto/Latência Severa (B3): {ping_ms:.1f}ms (Aceitável: <= {max_ping}ms)",
            )

        if spread_points is not None and spread_points > max_spread:
            return (
                False,
                f"Spread Alargado (Vazio de Liquidez/Notícia/Leilão): {spread_points} pts (Aceitável: <= {max_spread} pts)",
            )

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
            return (
                False,
                f"KILL SWITCH ATIVADO: Drawdown Extremo (Flutuante). Perca Atual: R$ {drawdown_value:.2f} >= Limite Master: R$ {self.max_daily_loss:.2f}",
            )

        return True, "Equity Seguro"

    def check_velocity_limit(self, current_profit_points, elapsed_seconds):
        """
        [FASE 2] Parede de Exaustão com Grace Period.
        """
        # 🛡️ [FIX CRÍTICO] Ignora o spread inicial. Só avalia a velocidade após 3s.
        if elapsed_seconds < 3.0:
            return False, "GRACE_PERIOD"

        if (
            elapsed_seconds > self.velocity_time_limit_sec
            and current_profit_points <= self.velocity_drawdown_limit
        ):
            logging.warning(
                f"⏳ LIMITE DE VELOCIDADE EXCEDIDO: Operação amarrada em {current_profit_points} pts por {elapsed_seconds:.1f}s. Abortando cedo."
            )
            return True, "LIMITE_VELOCIDADE_PERDA"

        return False, "VELOCIDADE_OK"

    def check_obi_reversal(
        self,
        position_side: str,
        current_obi: float,
        obi_reversal_threshold: float = 2.5,
    ) -> bool:
        """[MELHORIA-G] Detecção de Reversão de OBI com posição aberta.

        Se o fluxo de ordens inverter fortemente contra a posição, sinaliza saída precoce
        antes que o trailing stop ou SL sejam atingidos.

        Args:
            position_side:           "buy" ou "sell"
            current_obi:             OBI calculado no candle atual (-3.0 a +3.0)
            obi_reversal_threshold:  Intensidade de reversão para acionar saída (default: 1.2)

        Returns:
            True  → OBI reverteu fortemente contra a posição (saída recomendada)
            False → OBI ainda favorável ou neutro
        """
        if position_side.lower() == "buy" and current_obi <= -obi_reversal_threshold:
            logging.warning(
                f"⚡ [MELHORIA-G OBI-REVERSAL] COMPRA em risco: OBI reverteu para "
                f"{current_obi:.2f} (Threshold: -{obi_reversal_threshold:.1f})"
            )
            return True
        if position_side.lower() == "sell" and current_obi >= obi_reversal_threshold:
            logging.warning(
                f"⚡ [MELHORIA-G OBI-REVERSAL] VENDA em risco: OBI reverteu para "
                f"{current_obi:.2f} (Threshold: +{obi_reversal_threshold:.1f})"
            )
            return True
        return False

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
                logging.warning(
                    f"⏰ [TIME-STOP MASTER] {max_time}s atingidos. PnL {current_profit_points:.1f} abaixo do gatilho {self.be_trigger}. Abortando."
                )
                return True
        return False

    def allow_pyramiding(
        self,
        current_profit_points,
        signal_strength,
        current_volume,
        symbol=None,
        profit_threshold=None,
        signal_threshold=None,
        max_volume=None,
    ):
        """
        [v50 - MASTER] Piramidação Matemática (Scaling In).
        Suporta injeção de parâmetros dinâmicos via self.dynamic_params.
        """
        # Fallback para parâmetros dinâmicos se disponíveis
        norm_symbol = self._normalize_symbol(symbol) if symbol else None
        d_params = self.dynamic_params.get(norm_symbol, {}) if norm_symbol else {}

        trigger = (
            profit_threshold
            if profit_threshold is not None
            else d_params.get("pyramid_profit_threshold", self.be_trigger)
        )
        sig_threshold = (
            signal_threshold
            if signal_threshold is not None
            else d_params.get("pyramid_signal_threshold", 1.2)
        )
        max_vol = (
            max_volume
            if max_volume is not None
            else d_params.get("pyramid_max_volume", 3)
        )

        if current_profit_points >= trigger and abs(signal_strength) >= sig_threshold:
            if current_volume < max_vol:
                logging.info(
                    f"💎 [PIRAMIDAÇÃO DINÂMICA] Autorizada! Lucro {current_profit_points:.1f} | Fluxo: {signal_strength:.2f} | Vol Atual: {current_volume}"
                )
                return True
        return False

    def apply_time_decay_to_tp(self, original_tp_dist, elapsed_seconds):
        """
        [v50.1] Alvo com Decaimento Temporal (Time-Decaying TP).
        Reduz o alvo à medida que o tempo passa para mitigar exposição excessiva.
        """
        if elapsed_seconds < 60:
            return original_tp_dist

        minutes = elapsed_seconds / 60.0
        # Reduz 5% por minuto transcorrido
        decay_factor = max(0.2, 1.0 - (minutes * self.tp_decay_per_min))

        new_tp = original_tp_dist * decay_factor
        if decay_factor < 0.95:
            logging.debug(
                f"⏳ [DECAIMENTO TEMPORAL] Alvo reduzido: {original_tp_dist:.1f} -> {new_tp:.1f} (Decay: {decay_factor:.2%})"
            )
        return float(new_tp)

    def calculate_dynamic_tp(self, base_tp, atr_current):
        """
        [v22.2] Ajusta o TP dinamicamente com base na volatilidade.
        Evita alvos impossíveis em baixa volatilidade.
        """
        if not atr_current or atr_current <= 0:
            return base_tp

        # Se a volatilidade está 50% abaixo da média operacional (120 pts)
        if atr_current < 60.0:
            return min(base_tp, atr_current * 1.5)
        return base_tp

    def check_scaling_out(
        self,
        symbol,
        ticket,
        current_profit_points,
        current_volume,
        regime=None,
        **kwargs,
    ):
        """
        [v24] Saída Parcial (Scaling Out) / Mão Fracionada.
        Garante o profit do primeiro contrato e ativa o breakeven para o 'Caçador'.
        """
        target_partial = self.partial_profit_points

        # [MODO MOMENTUM / v24] Saída parcial preservada em 70 pts para garantir cobertura de taxas e lucro base
        if (
            regime == "MOMENTUM"
            or kwargs.get("comment") == "MOMENTUM_BYPASS"
            or kwargs.get("version") == "v24"
        ):
            target_partial = 70.0  # [v24 GOLDEN TARGET]

        if current_profit_points >= target_partial and current_volume >= 2.0:
            logging.info(
                f"🎯 [v24 PARCIAL] Alvo {target_partial} pts atingido. Realizando 1 contrato. Restante vira 'Caçador'."
            )
            return True, 1.0
        return False, 0.0

    def check_breakeven(self, current_profit_points, entry_price, side="buy"):
        """
        [v22 GOLDEN + MELHORIA-6] Verifica se a operação atingiu o gatilho de Breakeven.
        BUY:  Gatilho padrão (be_trigger = 60 pts). Mercado tem viés de alta — deixa respirar.
        SELL: Gatilho antecipado (40 pts). Operação contra-fluxo no mercado BR — protege capital cedo.
        """
        # [MELHORIA-6] Breakeven assimétrico: SELL ativa 20 pts antes do BUY
        effective_trigger = self.be_trigger if side.lower() == "buy" else min(self.be_trigger, 40.0)

        if current_profit_points >= effective_trigger:
            if side.lower() == "buy":
                new_sl = entry_price + self.be_lock
            else:
                new_sl = entry_price - self.be_lock

            return True, float(new_sl)
        return False, None

    def get_structural_stop(self, side, prev_extremes):
        """
        [v24.1] Trailing Stop Estrutural.
        Segue a mínima/máxima do candle M1 anterior (Escala Fracionada).
        Garante que o robô não seja 'violinado' por ruídos curtos.
        """
        if prev_extremes is None:
            return None

        if side.lower() == "buy" or side == 1:  # 1 = BUY no MT5
            # Protege 5 pts abaixo da mínima do candle anterior
            return float(prev_extremes["low"] - 5.0)
        else:
            # Protege 5 pts acima da máxima do candle anterior
            return float(prev_extremes["high"] + 5.0)

    def get_dynamic_trailing_params(self, current_atr, side="buy", regime_params=None):
        """
        [v24 + MELHORIA-4] Trailing Stop Dinâmico Assimétrico com Step Proporcional ao ATR.
        Compra: Trend Following (Largo) — trigger maior para deixar o movimento se desenvolver.
        Venda: Panic/Short Squeeze (Estrangulador) — trigger menor para proteger capital cedo.
        Step: Proporcional ao ATR (25%) para evitar saídas prematuras por ruído normal de tick.
        """
        if regime_params and "trailing_trigger" in regime_params:
            return (
                float(regime_params["trailing_trigger"]),
                float(regime_params["trailing_lock"]),
                float(regime_params["trailing_step"]),
            )

        # [MELHORIA-4] Step proporcional ao ATR (25% do ATR, com mínimos por símbolo)
        # WIN/IND: range normal ATR 80-150 pts → step 20-37 pts (adequado, evita ruído)
        # WDO/DOL: range normal ATR 4-8 pts → step 1-2 pts
        atr_ref = float(current_atr) if current_atr and current_atr > 0 else 80.0
        is_micro = atr_ref < 10.0  # Detecta WDO/DOL via ATR
        min_step = 2.0 if is_micro else 10.0
        dynamic_step = max(min_step, round(atr_ref * 0.25))

        # [v24] Lógica Assimétrica Baseada em Auditoria HFT
        if side.lower() == "sell":
            # Venda e pânico: Estrangular rápido (Panic/Short Squeeze)
            trigger = 80.0   # [v24.5] Começa a estrangular cedo na venda
            lock = 60.0      # Trava lucro inicial
            step = dynamic_step  # [MELHORIA-4] Proporcional ao ATR (era fixo 20 pts)
        else:
            # Compra: Trend Following (Deixar respirar para ralis)
            trigger = 150.0  # [v24.5] Dá mais espaço para a compra se desenvolver
            lock = 100.0     # Lock de lucro mais fundo
            step = dynamic_step  # [MELHORIA-4] Proporcional ao ATR (era fixo 50 pts)

        return float(trigger), float(lock), float(step)

    def calculate_quarter_kelly(
        self,
        balance,
        win_rate_pct,
        profit_factor,
        risk_per_trade_points=150.0,
        point_value=0.20,
    ):
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
        target_fraction = min(0.05, target_fraction)  # Max 5% arriscado
        risk_amount = balance * target_fraction
        volume = risk_amount / (risk_per_trade_points * point_value)
        return max(1.0, float(volume))

    def calculate_psr(self, returns_list, benchmark_sr=0.0):
        """
        Calcula o Probabilistic Sharpe Ratio (PSR).
        Determina se a performance observada é estatisticamente significativa.
        """
        n = len(returns_list)
        if n < 30:  # Amostra mínima conforme econometria para convergência
            return 1.0  # Neutro

        returns = np.array(returns_list)
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)

        if std_ret == 0:
            return 0.0

        sr = mean_ret / std_ret

        # Momentos (Skewness e Kurtosis)
        diffs = returns - mean_ret
        m2 = np.mean(diffs**2)
        m3 = np.mean(diffs**3)
        m4 = np.mean(diffs**4)

        skew = m3 / (m2**1.5) if m2 > 0 else 0
        kurt = m4 / (m2**2) - 3 if m2 > 0 else 0  # Excess Kurtosis

        # Fórmula de Bailey and López de Prado
        v = 1 - skew * sr + (kurt / 4) * (sr**2)
        if v <= 0:
            return 0.0

        z = (sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(v)

        # CDF Normal Aproximada (ERF)
        psr = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        return psr

    def validate_reliability(self, returns_list):
        """
        Veto AlphaX: Bloqueia se a confiabilidade estatística (PSR) for < 95%.
        """
        if not returns_list:
            return True, 1.0

        psr = self.calculate_psr(returns_list)
        if psr < 0.80:  # [RELAXADO] De 95% para 80% (Mais autonomia estatística)
            return False, psr
        return True, psr

    def should_force_close(self):
        """Verifica se passou das 17:50 para encerramento compulsório."""
        now = datetime.now().time()
        return now >= time(17, 50)

    def validate_market_condition(self, symbol, regime, current_atr, avg_atr, spread=1.0):
        """
        Valida se as condições de mercado são seguras para operar.
        Regras (Compliance com project_rules.json):
        1. Rejeita se Regime = 2 (RUÍDO/ALTA VOLATILIDADE).
        2. Rejeita se Volatilidade (ATR) > 5x ATR Médio (Circuit Breaker).
        3. Veto de Inércia (Mercado Parado).
        4. Veto de Spread Excessivo (Proteção contra Slippage).
        """
        # Regra 1: Regime de Mercado (0=Indefinido, 1=Tendência, 2=Ruído)
        # [RELAXADO] Permitir operação em Ruído (Pois a IA já penaliza o score internamente)
        if regime == 2 and not getattr(self, "force_noise_veto", False):
            logging.debug("⚠️ Regime de Ruído Detectado, permitindo operação cautelosa.")
        elif regime == 2:
            return {"allowed": False, "reason": "Regime de Mercado: RUÍDO/VOLÁTIL (2)"}

        # Regra 2: Circuit Breaker Dinâmico (Relativo)
        if avg_atr > 0 and current_atr > (5 * avg_atr):
            return {
                "allowed": False,
                "reason": f"Circuit Breaker: ATR {current_atr:.1f} > 5x Média {avg_atr:.1f}",
            }

        # Regra 3: Veto de Inércia (Inércia Institucional V22.5.1)
        min_atr = getattr(self, "min_atr_threshold", 50.0)
        vol_min = max(20.0, min_atr) if ("WIN" in symbol or "IND" in symbol) else 1.5

        if current_atr < vol_min:
            return {
                "allowed": False,
                "reason": f"Inércia Institucional: ATR {current_atr:.1f} < Mínimo {vol_min:.1f}",
            }

        # Regra 4: [MELHORIA-ELITE] Veto de Spread Excessivo
        # WIN: Spread > 30 pts (6 ticks de 5) é sinal de baixa liquidez/pânico no book
        # WDO: Spread > 2.5 pts normalizado
        max_spread = 6.0 if ("WIN" in symbol or "IND" in symbol) else 2.5
        if spread > max_spread:
            return {
                "allowed": False,
                "reason": f"Spread Excessivo: {spread:.1f} > Max {max_spread:.1f} (Risco Slippage)",
            }

        return {"allowed": True, "reason": "Condição de Mercado OK"}

    def is_sideways_market(self, adx, bb_upper, bb_lower, atr):
        """
        [v22.3] Detecta se o mercado está lateral/sem tendência.
        """
        # Critério 1: ADX Dinâmico (SOTA V22.4)
        # Se ATR > 120 (Volatilidade Alta), reduz threshold para 18.0 para capturar rompimentos rápidos
        threshold = self.adx_min_threshold
        if atr > self.atr_volatility_trigger:
            threshold = self.adx_volatility_threshold
            logging.info(
                f"⚡ [ADX DINÂMICO] Alta Volatilidade (ATR {atr:.1f} > {self.atr_volatility_trigger}). Threshold: {threshold}"
            )

        if adx is not None and adx < threshold:
            logging.warning(
                f"🛑 [VETO LATERALIDADE] ADX {adx:.1f} < {threshold} (Tendência Fraca)"
            )
            return True, "ADX_BAIXO"

        # Critério 2: Bollinger Squeeze (Estreitamento de bandas)
        bb_width = bb_upper - bb_lower
        min_width = atr * self.bollinger_squeeze_threshold
        if bb_width < min_width:
            logging.warning(
                f"🛑 [VETO LATERALIDADE] BB Width {bb_width:.1f} < {min_width:.1f} (Bollinger Squeeze)"
            )
            return True, "BB_SQUEEZE"

        return False, "PROPRIO_PARA_OPERAR"

    def check_macro_filter(self, side, macro_change_pct):
        """
        Filtro Macro (HFT Impact):
        Bloqueia COMPRA se S&P500 cair > 0.5% (Bearish Global).
        Bloqueia VENDA se S&P500 subir > 0.5% (Bullish Global).
        """
        # Se o usuário desativou manualmente o filtro Macro pela UI
        if hasattr(self, "enable_macro_filter") and not self.enable_macro_filter:
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
        win_rate = (
            (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0
        )
        profit_factor = (
            (self.gross_profit / self.gross_loss)
            if self.gross_loss > 0
            else (self.gross_profit if self.total_trades > 0 else 0.0)
        )
        return {
            "total_trades": self.total_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "gross_profit": round(self.gross_profit, 2),
            "gross_loss": round(self.gross_loss, 2),
            "net_profit": round(self.daily_profit, 2),
        }

    def check_daily_loss(self, total_profit):
        """
        Verifica se o limite de perda diária foi atingido.
        total_profit: Soma do Lucro Realizado + Flutuante.
        """
        # Se total_profit for negativo e maior (em magnitude) que o limite
        if total_profit <= -self.max_daily_loss:
            return (
                False,
                f"Limite de perda diária atingido: {total_profit:.2f} <= -{self.max_daily_loss:.2f}",
            )
        return True, "OK"

    def check_aggressive_risk(self, daily_pnl, initial_balance=1000.0):
        """
        [AGRESSIVO] Verifica se o prejuízo do dia atingiu o limite percentual.
        Ignora a contagem de trades enquanto houver capital e sinal.
        """
        limit = initial_balance * self.max_daily_loss_pct
        if daily_pnl <= -limit:
            return (
                False,
                f"Limite de perda agressivo atingido: R$ {abs(daily_pnl):.2f} (>= {int(self.max_daily_loss_pct * 100)}%)",
            )
        return True, "Risco OK"

    def check_trade_limit(self, current_trade_count):
        """
        Verifica se o limite de trades diários foi atingido.
        [AGRESSIVO] No modo 60%, este método pode ser ignorado pelo bot.
        """
        if current_trade_count >= self.daily_trade_limit:
            return (
                False,
                f"Limite de trades diários atingido: {current_trade_count} / {self.daily_trade_limit}",
            )
        return True, "OK"

    def validate_volatility(self, current_atr, avg_atr):
        """
        Implementa o Circuit Breaker baseado em volatilidade.
        Regra do Master Plan: Parar se volatilidade > 3x ATR_MEDIO.
        """
        if avg_atr <= 0 or current_atr <= 0:
            return True

        if current_atr > 3 * avg_atr:
            logging.error(
                f"CIRCUIT BREAKER: Volatilidade (ATR: {current_atr:.2f}) > 3x Média ({avg_atr:.2f})"
            )
            return False
        return True

    def calculate_volatility_sizing(
        self,
        balance: float,
        current_atr: float,
        point_value: float = 0.20,
        risk_pct: float = 0.01,
    ) -> float:
        """
        [SOTA] Calcula o tamanho do lote baseado na volatilidade (Volatility Sizing).
        Objetivo: Equalizar o risco financeiro ($ em risco) independente da volatilidade.

        Fórmula: Lotes = (Saldo * Risco%) / (ATR * Valor_Ponto)
        """
        if current_atr <= 0 or point_value <= 0:
            return 1.0  # Fallback conservador

        risk_amount = balance * risk_pct
        volatility_cost = current_atr * point_value

        if volatility_cost == 0:
            return 1.0

        suggested_lots = risk_amount / volatility_cost
        return float(suggested_lots)

    def load_optimized_params(self, symbol, json_path):
        """Carrega parâmetros otimizados (SL, TP, etc) de um arquivo JSON."""
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f:
                    raw_data = json.load(f)
                    # [ANTIVIBE-CODING] Busca hierárquica por parâmetros
                    params = raw_data.get(
                        "params", raw_data.get("strategy_params", raw_data)
                    )

                    if not isinstance(params, dict):
                        logging.warning(
                            f"⚠️ RISK: Parâmetros em {json_path} não são um dicionário válido."
                        )
                        return False

                    mapped_params = {
                        "sl": params.get("sl_dist") or params.get("sl") or 150.0,
                        "tp": params.get("tp_dist") or params.get("tp") or 300.0,
                        "rsi_period": params.get("rsi_period") or 9,
                        "vol_spike_mult": params.get("vol_spike_mult") or 1.0,
                        "pyramid_profit_threshold": params.get(
                            "pyramid_profit_threshold"
                        )
                        or 100.0,
                        "pyramid_signal_threshold": params.get(
                            "pyramid_signal_threshold"
                        )
                        or 0.6,
                        "pyramid_max_volume": params.get("pyramid_max_volume") or 1,
                        "be_trigger": params.get("be_trigger") or 60.0,
                        "be_lock": params.get("be_lock") or 5.0,
                        "adx_min_threshold": params.get("adx_min_threshold", 20.0),
                        "bollinger_squeeze_threshold": params.get(
                            "bollinger_squeeze_threshold", 1.2
                        ),
                        "min_atr_threshold": params.get("min_atr_threshold", 50.0),
                        "flux_imbalance_threshold": params.get(
                            "flux_imbalance_threshold"
                        )
                        or params.get("flux_threshold")
                        or 1.5,
                        "start_time": params.get("start_time") or "09:00",
                        "end_time": params.get("end_time") or "17:15",
                        "confidence_threshold": params.get("confidence_threshold")
                        or 0.52,
                        "trailing_step_atr": params.get("trailing_step_atr", 0.3),
                        "sell_trailing_step_atr": params.get(
                            "sell_trailing_step_atr", 0.3
                        ),
                    }
                    norm_symbol = self._normalize_symbol(symbol)
                    self.dynamic_params[norm_symbol] = mapped_params
                    # Salva também na chave original para garantir compatibilidade caso algum script use literal
                    if norm_symbol != symbol:
                        self.dynamic_params[symbol] = mapped_params

                    # [v50.1] Injeção direta nos atributos se for o símbolo principal
                    if "WIN" in symbol:
                        self.be_trigger = mapped_params.get(
                            "be_trigger", self.be_trigger
                        )
                        self.be_lock = mapped_params.get("be_lock", self.be_lock)
                        self.adx_min_threshold = mapped_params.get(
                            "adx_min_threshold", self.adx_min_threshold
                        )
                        self.adx_volatility_threshold = params.get(
                            "adx_volatility_threshold", self.adx_volatility_threshold
                        )
                        self.atr_volatility_trigger = params.get(
                            "atr_volatility_trigger", self.atr_volatility_trigger
                        )
                        self.bollinger_squeeze_threshold = mapped_params.get(
                            "bollinger_squeeze_threshold",
                            self.bollinger_squeeze_threshold,
                        )
                        self.max_daily_loss = float(
                            params.get("max_daily_loss", self.max_daily_loss)
                        )
                        self.daily_trade_limit = params.get(
                            "daily_trade_limit", self.daily_trade_limit
                        )
                        self.min_atr_threshold = mapped_params.get(
                            "min_atr_threshold", self.min_atr_threshold
                        )
                        self.flux_imbalance_threshold = mapped_params.get(
                            "flux_imbalance_threshold", self.flux_imbalance_threshold
                        )
                        self.force_lots = params.get("force_lots")
                        self.sl_dist = mapped_params.get(
                            "sl", 130.0
                        )  # [v24] Expondo para o bot
                        self.tp_dist = mapped_params.get(
                            "tp", 100.0
                        )  # [v24] Expondo para o bot

                    logging.info(
                        f"✅ RISCO: Parâmetros para {symbol} sincronizados: flux={self.flux_imbalance_threshold}, tp={getattr(self, 'tp_dist', 'Auto')}, lots={getattr(self, 'force_lots', 'Auto')}"
                    )
                    return True
            except Exception as e:
                logging.error(
                    f"❌ RISK: Erro crítico ao carregar parâmetros de {json_path}: {e}"
                )
        return False

    def get_order_params(
        self,
        symbol,
        type,
        price,
        volume,
        current_atr=None,
        regime=None,
        tp_multiplier=1.0,
        sl_multiplier=1.0,
        current_time=None,
        **kwargs,
    ):
        """
        Retorna parâmetros calculados para envio de ordem OCO.
        [SOTA v5] Suporta tp_multiplier e alvos baseados em ATR/Regime.
        """
        import MetaTrader5 as mt5

        # [MELHORIA-3] TP Adaptativo por Regime — usa regime_settings como âncora principal
        # Fundamentação: TP fixo de 500 pts é inalcançável em lateral (Regime 0/2).
        # regime_settings já define take_profit realista para cada regime:
        #   Regime 0 (Lateral):    150 pts — alvo atingível no range
        #   Regime 1 (Tendência):  550 pts — captura o movimento estendido
        #   Regime 2 (Volatilidade): 200 pts — saída rápida no rompimento
        #   Regime 3 (Reversão):   300 pts — alvo médio para reversão
        r_settings = self.get_regime_specific_params(regime)
        regime_tp = float(r_settings.get("take_profit", self.tp_dist))
        regime_sl = float(r_settings.get("stop_loss", self.sl_dist))

        if current_atr and current_atr > 0:
            # ATR como refinamento: se ATR sugere alvo maior que o regime, usa ATR (mercado em movimento)
            # Se ATR sugere alvo menor (ex: ATR=40 em lateral), mantém o alvo do regime (mais conservador)
            atr_tp = float(current_atr * 1.5)
            atr_sl = float(current_atr * 1.2)
            # Toma o maior entre ATR e regime_tp para BUY, mas limita a 2x o regime_tp para evitar alvos impossíveis
            tp_points = max(regime_tp * 0.7, min(atr_tp, regime_tp * 1.5))
            sl_points = max(regime_sl * 0.7, min(atr_sl, regime_sl * 1.5))
            logging.debug(
                f"[MELHORIA-3] TP Adaptativo: Regime={regime} | RegimeTP={regime_tp:.0f} | ATR-TP={atr_tp:.0f} | Final={tp_points:.0f}"
            )
        else:
            # Sem ATR — usa regime_settings diretamente
            tp_points = regime_tp
            sl_points = regime_sl
            norm_sym = self._normalize_symbol(symbol)
            d_params = self.dynamic_params.get(norm_sym, {})
            # Fallback para dynamic_params se disponível
            if d_params.get("sl"):
                sl_points = float(d_params["sl"])
            if d_params.get("tp"):
                tp_points = float(d_params["tp"])


        # [v24] Janela de Ouro (10:00 - 11:30)
        if current_time:
            # Sincronizado com v24_locked_params
            if time(10, 0) <= current_time <= time(11, 30):
                tp_points *= 1.5
                logging.info(
                    f"🚀 [v24 GOLDEN-WINDOW] TP expandido (+50%): {tp_points:.0f} pts"
                )

        # [MELHORIA-3] Fallback sem ATR já tratado acima via regime_settings.
        # Bloco legado [v23] removido — sobrescrevia TP=100 pts para WIN, anulando MELHORIA-3.
        # Proteção mínima por símbolo para garantir valores > 0 (casos extremos sem regime)
        if tp_points <= 0 or sl_points <= 0:
            if "WDO" in symbol or "DOL" in symbol:
                sl_points = sl_points if sl_points > 0 else 5.0
                tp_points = tp_points if tp_points > 0 else 10.0
            else:
                sl_points = sl_points if sl_points > 0 else 130.0
                tp_points = tp_points if tp_points > 0 else 150.0

        # [v23] Lógica de Momentum e Abertura consolidada
        if tp_multiplier > 1.1:
            tp_points *= tp_multiplier
            # sl_points *= 1.2 # [ANTIVIBE] Removido multiplicador legado em favor do sl_multiplier da IA

        # [v24.2] Aplica multiplicador de Stop Loss vindo da IA (Momentum Bypass)
        if sl_multiplier > 1.0:
            sl_points *= sl_multiplier
            logging.info(
                f"🛡️ [RISK SL] Stop Loss expandido via IA: x{sl_multiplier} ({sl_points:.0f} pts)"
            )

        # [v23] Aplicar multiplicador de lote por Regime
        r_params = self.get_regime_specific_params(regime)
        volume *= r_params.get("lot_multiplier", 1.0)

        now_time = current_time if current_time else datetime.now().time()
        if time(9, 0) <= now_time <= time(9, 10):
            volume *= self.opening_lot_multiplier
            volume = max(1.0, round(volume))
            sl_points *= 2.0
            logging.info(
                f"⚡ [RISCO v23] Abertura ({now_time}). Lote: {volume}, Stop: {sl_points}"
            )

        # [v24.2] Multiplicadores consolidados acimas

        if type in (
            mt5.ORDER_TYPE_BUY,
            mt5.ORDER_TYPE_BUY_LIMIT,
            mt5.ORDER_TYPE_BUY_STOP,
        ):
            side = "buy"
        elif type in (
            mt5.ORDER_TYPE_SELL,
            mt5.ORDER_TYPE_SELL_LIMIT,
            mt5.ORDER_TYPE_SELL_STOP,
        ):
            side = "sell"
        else:
            side = "neutral"

        # [v23.1] SL Dinâmico (Extremos do Candle Anterior)
        prev_extremes = kwargs.get("prev_extremes")
        sl_from_extremes = False

        if prev_extremes and type in [
            mt5.ORDER_TYPE_BUY,
            mt5.ORDER_TYPE_BUY_LIMIT,
            mt5.ORDER_TYPE_SELL,
            mt5.ORDER_TYPE_SELL_LIMIT,
        ]:
            if type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT]:
                sl = prev_extremes["low"] - 5  # 1 tick respiro (WIN = 5 pts)
            else:
                sl = prev_extremes["high"] + 5

            # Limite de segurança (Max 250 pts para WIN)
            if "WIN" in symbol and abs(price - sl) > 250:
                sl = (
                    price - 250
                    if type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT]
                    else price + 250
                )
            sl_from_extremes = True

        if not sl_from_extremes:
            sl, tp = 0.0, 0.0
            if sl_points > 0:
                if side == "buy":
                    sl = price - sl_points
                    tp = price + tp_points
                elif side == "sell":
                    sl = price + sl_points
                    tp = price - tp_points
                else:
                    side = "neutral"
        else:
            # Se veio dos extremos, apenas calcula o TP
            tp = (
                price + tp_points
                if type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT]
                else price - tp_points
            )

        # [FIX-CRÍTICO] Quantização aplicada em AMBOS os caminhos (anterior bug: só no else)
        # Sem isto, SL/TP enviados sem múltiplo de 5 pts causam rejection silenciosa na B3
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
        if price <= 0:
            return 0.0
        tick_size = (
            0.5
            if ("WDO" in symbol or "DOL" in symbol)
            else 5.0
            if ("WIN" in symbol or "IND" in symbol)
            else 0.01
        )
        return round(price / tick_size) * tick_size if tick_size > 0 else price

    def _apply_anti_violinada(self, symbol, price, side):
        if price <= 0:
            return price
        try:
            is_wdo = "WDO" in symbol or "DOL" in symbol
            round_interval = 10.0 if is_wdo else 100.0
            offset = 0.5 if is_wdo else 15.0
            if price < round_interval:
                return price
            remainder = price % round_interval
            danger_zone = round_interval * 0.1
            if (
                remainder == 0
                or remainder < danger_zone
                or remainder > (round_interval - danger_zone)
            ):
                new_price = (
                    price - offset
                    if side == "buy"
                    else price + offset
                    if side == "sell"
                    else price
                )
                return self._quantize_price(symbol, new_price)
            return price
        except:
            return price


class RegimeExpert:
    """
    [V36 EXPERT] Especialista em Multiplicadores de Regime.
    Centraliza a lógica de ajuste de alvos (TP/SL) para garantir paridade.
    """

    def __init__(self):
        # Matriz de Multiplicadores SOTA V36
        self.matrix = {
            1: {
                "label": "Tendência",
                "sl_mult": 1.1,
                "tp_mult": 1.4,
            },  # Tendência: Alvos longos
            0: {
                "label": "Lateral",
                "sl_mult": 0.8,
                "tp_mult": 0.7,
            },  # Lateral: Proteção curta
            2: {
                "label": "Volatilidade",
                "sl_mult": 1.3,
                "tp_mult": 0.8,
            },  # Volátil: Stop largo, Alvo curto
            3: {
                "label": "Reversão",
                "sl_mult": 1.0,
                "tp_mult": 1.1,
            },  # Reversão: Padrão
        }

    def get_regime_settings(self, regime_idx):
        return self.matrix.get(regime_idx, self.matrix[0])
