import pandas as pd
import numpy as np
import logging
import asyncio
import sys
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.ai_core import AICore, InferenceEngine
from backend.risk_manager import RiskManager, RegimeExpert
from backend.data_collector import DataCollector
from backend.mt5_bridge import MT5Bridge

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class BacktestPro:
    def __init__(
        self, symbol="WIN$", n_candles=5000, timeframe="M1", data_file=None, **kwargs
    ):
        self.symbol = symbol
        self.n_candles = n_candles
        self.timeframe = timeframe
        self.data_file = data_file
        self.bridge = MT5Bridge()
        self.ai = kwargs.get("ai_core", AICore())
        # Tenta carregar o motor de inferência (se existir o peso SOTA)
        try:
            self.inference = InferenceEngine(
                model_path="backend/patchtst_weights_sota.pth"
            )
            self.ai.inference_engine = self.inference
            logging.info("--- Motor de Inferência SOTA carregado.")
        except Exception as e_engine:
            self.inference = None
            self.ai.inference_engine = None
            logging.warning(
                f"[AVISO] Pesos SOTA não carregados ({e_engine}). Usando modo degenerado (Sentiment/OBI)."
            )

        self.risk = RiskManager()
        self.expert = RegimeExpert()  # [v36 Expert] Injeta o Expert de Regimes
        self.collector = DataCollector(symbol)

        # Parâmetros Editáveis no Grid Search - [ANTIVIBE-CODING]
        # Carrega Golden Params se existirem, senão usa defaults validados em 23/02/2026
        locked_params = {}
        try:
            import json

            # [v24] Sincronizado com a versão mais recente de Lucro Assimétrico
            params_path = os.path.join(
                os.path.dirname(__file__), "v24_locked_params.json"
            )
            if os.path.exists(params_path):
                with open(params_path, "r") as f:
                    config = json.load(f)
                locked_params = config.get("strategy_params", config)
                logging.info(
                    "[SEC] Golden Params V24 carregados com sucesso no BacktestPro."
                )
            else:
                # Fallback para v22 se v24 não existir (segurança)
                params_path_v22 = os.path.join(
                    os.path.dirname(__file__), "v22_locked_params.json"
                )
                if os.path.exists(params_path_v22):
                    with open(params_path_v22, "r") as f:
                        config = json.load(f)
                    locked_params = config.get("strategy_params", config)
                    logging.info("[SEC] Fallback: Golden Params V22 carregados.")
        except Exception as e:
            logging.warning(
                f"[AVISO] Falha ao carregar Golden Params ({e}). Usando defaults hardcoded."
            )

        self.opt_params = {
            "rsi_period": kwargs.get("rsi_period", locked_params.get("rsi_period", 9)),
            "bb_dev": kwargs.get("bb_dev", locked_params.get("bb_dev", 2.0)),
            "vol_spike_mult": kwargs.get(
                "vol_spike_mult", locked_params.get("vol_spike_mult", 1.0)
            ),
            "trailing_trigger": kwargs.get(
                "trailing_trigger", locked_params.get("trailing_trigger", 70.0)
            ),
            "trailing_lock": kwargs.get(
                "trailing_lock", locked_params.get("trailing_lock", 50.0)
            ),
            "trailing_step": kwargs.get(
                "trailing_step", locked_params.get("trailing_step", 5.0)
            ),
            "sl_dist": kwargs.get("sl_dist", locked_params.get("sl_dist", 150.0)),
            "tp_dist": kwargs.get("tp_dist", locked_params.get("tp_dist", 400.0)),
            "confidence_threshold": kwargs.get(
                "confidence_threshold", locked_params.get("confidence_threshold", 0.60)
            ),
            "aggressive_mode": kwargs.get("aggressive_mode", True),
            "use_trailing_stop": kwargs.get("use_trailing_stop", True),
            "dynamic_lot": kwargs.get(
                "dynamic_lot", locked_params.get("dynamic_lot", False)
            ),
            "start_time": kwargs.get("start_time", "09:00"),
            "end_time": kwargs.get("end_time", "17:15"),
            "daily_trade_limit": kwargs.get(
                "daily_trade_limit", locked_params.get("daily_trade_limit", 999)
            ),
            "use_flux_filter": kwargs.get(
                "use_flux_filter", locked_params.get("use_flux_filter", True)
            ),
            "flux_imbalance_threshold": kwargs.get(
                "flux_imbalance_threshold",
                locked_params.get("flux_imbalance_threshold", 0.95),
            ),
            "bollinger_squeeze_threshold": kwargs.get(
                "bollinger_squeeze_threshold",
                locked_params.get("bollinger_squeeze_threshold", 1.2),
            ),
            "min_atr_threshold": kwargs.get(
                "min_atr_threshold", locked_params.get("min_atr_threshold", 50.0)
            ),
            "be_trigger": kwargs.get(
                "be_trigger", locked_params.get("be_trigger", 60.0)
            ),
            "be_lock": kwargs.get("be_lock", locked_params.get("be_lock", 5.0)),
            "partial_profit_points": kwargs.get(
                "partial_profit_points",
                locked_params.get("partial_profit_points", 70.0),
            ),
            "base_lot": kwargs.get("base_lot", locked_params.get("base_lot", 1)),
            "use_ai_core": kwargs.get(
                "use_ai_core", locked_params.get("use_ai_core", True)
            ),
            "vwap_dist_threshold": kwargs.get(
                "vwap_dist_threshold", locked_params.get("vwap_dist_threshold", 400.0)
            ),
            "pyramid_profit_threshold": kwargs.get(
                "pyramid_profit_threshold",
                locked_params.get("pyramid_profit_threshold", 100.0),
            ),
            "pyramid_signal_threshold": kwargs.get(
                "pyramid_signal_threshold",
                locked_params.get("pyramid_signal_threshold", 0.6),
            ),
            "pyramid_max_volume": kwargs.get(
                "pyramid_max_volume", locked_params.get("pyramid_max_volume", 1)
            ),
            "volatility_pause_threshold": kwargs.get(
                "volatility_pause_threshold",
                locked_params.get("volatility_pause_threshold", 250.0),
            ),
            "volatility_scalability_threshold": kwargs.get(
                "volatility_scalability_threshold", 450.0
            ),  # [v24.3] Limite para pausa total
            "reduced_lot_factor": kwargs.get(
                "reduced_lot_factor", 0.5
            ),  # [v24.3] Redução de lote em vol alta
            "rsi_buy_level": kwargs.get(
                "rsi_buy_level", locked_params.get("rsi_buy_level", 32)
            ),
            "rsi_sell_level": kwargs.get(
                "rsi_sell_level", locked_params.get("rsi_sell_level", 68)
            ),
            "confidence_buy_threshold": kwargs.get("confidence_buy_threshold", None),
            "confidence_sell_threshold": kwargs.get("confidence_sell_threshold", None),
            "use_confidence_filter": kwargs.get(
                "use_confidence_filter",
                locked_params.get("use_confidence_filter", True),
            ),
            "use_anti_exhaustion": kwargs.get(
                "use_anti_exhaustion", locked_params.get("use_anti_exhaustion", True)
            ),
            "use_anti_trap": kwargs.get(
                "use_anti_trap", locked_params.get("use_anti_trap", True)
            ),
        }

        logging.warning(
            f"[INIT] [INIT-STATE] use_ai_core_param={self.opt_params['use_ai_core']}"
        )

        # [v52.1] SINCRONIZAÇÃO DE PARÂMETROS: Injeta opt_params no RiskManager
        # Garante que os valores do JSON (golden params) sejam usados em execução
        self.risk.daily_trade_limit = self.opt_params["daily_trade_limit"]
        self.risk.be_trigger = self.opt_params["be_trigger"]
        self.risk.be_lock = self.opt_params["be_lock"]
        self.risk.partial_profit_points = self.opt_params["partial_profit_points"]
        self.risk.vwap_dist_threshold = self.opt_params.get(
            "vwap_dist_threshold", 400.0
        )
        self.risk.min_atr_threshold = self.opt_params.get("min_atr_threshold", 50.0)
        self.risk.bollinger_squeeze_threshold = self.opt_params.get(
            "bollinger_squeeze_threshold", 1.2
        )
        self.risk.flux_imbalance_threshold = self.opt_params.get(
            "flux_imbalance_threshold", 1.5
        )
        # Sincroniza threshold de confiança com o AICore (Convertendo 0.65 -> 65.0)
        self.ai.confidence_buy_threshold = (
            float(self.opt_params.get("confidence_buy_threshold") or 0.65) * 100.0
        )
        self.ai.confidence_sell_threshold = (
            float(self.opt_params.get("confidence_sell_threshold") or 0.35) * 100.0
        )
        self.ai.uncertainty_threshold = float(
            self.opt_params.get("uncertainty_threshold") or 0.4
        )

        if hasattr(self.ai, "vwap_dist_threshold"):
            self.ai.vwap_dist_threshold = self.opt_params.get(
                "vwap_dist_threshold", 450.0
            )
        # [SOTA v22.5.3] Sincroniza Bias H1 (paridade com bot live)
        self.ai.use_h1_trend_bias = bool(
            kwargs.get(
                "use_h1_trend_bias", locked_params.get("use_h1_trend_bias", True)
            )
        )
        self.ai.h1_ma_period = int(
            kwargs.get("h1_ma_period", locked_params.get("h1_ma_period", 20))
        )
        self.ai.h1_hysteresis_pts = float(locked_params.get("h1_hysteresis_pts", 400.0))
        # [SOTA v22.5.4] Confidence Relax (paridade com bot live)
        self.ai.confidence_relax_factor = float(
            locked_params.get("confidence_relax_factor", 0.80)
        )
        self.ai.atr_confidence_relax_trigger = float(
            locked_params.get("atr_confidence_relax_trigger", 100.0)
        )
        logging.info(
            f"[SYNC] [v22.5.1] RiskManager sincronizado: limite={self.risk.daily_trade_limit} | OBI={self.risk.flux_imbalance_threshold} | Squeeze={self.risk.bollinger_squeeze_threshold}"
        )
        logging.info(
            f"[DATA] [v22.5.3/4/5] H1 + Hysteresis: use_h1={self.ai.use_h1_trend_bias} | MA={self.ai.h1_ma_period} | Hyst={self.ai.h1_hysteresis_pts} | Relax={self.ai.confidence_relax_factor}"
        )

        # [v36.2] Injeta toggles de Expert Mode no AICore
        self.ai.use_confidence_filter = self.opt_params["use_confidence_filter"]
        self.ai.use_anti_exhaustion = self.opt_params["use_anti_exhaustion"]
        self.ai.use_anti_trap = self.opt_params["use_anti_trap"]

        # Estado do Backtest
        self.initial_balance = kwargs.get("initial_balance", 500.0)
        self.balance = self.initial_balance
        self.equity_curve = [self.initial_balance]
        self.sentiment_stream = kwargs.get(
            "sentiment_stream", None
        )  # {timestamp: score}
        self.timestamps = []
        self.trades = []
        self.position = None  # {'side': 'buy/sell', 'entry_price': float, 'sl': float, 'tp': float, 'lots': int}
        self.consecutive_wins = 0  # Anti-Martingale tracker

        # Gestão de Performance
        self.max_drawdown = 0.0
        self.peak_balance = self.initial_balance
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        # Tracking de Oportunidades (Shadow Trading)
        self.shadow_signals = {
            "total_missed": 0,
            "filtered_by_ai": 0,
            "filtered_by_flux": 0,
            "filtered_by_bias": 0,
            "veto_reasons": {},
            "shadow_by_date": {},   # [GRANULAR] vetos segregados por data (AAAA-MM-DD)
            "v22_candidates": 0,
            "component_fail": {"rsi": 0, "bb": 0, "volume": 0},
            "tiers": {"70-75": 0, "75-80": 0, "80-85": 0},
        }
        self.last_day = None
        self.last_trade_time = datetime(2000, 1, 1)  # Cooldown control geral
        # [MELHORIA H - 03/03/2026] Cooldown diferenciado por direção
        self._last_buy_time = datetime(2000, 1, 1)  # Cooldown independente de COMPRA
        self._last_sell_time = datetime(2000, 1, 1)  # Cooldown independente de VENDA
        # [PAUSA PARCIAL - 03/03/2026] Flag de pausa por ATR extremo na abertura
        # True = operações suspensas até ATR normalizar (< ATR_NORMALIZA)
        self._dia_pausado_atr = False
        self.data = None  # Para inspeção externa

    def _shadow_veto(self, reason: str, ts) -> None:
        """
        [GRANULAR] Registra um veto no shadow_signals de forma dupla:
          - veto_reasons[reason]: contador global legado (retrocompatível)
          - shadow_by_date[AAAA-MM-DD][reason]: contador por data (novo)

        Parâmetros:
            reason: string identificadora do veto (ex: 'PANICO_MERCADO_SEM_BYPASS')
            ts:     timestamp do candle (datetime, pd.Timestamp ou qualquer obj com .date())
        """
        # Legado — mantém compatibilidade total com scripts existentes
        self.shadow_signals["veto_reasons"][reason] = (
            self.shadow_signals["veto_reasons"].get(reason, 0) + 1
        )
        # Granular por data
        try:
            date_key = str(ts.date()) if hasattr(ts, "date") else str(ts)[:10]
        except Exception:
            date_key = "desconhecido"
        daily = self.shadow_signals["shadow_by_date"].setdefault(date_key, {})
        daily[reason] = daily.get(reason, 0) + 1

    async def load_data(self):
        if self.data_file is not None and os.path.exists(self.data_file):
            logging.info(
                f"[LOAD] Lendo DataFrame Estático em O(1) do filepath: {self.data_file} (Amostra: {self.n_candles} velas)"
            )
            df = pd.read_csv(self.data_file, nrows=self.n_candles)
            df["time"] = pd.to_datetime(df["time"])
            df.set_index("time", inplace=True)
            self.data = df
            return self.data

        logging.info(f"📥 Coletando {self.n_candles} candles de {self.symbol}...")
        if not self.bridge.connect():
            logging.error("❌ Falha ao conectar no MetaTrader 5.")
            return None

        # Pega o timeframe do MT5 (ex: mt5.TIMEFRAME_M1)
        import MetaTrader5 as mt5

        tf = mt5.TIMEFRAME_M1  # Hardcoded for backtest simplicity

        rates = await asyncio.to_thread(
            mt5.copy_rates_from_pos, self.symbol, tf, 0, self.n_candles
        )
        if rates is None or len(rates) == 0:
            logging.error(
                f"❌ Falha na coleta de candles para {self.symbol}. Verifique o Market Watch."
            )
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        logging.info(f"✅ {len(df)} candles carregados.")
        self.data = df
        return self.data

    def simulate_oco(self, row, position, prev_row=None):
        """
        Simula execução OCO e Trailing Stop SOTA (v24.1 Pro).
        """
        side = position["side"]
        sl = position["sl"]
        tp = position["tp"]
        entry = position["entry_price"]
        use_trailing = self.opt_params.get("use_trailing_stop", False)

        if side == "buy":
            # [v24.1] Trailing Stop Estrutural (Mínima M1 Anterior)
            if prev_row is not None:
                struct_sl = self.risk.get_structural_stop("buy", prev_row)
                if struct_sl and struct_sl > position["sl"]:
                    position["sl"] = struct_sl
                    logging.debug(
                        f"🧱 [v24.1 TRAILING-ESTRUTURAL] SL movido p/ {struct_sl} (Mínima Ant)"
                    )

            # 1. Lógica de Trailing Stop - COMPRA (USA PARÂMETROS PADRÃO)
            trigger_pts = self.opt_params.get("trailing_trigger", 70.0)
            lock_pts = self.opt_params.get("trailing_lock", 50.0)
            step_pts = self.opt_params.get("trailing_step", 20.0)

            # 1.1 Lógica de Breakeven [v52.0]
            be_trigger = self.opt_params.get("be_trigger", self.risk.be_trigger)
            be_lock = self.opt_params.get("be_lock", self.risk.be_lock)
            profit_pts_be = row["high"] - entry

            if profit_pts_be >= be_trigger and position["sl"] < entry:
                position["sl"] = entry + be_lock
                logging.info(
                    f"🛡️ [v24.1 BREAKEVEN] SL movido p/ {position['sl']} (+{be_lock})"
                )

            # 1.2 Lógica de Trailing Stop SOTA
            if row["low"] <= sl:
                return "SL", sl

            if use_trailing:
                profit_pts = row["high"] - entry
                if profit_pts >= trigger_pts:
                    initial_lock = entry + lock_pts
                    if position["sl"] < initial_lock:
                        position["sl"] = initial_lock
                    new_sl = row["high"] - (trigger_pts - lock_pts)
                    if new_sl > position["sl"] + step_pts:
                        position["sl"] = new_sl

            # 1.3 Take Profit com Time-Decay [v50.1]
            elapsed = (row.name - position["time"]).total_seconds()
            tp_dist = abs(position["tp"] - entry)
            decayed_tp_dist = self.risk.apply_time_decay_to_tp(tp_dist, elapsed)

            if row["high"] >= (entry + decayed_tp_dist):
                return "TP_DECAY", (entry + decayed_tp_dist)

        else:  # sell
            # [v24.1] Trailing Stop Estrutural (Máxima M1 Anterior)
            if prev_row is not None:
                struct_sl = self.risk.get_structural_stop("sell", prev_row)
                if struct_sl and (position["sl"] == 0 or struct_sl < position["sl"]):
                    position["sl"] = struct_sl
                    logging.debug(
                        f"🧱 [v24.1 TRAILING-ESTRUTURAL] SL movido p/ {struct_sl} (Máxima Ant)"
                    )

            # 1. Lógica de Trailing Stop - VENDA (USA ASSIMETRIA v50.1)
            atr_now = row.get("atr_current", 100.0)
            trigger_pts, lock_pts, step_pts = self.risk.get_dynamic_trailing_params(
                atr_now, side="sell"
            )

            # 2.1 Lógica de Breakeven [v52.0]
            be_trigger = self.opt_params.get("be_trigger", self.risk.be_trigger)
            be_lock = self.opt_params.get("be_lock", self.risk.be_lock)
            profit_pts_be = entry - row["low"]

            if profit_pts_be >= be_trigger and position["sl"] > entry:
                position["sl"] = entry - be_lock
                logging.info(
                    f"🛡️ [v24.1 BREAKEVEN] SL movido p/ {position['sl']} (-{be_lock})"
                )

            # 2.2 Lógica de Trailing Stop SOTA
            if row["high"] >= sl:
                return "SL", sl

            if use_trailing:
                profit_pts = entry - row["low"]
                if profit_pts >= trigger_pts:
                    initial_lock = entry - lock_pts
                    if position["sl"] == 0 or position["sl"] > initial_lock:
                        position["sl"] = initial_lock
                    new_sl = row["low"] + (trigger_pts - lock_pts)
                    if new_sl < position["sl"] - step_pts:
                        position["sl"] = new_sl

            # 2.3 Take Profit com Time-Decay [v50.1]
            elapsed = (row.name - position["time"]).total_seconds()
            tp_dist = abs(position["tp"] - entry)
            decayed_tp_dist = self.risk.apply_time_decay_to_tp(tp_dist, elapsed)

            if row["low"] <= (entry - decayed_tp_dist):
                return "TP_DECAY", (entry - decayed_tp_dist)

        # 4. Scaling Out — Saída Parcial [SOTA v26] Real Financeiramente
        if not position.get("partial_done", False):
            # Se atingiu o lucro parcial (Ex: 50pts)
            partial_pts = self.risk.partial_profit_points
            profit_now = profit_pts_be if side == "buy" else (entry - row["low"])

            if profit_now >= partial_pts and position["lots"] >= 2:
                # Realiza lucro de 1 contrato (metade no caso de base_lot=2)
                symbol_mult = 0.20 if "WIN" in self.symbol else 10.0
                partial_pnl = partial_pts * 1 * symbol_mult  # 1 contrato de parcial
                self.balance += partial_pnl
                self.daily_pnl += partial_pnl

                position["partial_done"] = True
                position["lots"] -= 1  # Mantém o restante no trade
                logging.debug(
                    f"✂️ PARCIAL REALIZADA: +{partial_pnl} R$ (Mantém {position['lots']} lotes)"
                )

        return None, None

    async def run(self):
        # [v22.2] Garante que os dados existam antes do processamento
        if self.data is None:
            data_loaded = await self.load_data()
            if data_loaded is None or data_loaded.empty:
                logging.error(
                    "❌ Erro no BacktestPro: falha crítica ao carregar dados."
                )
                return

        data = self.data

        logging.info(f"🚀 Iniciando Simulação High Fidelity com {len(data)} velas...")

        # ---- PRE-CALCULATIONS FOR EXTREME SPEED ----
        # 1. RSI (Usa EWM para suavizar e evitar NaNs persistentes)
        rsi_p = self.opt_params["rsi_period"]
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=rsi_p, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=rsi_p, adjust=False).mean()
        rs = gain / (loss + 1e-9)
        data["rsi"] = 100 - (100 / (1 + rs))
        data["rsi"] = data["rsi"].fillna(50.0)  # Estabiliza início

        # 2. Bollinger Bands
        bb_d = self.opt_params["bb_dev"]
        data["sma_20"] = data["close"].rolling(window=20).mean()
        data["std_20"] = data["close"].rolling(window=20).std()
        data["upper_bb"] = data["sma_20"] + bb_d * data["std_20"]
        data["lower_bb"] = data["sma_20"] - bb_d * data["std_20"]

        # 2.5 RSI calculation (SOTA Period = 9)
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=9, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=9, adjust=False).mean()
        rs = gain / (loss + 1e-9)
        data["rsi"] = 100 - (100 / (1 + rs))

        # 3. ATR 14
        tr = pd.concat(
            [
                data["high"] - data["low"],
                (data["high"] - data["close"].shift()).abs(),
                (data["low"] - data["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        data["atr_current"] = tr.rolling(window=14).mean()

        # [v22.3] Cálculo do ADX 14 (Vectorized)
        plus_dm = (data["high"] - data["high"].shift(1)).clip(lower=0)
        minus_dm = (data["low"].shift(1) - data["low"]).clip(lower=0)

        # Filtro de direção do DM
        plus_dm.loc[plus_dm < minus_dm] = 0
        minus_dm.loc[minus_dm < plus_dm] = 0

        tr_smooth = tr.ewm(span=14, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(span=14, adjust=False).mean() / tr_smooth)
        minus_di = 100 * (minus_dm.ewm(span=14, adjust=False).mean() / tr_smooth)
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
        data["adx"] = dx.ewm(span=14, adjust=False).mean()

        # [MELHORIA H - V28] EMA30 e EMA90 para Filtro de Tendência Diária
        data["ema30"] = data["close"].ewm(span=30, adjust=False).mean()
        data["ema90"] = data["close"].ewm(span=90, adjust=False).mean()

        # 4. Volume SMA
        data["vol_sma"] = data["tick_volume"].rolling(window=20).mean().bfill()

        # [SOTA v26] VWAP Intraday & Bands Pre-calculation
        tp = (data["high"] + data["low"] + data["close"]) / 3
        v = data["tick_volume"]
        # [SOTA v26] VWAP Intraday & Bands Pre-calculation - Corrigido para estabilidade de Index
        data["day"] = data.index.date
        group_v = v.groupby(data["day"])
        group_tp_v = (tp * v).groupby(data["day"])
        data["vwap"] = group_tp_v.cumsum() / group_v.cumsum()
        data["vwap_std"] = tp.rolling(20).std().fillna(0)  # Std local de 20p como o bot

        # [SOTA v25] Microstructure Pre-calculation (Vectorized)
        logging.info("🔬 Calculando Microestrutura em Vetor (CVD/OFI/Ratio/Accel)...")
        body = data["close"] - data["open"]
        high_low = data["high"] - data["low"] + 1e-8
        # Simula CVD com base no fechamento do candle
        data["cvd"] = (
            data["tick_volume"]
            * body.apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
        ).cumsum()

        # [v24.5] Aceleração de CVD (Sweep Institucional)
        # Calcula a mudança de CVD normalizada pelo volume para detectar urgência
        data["cvd_accel"] = data["cvd"].diff() / (data["tick_volume"] + 1e-8)

        # OFI simplificado para backtest OHLCV
        data["ofi"] = body / high_low
        # Volume Ratio (Z-score like)
        data["volume_ratio"] = data["tick_volume"] / (data["vol_sma"] + 1e-8)

        self.data = data  # Expor para debug externo

        # 5. Regime Detection (Vectorized)
        try:
            obi_dummy = np.zeros(len(data))
            states = np.column_stack((data["atr_current"].fillna(0).values, obi_dummy))
            raw_labels = self.ai.regime_model.predict(states)
            centers = self.ai.regime_model.cluster_centers_
            sorted_indices = np.argsort(centers[:, 0])
            mapped_labels = np.array(
                [np.where(sorted_indices == rl)[0][0] for rl in raw_labels]
            )
            data["regime"] = mapped_labels
        except:
            data["regime"] = 0

        # 6. Directional Probability (Vectorized)
        prices = data["close"].values
        returns = np.diff(prices) / prices[:-1]
        returns_pad = np.insert(returns, 0, 0)

        ret_series = pd.Series(returns_pad, index=data.index)
        all_pos = (ret_series > 0).rolling(window=4).sum() == 4
        all_neg = (ret_series < 0).rolling(window=4).sum() == 4
        roll_sum = ret_series.rolling(window=4).sum()

        base_probs = np.where(all_pos | all_neg, 0.85, np.abs(roll_sum) * 100)
        data["dir_prob"] = np.clip(base_probs, 0.0, 0.99)
        data["dir_prob"] = data["dir_prob"].fillna(0.5)

        # Janela para indicadores (ex: 60 períodos)
        lookback = 60
        for i in range(lookback, len(data)):
            row = data.iloc[i]
            window = data.iloc[i - lookback : i]

            # 0. Reset de Perda Diária (Mudança de Dia)
            current_date = row.name.date()
            if self.last_day and current_date != self.last_day:
                logging.info(
                    f"📅 Mudança de dia detectada ({self.last_day} -> {current_date}). Resetando métricas diárias."
                )
                self.daily_pnl = 0.0
                self.daily_trade_count = 0

                # [V22.2] VERIFICAÇÃO DE GAP DE ABERTURA
                try:
                    # Busca o fechamento do dia anterior para o cálculo do GAP
                    prev_day_data = data[data.index.date < current_date].tail(1)
                    if not prev_day_data.empty:
                        prev_close = prev_day_data["close"].iloc[0]
                        opening_price = row["open"]
                        gap_ok, gap_msg = self.risk.check_gap_safety(
                            opening_price, prev_close
                        )
                        if not gap_ok:
                            self._dia_pausado_atr = (
                                True  # Usa a mesma flag de pausa para o Gap
                            )
                            logging.warning(
                                f"🚫 [VETO V22.2] Dia {current_date} pausado por: {gap_msg}"
                            )
                except Exception as e_gap:
                    logging.error(f"Erro ao calcular Gap: {e_gap}")
            self.last_day = current_date

            # 1. Verificar saída de posição aberta (Simulação OCO)
            if self.position:
                # [v24.5] MONITORAMENTO DE SAÍDA PARCIAL (SCALING OUT) - SNIPER MODE
                if not self.position.get("partial_executed", False):
                    price_now = row["close"]
                    side_now = self.position["side"]
                    pnl_pts = (
                        (price_now - self.position["entry_price"])
                        if side_now == "buy"
                        else (self.position["entry_price"] - price_now)
                    )

                    # Correção da assinatura (v24.5): symbol, ticket, current_profit_points, current_volume, regime
                    if self.risk.check_scaling_out(
                        self.symbol,
                        0,
                        pnl_pts,
                        self.position["lots"],
                        regime=getattr(self, "current_regime", 0),
                    ):
                        # [v27] Executa Parcial: Registro Obrigatório para Auditoria Financeira
                        full_lots = self.position["lots"]
                        partial_lots = max(1, int(full_lots // 2))
                        
                        if full_lots >= 2:
                            mult = 0.20 if "WIN" in self.symbol else 10.0
                            partial_pnl = pnl_pts * partial_lots * mult

                            # Registro na lista de trades para o relatório
                            self.trades.append({
                                "entry_time": self.position["time"],
                                "exit_time": row.name,
                                "side": self.position["side"],
                                "entry_price": self.position["entry_price"],
                                "exit_price": row["close"],
                                "lots": float(partial_lots),
                                "pnl_pts": float(pnl_pts),
                                "pnl_fin": float(partial_pnl),
                                "reason": "SCALING_OUT",
                                "quantile_confidence": self.position.get("quantile_confidence", "NORMAL")
                            })

                            self.balance += partial_pnl
                            self.daily_pnl += partial_pnl
                            self.position["lots"] -= partial_lots
                            self.position["partial_executed"] = True

                            # [v24.5] Ajusta Stop Loss para o Breakeven após parcial
                            self.position["sl"] = self.position["entry_price"]

                            logging.info(
                                f"💰 [PARCIAL] {side_now.upper()} @ {price_now} | Lucro: R${partial_pnl:.2f} | Restante: {self.position['lots']} lotes | SL @ BE"
                            )

                exit_type, exit_price = self.simulate_oco(
                    row, self.position, prev_row=data.iloc[i - 1] if i > 0 else None
                )
                if exit_type:
                    self._close_trade(exit_price, exit_type, row.name)
                    self.last_trade_time = row.name  # Inicia cooldown após fechar
                elif (
                    row.name - self.position["time"]
                ).total_seconds() / 60.0 >= self.risk.max_trade_duration_min:
                    # [v52.0] Alpha Decay - Saída Compulsória por tempo (Exclusivo HFT)
                    self._close_trade(row["close"], "ALPHA_DECAY", row.name)
                    self.last_trade_time = row.name
                else:
                    # [MELHORIA-G] Verificar reversão de OBI com posição aberta (Saída de Emergência)
                    # Aplica somente quando use_ai_core está ativo (OBI proxy disponível)
                    _use_ai_g = self.opt_params.get("use_ai_core", False)
                    if _use_ai_g and self.position:
                        _cr_pos_g = row["high"] - row["low"]
                        _obi_pos_g = (
                            ((row["close"] - row["open"]) / _cr_pos_g * 3.0)
                            if _cr_pos_g > 0
                            else 0.0
                        )
                        _obi_pos_g = max(-3.0, min(3.0, _obi_pos_g))
                        if self.risk.check_obi_reversal(self.position["side"], _obi_pos_g):
                            self._close_trade(row["close"], "OBI_REVERSAL", row.name)
                            self.last_trade_time = row.name

                    if self.position:  # Piramida somente se posição ainda estiver aberta
                        # [v50.1] Simulação de Piramidação (Scaling In) - Apenas se posição ainda ativa
                        profit_now = (
                            (row["close"] - self.position["entry_price"])
                            if self.position["side"] == "buy"
                            else (self.position["entry_price"] - row["close"])
                        )
                        # [MELHORIA-C] Piramidação Progressiva em Alta Convicção.
                        # Em tendência forte (H1 confirmado + ADX > 30), eleva o limite
                        # de piramidação de 1 para 2 contratos adicionais.
                        # v24_locked_params.json (pyramid_max_volume: 1) é a base para
                        # condições normais — esta lógica é condicional e aditiva.
                        _max_pyra_c = self.opt_params.get("pyramid_max_volume", 1)
                        _use_ai_c = self.opt_params.get("use_ai_core", False)
                        if _use_ai_c:
                            _h1_for_c = getattr(self.ai, "h1_trend", 0)
                            _adx_for_c = 0.0
                            try:
                                _adx_for_c = float(data.loc[row.name, "adx"])
                            except Exception:
                                pass
                            if _h1_for_c != 0 and _adx_for_c > 30:
                                _max_pyra_c = min(2, _max_pyra_c * 2)
                                logging.info(
                                    f"[MELHORIA-C PYRAMID+] ADX={_adx_for_c:.1f} H1={_h1_for_c} "
                                    f"→ max_pyramid elevado para {_max_pyra_c} (tendência forte)"
                                )
                        if self.risk.allow_pyramiding(
                            profit_now,
                            row.get("ofi", 0),
                            self.position["lots"],
                            profit_threshold=self.opt_params.get(
                                "pyramid_profit_threshold"
                            ),
                            signal_threshold=self.opt_params.get(
                                "pyramid_signal_threshold"
                            ),
                            max_volume=_max_pyra_c,
                        ):
                            self.position["lots"] += 1
                            logging.info(
                                f"💎 [PIRAMIDAÇÃO] +1 contrato adicionado @ {row['close']} | Novo Lote: {self.position['lots']}"
                            )

            # [SOTA v5] Simulação de Spread Dinâmico (1.0 a 3.5 pts)
            fixed_spread = self.opt_params.get("spread")
            if fixed_spread is not None:
                current_spread = fixed_spread
            else:
                current_spread = 1.0 + (row["high"] - row["low"]) * 0.1
                current_spread = min(4.0, max(1.0, current_spread))

            # [SOTA v5] Sincronizar Âncora de Sentimento (Price-Based Decay)
            self.ai.update_sentiment_anchor(row["close"])

            # [v24.5] Inicialização para segurança do escopo
            ai_decision = {}

            # [SOTA v22.5.3] Atualizar Bias H1 (resample M1→H1 sem olhar o futuro)
            if (
                self.ai.use_h1_trend_bias and i % 60 == 0
            ):  # Atualiza a cada ~60 candles M1 (1h)
                try:
                    h1_slice = (
                        data.iloc[:i]
                        .resample("1h")
                        .agg(
                            {
                                "open": "first",
                                "high": "max",
                                "low": "min",
                                "close": "last",
                                "tick_volume": "sum",
                            }
                        )
                        .dropna()
                    )
                    if not h1_slice.empty:
                        self.ai.update_h1_trend(h1_slice)
                except Exception as e_h1_bt:
                    logging.debug(f"Bias H1 backtest: {e_h1_bt}")

            # [v22.5.7] Reset de Sinais e Cálculo de Indicadores (Obrigatório em todas as velas)
            v22_buy = v22_sell = False
            v22_buy_raw = v22_sell_raw = False
            rsi = row["rsi"]
            upper_bb = row["upper_bb"]
            lower_bb = row["lower_bb"]
            mid_bb = row["sma_20"]
            atr_current = row["atr_current"]
            vol_sma = row["vol_sma"]

            # 2. Lógica de Entrada (Se estiver zerado)
            if not self.position:
                # 4. Price Action: Rejeição (Pavio)
                body = abs(row["open"] - row["close"])
                upper_wick = row["high"] - max(row["open"], row["close"])
                lower_wick = min(row["open"], row["close"]) - row["low"]

                # 5. Volume Analysis (Alpha V22)
                v_mult = self.opt_params[
                    "vol_spike_mult"
                ]  # [v52.2] Sincronizado com JSON (0.8)
                vol_spike = row["tick_volume"] > (vol_sma * v_mult)

                # [v22.5.7] Gatilhos Técnicos (Candidatos para a IA)
                cond_rsi_buy = rsi < self.opt_params.get("rsi_buy_level", 30)
                cond_bb_buy = row["close"] < lower_bb
                cond_rsi_sell = rsi > self.opt_params.get("rsi_sell_level", 70)
                cond_bb_sell = row["close"] > upper_bb

                current_flux_thresh = self.opt_params.get(
                    "flux_imbalance_threshold", 1.2
                )
                if (
                    self.opt_params.get("adaptive_flux_active", False)
                    and atr_current > 200
                ):
                    current_flux_thresh = 1.05

                cond_vol_buy = row["tick_volume"] > vol_sma * current_flux_thresh
                cond_vol_sell = row["tick_volume"] > vol_sma * current_flux_thresh

                # [MELHORIA-E] Padrão de Candle como confirmação adicional de entrada.
                # Reduz falsos positivos do RSI(9) em M1. Opera como filtro AND — não substitui os demais.
                _prev_e = data.iloc[i - 1] if i > 0 else row
                _body_prev_e = abs(_prev_e["close"] - _prev_e["open"])

                # Engolfo de Alta: corpo atual engloba o corpo anterior na direção altista
                _cond_engulfo_buy = (
                    row["close"] > _prev_e["open"]
                    and row["open"] < _prev_e["close"]
                    and abs(row["close"] - row["open"]) > _body_prev_e
                )
                # Engolfo de Baixa: corpo atual engloba o corpo anterior na direção baixista
                _cond_engulfo_sell = (
                    row["close"] < _prev_e["open"]
                    and row["open"] > _prev_e["close"]
                    and abs(row["close"] - row["open"]) > _body_prev_e
                )
                # Pin Bar de Alta: pavio inferior >= 2x corpo, pavio superior pequeno
                _cond_pinbar_buy = (
                    body > 0
                    and lower_wick >= body * 2.0
                    and upper_wick <= body * 0.5
                )
                # Pin Bar de Baixa: pavio superior >= 2x corpo, pavio inferior pequeno
                _cond_pinbar_sell = (
                    body > 0
                    and upper_wick >= body * 2.0
                    and lower_wick <= body * 0.5
                )
                cond_candle_confirm_buy = _cond_engulfo_buy or _cond_pinbar_buy
                cond_candle_confirm_sell = _cond_engulfo_sell or _cond_pinbar_sell

                v22_buy_raw = cond_rsi_buy and cond_bb_buy and cond_vol_buy and cond_candle_confirm_buy
                v22_sell_raw = cond_rsi_sell and cond_bb_sell and cond_vol_sell and cond_candle_confirm_sell

                # --- MELHORIA H (V28): Filtro de Tendência Diária ---
                # Na abertura de cada dia, deteta se EMA30 < EMA90 → mercado em baixa.
                # Nesse caso, BUY fica vetado para evitar counter-trend losses.
                current_hour = row.name.hour
                current_minute = row.name.minute
                is_opening_window = (
                    current_hour == 9 and current_minute <= 10
                )  # [v23] Sincronizado com RiskManager
                current_ema30 = row["ema30"]
                current_ema90 = row["ema90"]
                if current_date != getattr(self, "_bias_day", None):
                    # Reset do bias diário na troca de dia
                    self._bias_diario = "neutro"
                    self._bias_day = current_date
                    # [PAUSA PARCIAL - 03/03/2026] Reseta pausa a cada novo dia
                    self._dia_pausado_atr = False
                    self._velas_hoje = 0
                    self._hl_acumulado = 0.0

                # Contador eficiente O(1) para as primeiras 10 velas disponíveis no dia
                self._velas_hoje += 1
                if self._velas_hoje <= 10:
                    self._hl_acumulado += row["high"] - row["low"]

                # [v24.4] MONITORAMENTO DINÂMICO DE RISCO (Córtex de Risco)
                ATR_MM20_AVG = 75.0  # Média histórica do WIN em M1 (Normalização)

                # Média ultra-curta (últimos 10 candles) para detectar estabilização
                last_10_candles = self.data.iloc[max(0, i - 10) : i]
                ultra_short_hl = (
                    (last_10_candles["high"] - last_10_candles["low"]).mean()
                    if len(last_10_candles) > 0
                    else atr_current
                )

                # Cálculo de Inércia de Volatilidade
                if not hasattr(self, "_last_atr"):
                    self._last_atr = atr_current
                atr_delta = atr_current - self._last_atr
                self._last_atr = atr_current

                # Lógica de Normalização Acelerada:
                # Se os últimos 10 min estão estabilizados (< 100 pts de HL médio), relaxamos as travas.
                if ultra_short_hl < 100.0 and self._velas_hoje > 20:
                    risk_index = 0.8  # Nível de segurança normal
                    if self._velas_hoje % 15 == 0:
                        logging.debug(
                            f"📉 [NORMALIZANDO] {row.name} | HL 10min={ultra_short_hl:.1f} | Risco reduzido."
                        )
                else:
                    attenuation = 0.85 if atr_delta < 0 else 1.0
                    risk_index = (atr_current / ATR_MM20_AVG) * attenuation

                # Cálculo de Lote Dinâmico Baseado no Risco
                if risk_index <= 0.85:
                    current_lot_factor = 1.0
                    self._reduced_lot_mode = False
                elif risk_index <= 1.6:
                    current_lot_factor = max(0.5, 1.3 - (risk_index * 0.5))
                    self._reduced_lot_mode = True
                else:
                    current_lot_factor = 0.3
                    self._reduced_lot_mode = True

                self._extreme_vol_factor = current_lot_factor

                # Determinar se podemos operar
                is_momentum_bypass = (
                    ai_decision.get("is_momentum_bypass", False)
                    if "ai_decision" in locals()
                    else False
                )

                # [v24.4] Sensibilidade Fluida:
                # Não há mais veto binário por volatilidade média. O risco agora controla LOTE e BYPASS.
                # Veto apenas em Pânico Absoluto (> 2.5 = 187 pts de ATR)
                #
                # [MELHORIA-H] Bypass Condicional de Pânico (autorizado 17/03/2026).
                # Lógica anterior: veto total se risk > 2.5 e sem momentum_bypass.
                # Lógica nova:
                #   - Sem momentum_bypass → veto total mantido (comportamento original)
                #   - Com momentum_bypass MAS sem H1 confirmado → veto mantido (mercado caótico)
                #   - Com momentum_bypass E H1 confirmado → permite operação com lote reduzido (0.5)
                #     para capturar tendências fortes mesmo em ATR elevado, limitando exposição.
                if risk_index > 2.5:
                    if not is_momentum_bypass:
                        # Caso 1: Pânico sem IA com convicção — veto total (proteção máxima)
                        self._shadow_veto("PANICO_MERCADO_SEM_BYPASS", row.name)
                        continue
                    else:
                        # Caso 2: Momentum bypass ativo — verifica se H1 confirma tendência
                        _h1_panico = getattr(self.ai, "h1_trend", 0)
                        if _h1_panico == 0:
                            # Sem tendência H1 clara → não vale o risco em mercado explosivo
                            self._shadow_veto("PANICO_SEM_H1", row.name)
                            continue
                        # Caso 3: Momentum bypass + H1 confirmado → lote reduzido e segue
                        current_lot_factor = min(current_lot_factor, 0.5)
                        logging.info(
                            f"[MELHORIA-H BYPASS] Pânico com convicção: lote reduzido para 0.5 | "
                            f"ATR={atr_current:.1f} | risk={risk_index:.2f} | H1={_h1_panico}"
                        )

                if is_opening_window:
                    if (
                        current_ema30 < current_ema90 * 0.9998
                    ):  # Margem de 0.02% para evitar falsos alertas
                        self._bias_diario = "baixa"
                    elif current_ema30 > current_ema90 * 1.0002:
                        self._bias_diario = "alta"
                    else:
                        self._bias_diario = "neutro"
                bias_veto_buy = getattr(self, "_bias_diario", "neutro") == "baixa"
                # [AUTORIZADO 03/03/2026] bias_veto_sell relaxado: em dias de alta, permite venda
                # apenas quando gatilho técnico é confirmado (RSI overextended > 72 já foi exigido
                # no v22_sell_raw). O filtro aqui reflete a mesma lógica do H1 bypass no AICore.
                # Em bias de alta, VENDA exige RSI mais extremo (> 70 já capturado no v22_sell_raw)
                # então removemos o bloqueio absoluto para permitir reversões intraday.
                bias_veto_sell = (
                    False  # [v52.2] Removido bloqueio absoluto — veto H1/RSI já cobrem
                )
                # [ANTIVIBE-CODING] bias_veto_sell relaxado — autorizado pelo usuário em 03/03/2026

                # Gatilhos Alpha V22 (Counter-Trend Sniper)
                # [SOTA v24] Cooldown Dinâmico por Convicção
                # [MELHORIA J - V28] VERY_HIGH=3min
                # [MELHORIA N - V28] Cooldown adaptativo por regime: Tendência=5min, Lateral=9min, Ruído=12min
                cooldown_base = self.opt_params.get("cooldown_minutes", 7)
                last_conf = (
                    self.trades[-1].get("quantile_confidence", "NORMAL")
                    if self.trades
                    else "NORMAL"
                )
                if last_conf == "VERY_HIGH":
                    cooldown_min = 3
                else:
                    # Regime adaptativo: 5min tendência, 9min lateral, 12min ruído
                    _regime_now = row.get(
                        "regime", row["regime"] if "regime" in row else 0
                    )
                    if _regime_now == 1:  # Tendência clara
                        cooldown_min = 5
                    elif _regime_now == 2:  # Ruído/alta volatilidade
                        cooldown_min = 12
                    else:  # Lateral / indefinido
                        cooldown_min = max(cooldown_base, 8)
                # [ANTIVIBE-CODING] Cooldown adaptativo V28-N — aprovado pelo usuário em 01/03/2026
                cooldown_ok = (row.name - self.last_trade_time) >= timedelta(
                    minutes=cooldown_min
                )

                # --- ADAPTIVE REGIME CORTEX ---
                # OBI is approximated as 0.0 in OHLCV backtester
                current_regime = row["regime"]
                use_ai_core = self.opt_params.get("use_ai_core", False)

                # Default for operational filters
                vol_spike_eff = vol_spike
                ai_stability = 0.75  # Default threshold

                # --- [FASE 27] CORTEX DE DECISÃO CEGA ---
                if use_ai_core:
                    # Preparar métricas sincronizadas
                    # [v24.3] Proxy de OBI para Backtest: Deslocamento / Amplitude * 3.0
                    # Representa o desequilíbrio de fluxo baseado na força do candle.
                    candle_range = row["high"] - row["low"]
                    if candle_range > 0:
                        obi = ((row["close"] - row["open"]) / candle_range) * 3.0
                    else:
                        obi = 0.0

                    # Suavização leve para evitar ruído extremo
                    obi = max(-3.0, min(3.0, obi))

                    sentiment_score = 0.0
                    if self.sentiment_stream and row.name in self.sentiment_stream:
                        sentiment_score = self.sentiment_stream[row.name]

                        # [SOTA v5] Atualiza o score interno do AI para que o Decay atue sobre o valor real do candle
                        self.ai.latest_sentiment_score = sentiment_score

                    # Predição PatchTST (Agora com normalização automática no AICore)
                    patchtst_data = 0.0
                    if self.ai.inference_engine is not None:
                        # Extrair janela para predição
                        window_data = data.iloc[i - 64 : i]  # PatchTST usa 64 velas
                        if len(window_data) == 64:
                            # [v50.1] Predição retorna dicionário {"score": float, "confidence": float}
                            pred_res = await self.ai.predict_with_patchtst(
                                self.ai.inference_engine, window_data
                            )
                            patchtst_data = pred_res.get("score", 50.0)

                            # FALLBACK: Se predição for neutra, usar momentum do sentimento como proxy
                            if abs(patchtst_data - 50.0) < 1.0:
                                patchtst_data = 50.0 + (
                                    sentiment_score * 10.0
                                )  # Escala 0-100

                    # Volatilidade Anualizada (Proxy do Bot)
                    log_returns = np.log(window["close"] / window["close"].shift(1))
                    vol_val = float(log_returns.tail(20).std() * np.sqrt(252 * 480))
                    if not np.isfinite(vol_val):
                        vol_val = 0.0

                    # Decisão da IA (Passando OFI se disponível)
                    # No backtest OHLCV, simulamos OFI como 0.5 * sentiment para manter consistência
                    sim_ofi = (sentiment_score * 0.5) if sentiment_score != 0 else 0.0

                    # Atualizar vwap_dist_threshold no AICore se disponível
                    self.ai.vwap_dist_threshold = self.opt_params.get(
                        "vwap_dist_threshold", 400.0
                    )

                    # [v22.5.5-SYNC] Sincronização de Tendência H1 (Alta Frequência - 1 min)
                    if True:
                        try:
                            # Janela ampliada (3000 min = 50h) para garantir SMA20 H1 após gaps noturnos
                            h1_window = data.iloc[max(0, i - 3000) : i + 1]
                            h1_resampled = (
                                h1_window["close"]
                                .resample("1h")
                                .last()
                                .dropna()
                                .to_frame()
                            )
                            self.ai.update_h1_trend(h1_resampled)
                        except Exception as e:
                            if i % 60 == 0:
                                logging.error(
                                    f"🚨 CRASH em update_h1_trend no índice {i}: {e}"
                                )

                    # [v52.5] Sincronização de Histórico para Gatilhos de Squeeze
                    self.ai.micro_analyzer.price_history.append(row["close"])
                    if len(self.ai.micro_analyzer.price_history) > 50:
                        self.ai.micro_analyzer.price_history.pop(0)

                    if (
                        row.name.day == 10
                        and row.name.month == 3
                        and getattr(self, "_debug_printed", 0) < 3
                    ):
                        logging.warning(
                            f"[v22.5.5-STATE] use_ai_core={self.opt_params['use_ai_core']}"
                        )
                        self._debug_printed = getattr(self, "_debug_printed", 0) + 1

                    ai_decision = self.ai.calculate_decision(
                        obi=obi,
                        sentiment=self.ai.latest_sentiment_score,  # Usa score com decay v5
                        patchtst_score=patchtst_data,
                        regime=current_regime,
                        atr=atr_current,
                        volatility=vol_val,
                        hour=row.name.hour,
                        minute=row.name.minute,  # [SOTA v24.1] Sincronia de minuto para Janela de Ouro
                        current_vol=row["tick_volume"],  # [v24.1] Volume Real
                        avg_vol_20=vol_sma,  # [v24.1] Média de Volume 20m
                        ofi=sim_ofi,
                        cvd_accel=row.get(
                            "cvd_accel", 0.0
                        ),  # [v24.5] Novo input de aceleração
                        current_price=row["close"],
                        vwap=row["vwap"],
                        spread=current_spread,
                        sma_20=mid_bb,
                        wdo_aggression=0.0,
                        bluechip_score=0.0,
                    )

                    ai_dir = ai_decision.get("direction", "NEUTRAL")
                    ai_score = ai_decision.get("score", 50.0)
                    is_momentum_bypass = ai_decision.get("is_momentum_bypass", False)

                    # [v36 PRIME] GATILHOS ASSIMÉTRICOS (RSI DINÂMICO) PROVINIENTES DA IA
                    rsi_buy_level = ai_decision.get(
                        "rsi_buy_trigger", self.opt_params.get("rsi_buy_level", 32)
                    )
                    rsi_sell_level = ai_decision.get(
                        "rsi_sell_trigger", self.opt_params.get("rsi_sell_level", 68)
                    )
                    v_spike_mult = self.opt_params.get("vol_spike_mult", 1.5)
                    vol_spike_eff = row["tick_volume"] > (vol_sma * v_spike_mult)

                    # [v24.3] GATILHO DE TENDÊNCIA (Trend-Following)
                    # Se em Momentum Bypass, permite entrada direta sem esperar reversão de RSI/BB
                    v24_momentum_buy = (
                        is_momentum_bypass
                        and ai_dir == "COMPRA"
                        and getattr(self.ai, "h1_trend", 0) >= 0
                    )
                    v24_momentum_sell = (
                        is_momentum_bypass
                        and ai_dir == "VENDA"
                        and getattr(self.ai, "h1_trend", 0) <= 0
                    )

                    # Estabilidade Direcional Corrigida (0=Sell, 100=Buy)
                    if ai_dir == "COMPRA":
                        ai_stability = ai_score / 100.0
                    elif ai_dir == "VENDA":
                        ai_stability = (100.0 - ai_score) / 100.0
                    else:
                        ai_stability = 0.5  # Neutro

                    # Consolidar Sinais
                    v22_buy = (
                        v22_buy_raw
                        and ai_dir == "COMPRA"
                        and ai_stability >= self.opt_params["confidence_threshold"]
                    ) or v24_momentum_buy
                    v22_sell = (
                        v22_sell_raw
                        and ai_dir == "VENDA"
                        and ai_stability >= self.opt_params["confidence_threshold"]
                    ) or v24_momentum_sell

                    if is_momentum_bypass and (v24_momentum_buy or v24_momentum_sell):
                        logging.info(
                            f"🚀 [MOMENTUM ENTRY] {row.name} | Dir: {ai_dir} | Entrando a favor da Inércia Direcional."
                        )

                    self.shadow_signals["v22_candidates"] = (
                        self.shadow_signals.get("v22_candidates", 0) + 1
                    )

                    # [v36.1] Estabilidade Direcional Corrigida (0=Sell, 100=Buy)
                    if ai_dir == "COMPRA":
                        ai_stability = ai_score / 100.0
                    elif ai_dir == "VENDA":
                        ai_stability = (100.0 - ai_score) / 100.0
                    else:
                        ai_stability = 0.5  # Neutro

                    if v22_buy_raw or v22_sell_raw:
                        logging.debug(
                            f"[SINAL] {row.name} | Dir: {ai_dir} | Stability: {ai_stability:.2f} | Veto: {ai_decision.get('veto')} | Reason: {ai_decision.get('reason')}"
                        )

                    if v22_buy_raw or v22_sell_raw:
                        logging.info(
                            f"[DIAGNÓSTICO] {row.name} | Risk Index: {risk_index:.2f} | Lote: {current_lot_factor * 100:.0f}% | IA Score: {ai_score:.1f}"
                        )
                        self.shadow_signals["component_fail"]["ai_veto_total"] = (
                            self.shadow_signals["component_fail"].get(
                                "ai_veto_total", 0
                            )
                            + 1
                        )
                        if ai_dir == "WAIT":
                            reason = ai_decision.get("reason", "UNKNOWN")
                            self._shadow_veto(reason, row.name)
                        else:
                            # Threshold dinâmico v24.4
                            dynamic_thr = ai_decision.get(
                                "dynamic_bypass_thresh",
                                self.opt_params["confidence_threshold"],
                            )
                            if (v22_buy_raw and ai_stability < dynamic_thr) or (
                                v22_sell_raw and ai_stability < dynamic_thr
                            ):
                                self._shadow_veto("LOW_CONFIDENCE", row.name)

                    # Decisão Final: Precisa do gatilho técnico + viés de direção da IA + confiança + travas operacionais
                    thr_buy = (
                        self.opt_params.get("confidence_buy_threshold")
                        or self.opt_params["confidence_threshold"]
                    )
                    thr_sell = (
                        self.opt_params.get("confidence_sell_threshold")
                        or self.opt_params["confidence_threshold"]
                    )

                    v22_buy = (
                        (v22_buy_raw or is_momentum_bypass)
                        and (ai_dir == "COMPRA")
                        and (ai_stability >= thr_buy or is_momentum_bypass)
                        and cooldown_ok
                        and (not bias_veto_buy or is_momentum_bypass)
                    )
                    v22_sell = (
                        (v22_sell_raw or is_momentum_bypass)
                        and (ai_dir == "VENDA")
                        and (ai_stability >= thr_sell or is_momentum_bypass)
                        and cooldown_ok
                        and (not bias_veto_sell or is_momentum_bypass)
                    )

                    # [v22.3] Filtro Anti-Lateralidade (Anti-Sideways)
                    if v22_buy or v22_sell:
                        # [SOTA V22.5.1] Sincronização Absoluta de Parâmetros
                        is_sideways, s_reason = self.risk.is_sideways_market(
                            adx=data.loc[row.name, "adx"],
                            bb_upper=upper_bb,
                            bb_lower=lower_bb,
                            atr=atr_current,
                        )
                        if is_sideways:
                            logging.info(
                                f"[VETO LATERALIDADE] {row.name} | Motivo: {s_reason} | Sinal Abortado."
                            )
                            self._shadow_veto(s_reason, row.name)
                            v22_buy = False
                            v22_sell = False

                    # [AUTORIZADO 03/03/2026] GATE TÉCNICO DE VENDA (sem exigir ai_dir=="VENDA")
                    # Quando RSI+BB+Vol confirmam sobrecompra E IA não contradiz (score < 60):
                    # executa VENDA com lote conservador (0.5 contratos).
                    # Isso captura reversões intraday onde o PatchTST (tendencialista) ainda não detectou o topo.
                    # [REC.2 - 03/03/2026] FILTRO DE VOLATILIDADE ATR NO GATE DE VENDA
                    # ATR M1 do WIN$ em dias normais: 40-80pts/candle
                    # ATR M1 em dias voláteis (como 03/03 Δ=4490pts): 100-180pts/candle
                    # Limiar 100pts = proxy confiável para dias de alta volatilidade
                    atr_ok_pra_venda = (
                        atr_current <= 100.0
                    )  # [REC.2] Bloqueia VENDA gate técnico em dias voláteis
                    ia_nao_contradiz_venda = (ai_score < 65.0) and (
                        ai_dir != "COMPRA"
                    )  # [MELHORIA D]
                    v22_sell_technical = (
                        v22_sell_raw
                        and ia_nao_contradiz_venda
                        and atr_ok_pra_venda  # [REC.2] Filtro de volatilidade
                        and not v22_sell  # Só ativa se o gate principal NÃO ativou
                        and cooldown_ok
                        and not bias_veto_sell
                    )

                    # [V50.1] Rastreamento de Vetos de IA (Shadow)
                    if (
                        ai_dir == "WAIT"
                        or ai_stability < self.opt_params["confidence_threshold"]
                    ):
                        if v22_buy_raw or v22_sell_raw:
                            self.shadow_signals["filtered_by_ai"] += 1
                            reason = ai_decision.get("reason", "LOW_CONFIDENCE")
                            self._shadow_veto(reason, row.name)
                    if v22_buy_raw and not v22_buy:
                        self.shadow_signals["buy_vetos_ai"] = (
                            self.shadow_signals.get("buy_vetos_ai", 0) + 1
                        )
                    if v22_sell_raw and not v22_sell:
                        self.shadow_signals["sell_vetos_ai"] = (
                            self.shadow_signals.get("sell_vetos_ai", 0) + 1
                        )

                    quantile_confidence = ai_decision.get(
                        "quantile_confidence", "NORMAL"
                    )
                    regime_tag = f"SOTA_SNIPER_{ai_dir}"

                    # [v24.2] ALVOS DINÂMICOS (SL/TP Multiplier)
                    sl_multiplier = ai_decision.get("sl_multiplier", 1.0)
                    tp_multiplier = ai_decision.get("tp_multiplier", 1.0)

                    dyn_sl = self.opt_params["sl_dist"] * sl_multiplier
                    dyn_tp = self.opt_params["tp_dist"] * tp_multiplier
                    use_partial_flag = ai_decision.get("use_partial", True)

                    # [MELHORIA-B] SL Dinâmico por ATR.
                    # Adapta o stop à volatilidade real: menor em dias tranquilos, maior em dias voláteis.
                    # v24_locked_params.json (sl_dist: 150) permanece como fallback para o multiplicador da IA.
                    # Fórmula: max(80pts, min(200pts, ATR_atual × 1.2))
                    if use_ai_core:
                        _atr_sl_b = max(80.0, min(200.0, atr_current * 1.2))
                        dyn_sl = _atr_sl_b * sl_multiplier
                        logging.debug(
                            f"[MELHORIA-B SL-ATR] ATR={atr_current:.1f} → "
                            f"SL Dinâmico={dyn_sl:.1f} pts (sl_dist base: {self.opt_params['sl_dist']})"
                        )

                    # [MELHORIA-D] TP Expansivo em Tendência Forte.
                    # Quando ADX > 30 + H1 confirma direção, expande TP em +50% (cap 800pts)
                    # para capturar movimentos extensos que o TP fixo de 400pts desperdiçava.
                    # v24_locked_params.json (tp_dist: 400) permanece como base — multiplicador
                    # adicional é aplicado condicionalmente (somente em tendência forte detectada).
                    _h1_tp_d = getattr(self.ai, "h1_trend", 0) if use_ai_core else 0
                    _adx_tp_d = 0.0
                    try:
                        _adx_tp_d = float(data.loc[row.name, "adx"])
                    except Exception:
                        pass
                    if use_ai_core and _adx_tp_d > 30 and _h1_tp_d != 0:
                        _base_tp_d = self.opt_params["tp_dist"] * tp_multiplier
                        dyn_tp = min(800.0, _base_tp_d * 1.5)
                        logging.info(
                            f"[MELHORIA-D TP+] ADX={_adx_tp_d:.1f} H1={_h1_tp_d} → "
                            f"TP Expandido: {_base_tp_d:.0f} → {dyn_tp:.0f} pts"
                        )

                    # Ajustes de alvos por regime (Compatibilidade com Phase 13)
                    # [v24.2] Respeitar os multiplicadores da IA sem limites legados de 200pts
                    pass

                    # Log de auditoria interna
                    if v22_buy or v22_sell:
                        logging.debug(f"🤖 Decisão da IA: {ai_decision}")
                        vol_spike_eff = vol_spike  # No modo IA usamos volume puro
                        ai_stability = (
                            ai_decision.get("score", 50.0) / 100.0
                        )  # [SOTA v25.4] Usa score real para o filtro de confianca do auditor

                # --- [LEGACY] INTELIGÊNCIA DO SUCESSO: REGIME MAESTRO & ADAPTAÇÃO DE SCALPING ---
                else:
                    dir_prob = row["dir_prob"]
                    aggressive = self.opt_params.get("aggressive_mode", False)
                    v_mult_eff = (
                        v_mult * 0.8 if aggressive else v_mult
                    )  # Reduce volume spike req by 20%

                    # Sinais V22 (Estratégia de Reversão de Volatilidade - Mean Reversion)
                    cond_rsi_buy = rsi < 30
                    cond_bb_buy = row["close"] < lower_bb
                    cond_rsi_sell = rsi > 70
                    cond_bb_sell = row["close"] > upper_bb

                    # [SOTA v23] FLUXO ADAPTATIVO: Se ATR > 200, reduz threshold para 1.05
                    current_flux_thresh = self.opt_params["flux_imbalance_threshold"]
                    if (
                        self.opt_params.get("adaptive_flux_active", False)
                        and atr_current > 200
                    ):
                        current_flux_thresh = 1.05

                    cond_vol_buy = row["tick_volume"] > vol_sma * current_flux_thresh
                    cond_vol_sell = row["tick_volume"] > vol_sma * current_flux_thresh

                    v22_reversion_buy = cond_rsi_buy and cond_bb_buy and cond_vol_buy
                    v22_reversion_sell = (
                        cond_rsi_sell and cond_bb_sell and cond_vol_sell
                    )

                    # 1. Regime Maestro (Trend Routing)
                    v22_trend_buy = v22_trend_sell = False
                    if dir_prob >= 0.8 and current_regime == 1:  # Trend Mode
                        v22_trend_buy = (
                            (row["close"] > mid_bb)
                            and (rsi > 50)
                            and (rsi < 70)
                            and vol_spike_eff
                        )
                        v22_trend_sell = (
                            (row["close"] < mid_bb)
                            and (rsi < 50)
                            and (rsi > 30)
                            and vol_spike_eff
                        )
                        dyn_sl = self.opt_params["sl_dist"] * 1.5
                        dyn_tp = self.opt_params["tp_dist"] * 2.0
                        regime_tag = "TREND_MAESTRO"

                    # 2. Amorphous Regimes (Scalping Adaptation)
                    v22_scalp_buy = v22_scalp_sell = False
                    if current_regime == 2:  # Noise Mode
                        rsi_buy_thresh = (
                            35 if aggressive else 25
                        )  # Loosened for relaxed analysis
                        rsi_sell_thresh = 65 if aggressive else 75
                        v22_scalp_buy = (
                            (row["close"] < lower_bb)
                            and (rsi < rsi_buy_thresh)
                            and (lower_wick > body * 0.4)
                            and vol_spike_eff
                        )
                        v22_scalp_sell = (
                            (row["close"] > upper_bb)
                            and (rsi > rsi_sell_thresh)
                            and (upper_wick > body * 0.4)
                            and vol_spike_eff
                        )
                        dyn_sl = self.opt_params["sl_dist"] * 0.5
                        dyn_tp = (
                            100.0
                            if "WIN" in self.symbol
                            else self.opt_params["tp_dist"] * 0.5
                        )
                        regime_tag = "NOISE_SCALP"

                    elif current_regime == 3 or True:  # Consolidation / Default Mode
                        rsi_buy_thresh = 35 if aggressive else 25
                        rsi_sell_thresh = 65 if aggressive else 75
                        v22_scalp_buy = (
                            (row["close"] < lower_bb)
                            and (rsi < rsi_buy_thresh)
                            and (lower_wick > body * 0.4)
                            and vol_spike_eff
                        )
                        v22_scalp_sell = (
                            (row["close"] > upper_bb)
                            and (rsi > rsi_sell_thresh)
                            and (upper_wick > body * 0.4)
                            and vol_spike_eff
                        )
                        dyn_sl = self.opt_params["sl_dist"]
                        dyn_tp = (
                            100.0
                            if "WIN" in self.symbol
                            else self.opt_params["tp_dist"] * 0.5
                        )
                        regime_tag = "CONSOL_SCALP"

                    v22_buy = v22_reversion_buy or v22_trend_buy or v22_scalp_buy
                    v22_sell = v22_reversion_sell or v22_trend_sell or v22_scalp_sell

                    ai_stability = min(0.99, 0.70)  # Placeholder para fluxo legado

                # [PHASE 2] Audit Tracking Sync: Contamos candidatos v22 independentemente do modo
                # Isso permite ver no relatório de auditoria quantos sinais a IA vetou.
                if (rsi < 30 and row["close"] < lower_bb) or (
                    rsi > 70 and row["close"] > upper_bb
                ):
                    self.shadow_signals["v22_candidates"] += 1

                # Filtros Operacionais
                t_start = datetime.strptime(
                    self.opt_params["start_time"], "%H:%M"
                ).time()
                t_end = datetime.strptime(self.opt_params["end_time"], "%H:%M").time()
                time_ok = t_start <= row.name.time() <= t_end

                # [v23] Sincronia de Produção: Abertura Flexível (09:00-09:10 liberado se for Momentum ou via Expert)
                is_opening_flex = row.name.hour == 9 and row.name.minute < 10
                if is_opening_flex and not is_momentum_bypass:
                    # Se não for momentum bypass, mantemos o bloqueio legacy ou habilitamos via flag
                    time_ok = self.opt_params.get("allow_flex_opening", True)
                else:
                    time_ok = t_start <= row.name.time() <= t_end

                # [AGRESSIVO] Limite de 60% de perda diária
                limit_loss = self.initial_balance * 0.60
                risk_ok = self.daily_pnl > -limit_loss

                # Ignora limite numérico de trades no modo agressivo
                limit_ok = True
                # [v22.5] FILTRO DE INÉRCIA VOLÁTIL
                # Impede operação se o mercado estiver muito parado (evita ruído)
                min_atr = self.opt_params.get("min_atr_threshold", 50.0)
                vol_min = max(20.0, min_atr) if "WIN" in self.symbol else 1.5
                vol_max = 400 if "WIN" in self.symbol else 30.0
                vol_stable = vol_min < atr_current < vol_max

                if not vol_stable and atr_current < vol_min:
                    self._shadow_veto("INERCIA_VOLATIL", row.name)

                # AI Filter (SOTA Stability)
                # Se estiver usando AI Core, respeitamos a decisão e estabilidade real do modelo
                if not use_ai_core:
                    # No modo legado, simulamos a confiança da IA com base no RSI e Volume (Proxy)
                    # Isso evita que o modo legado seja "perfeito" demais sem filtros.
                    test_side = "buy" if v22_buy else ("sell" if v22_sell else None)
                    base_confidence = 0.70
                    if vol_spike_eff:
                        base_confidence += 0.15
                    if (test_side == "buy" and rsi < 25) or (
                        test_side == "sell" and rsi > 75
                    ):
                        base_confidence += 0.10
                    ai_stability = min(0.99, base_confidence)

                # [v22.5] RIGOR DIRECIONAL DINÂMICO
                # Aumenta exigência de confiança se contra a tendência primária (EMA 90)
                # target_conf = Base (0.35) * Rigor (1.0 ou 2.0)
                current_ema90 = row["ema90"]  # Disponível no dataframe de backtest
                current_price = row["close"]

                # Determinamos o rigor com base na direção pretendida
                potential_side = (
                    "buy" if v22_buy else ("sell" if v22_sell else "neutral")
                )
                rigor_mult = self.risk.get_directional_rigor(
                    potential_side, current_ema90, current_price
                )

                effective_conf_threshold = (
                    self.opt_params["confidence_threshold"] * rigor_mult
                )
                ai_filter_ok = (
                    ai_stability >= effective_conf_threshold
                ) or is_momentum_bypass

                if (
                    not ai_filter_ok
                    and ai_stability >= self.opt_params["confidence_threshold"]
                ):
                    self._shadow_veto("RIGOR_DIRECIONAL", row.name)

                # Sentiment Filter (V2.5) — [MELHORIA-A] Threshold ajustado de ±0.5 para ±0.3
                # Alinhado com o is_direction_allowed() do RiskManager para consistência total.
                sentiment_ok = True
                if self.sentiment_stream and row.name in self.sentiment_stream:
                    score = self.sentiment_stream[row.name]
                    if (v22_buy and score < -0.3) or (v22_sell and score > 0.3):
                        sentiment_ok = False

                # Flux Filter (Proxy para Backtest CSV)
                flux_ok = True
                if not use_ai_core and self.opt_params.get("use_flux_filter", False):
                    flux_ok = row["tick_volume"] > (
                        vol_sma * self.opt_params.get("flux_imbalance_threshold", 1.2)
                    )

                # Tracking Detalhado de Oportunidades Perdidas
                if v22_buy or v22_sell:
                    if not time_ok:
                        self.shadow_signals["component_fail"]["time"] = (
                            self.shadow_signals["component_fail"].get("time", 0) + 1
                        )
                    if not vol_stable:
                        self.shadow_signals["component_fail"]["vol_stable"] = (
                            self.shadow_signals["component_fail"].get("vol_stable", 0)
                            + 1
                        )
                    if not cooldown_ok:
                        self.shadow_signals["component_fail"]["cooldown"] = (
                            self.shadow_signals["component_fail"].get("cooldown", 0) + 1
                        )

                    if not ai_filter_ok:
                        self.shadow_signals["total_missed"] += 1
                        self.shadow_signals["filtered_by_ai"] += 1
                        if 0.70 <= ai_stability < 0.75:
                            self.shadow_signals["tiers"]["70-75"] += 1
                        elif 0.75 <= ai_stability < 0.80:
                            self.shadow_signals["tiers"]["75-80"] += 1
                        elif 0.80 <= ai_stability < 0.85:
                            self.shadow_signals["tiers"]["80-85"] += 1

                    elif not flux_ok:
                        self.shadow_signals["total_missed"] += 1
                        self.shadow_signals["filtered_by_flux"] += 1

                    elif not sentiment_ok:
                        self.shadow_signals["total_missed"] += 1
                        # self.shadow_signals['filtered_by_sentiment'] = ...

                # 3. Executar Entrada se todos os filtros conferem
                if (
                    (v22_buy or v22_sell or v22_sell_technical)
                    and time_ok
                    and risk_ok
                    and ai_filter_ok
                    and sentiment_ok
                    and flux_ok
                ):
                    side = (
                        "buy" if v22_buy else ("sell" if v22_sell else "sell")
                    )  # Default to sell if v22_sell_technical is true

                    # [MELHORIA H - V28] Veto de direção por tendência diária
                    if side == "buy" and bias_veto_buy:
                        self.shadow_signals["total_missed"] = (
                            self.shadow_signals.get("total_missed", 0) + 1
                        )
                        self.shadow_signals["filtered_by_bias"] = (
                            self.shadow_signals.get("filtered_by_bias", 0) + 1
                        )
                        self._shadow_veto("BIAS_BUY_VETADO", row.name)
                        logging.debug(
                            f"[VETO] [H] BUY vetado por tendência diária de BAIXA em {row.name}"
                        )
                        continue
                    if side == "sell" and bias_veto_sell:
                        self.shadow_signals["total_missed"] = (
                            self.shadow_signals.get("total_missed", 0) + 1
                        )
                        self.shadow_signals["filtered_by_bias"] = (
                            self.shadow_signals.get("filtered_by_bias", 0) + 1
                        )
                        self._shadow_veto("BIAS_SELL_VETADO", row.name)
                        logging.debug(
                            f"[VETO] [H] SELL vetado por tendência diária de ALTA em {row.name}"
                        )
                        continue

                    # [v23] Solicita parâmetros ao RiskManager (já ajustados para abertura/momentum)
                    import MetaTrader5 as mt5

                    params = self.risk.get_order_params(
                        self.symbol,
                        (mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL),
                        row["close"],
                        self.opt_params["base_lot"],
                        current_atr=atr_current,
                        regime=current_regime,
                        tp_multiplier=float(
                            ai_decision.get("tp_multiplier", 1.0).iloc[0]
                        )
                        if isinstance(
                            ai_decision.get("tp_multiplier"), (pd.Series, pd.DataFrame)
                        )
                        else float(ai_decision.get("tp_multiplier", 1.0)),
                        sl_multiplier=float(
                            ai_decision.get("sl_multiplier", 1.0).iloc[0]
                        )
                        if isinstance(
                            ai_decision.get("sl_multiplier"), (pd.Series, pd.DataFrame)
                        )
                        else float(ai_decision.get("sl_multiplier", 1.0)),
                        current_time=row.name.time(),
                    )

                    self.position = {
                        "side": side,
                        "entry_price": row["close"],
                        "sl": params["sl"],
                        "tp": params["tp"],
                        "lots": params["volume"],
                        "index": i,
                        "time": row.name,
                        "tp_multiplier": tp_multiplier,
                        "quantile_confidence": quantile_confidence
                        if "quantile_confidence" in locals()
                        else "NORMAL",
                        "execution_mode": ai_decision.get("execution_mode", "LIMIT")
                        if "ai_decision" in locals()
                        else "LIMIT",
                    }
                    self.daily_trade_count += 1
                    # [MELHORIA H - 03/03/2026] Rastreia cooldown por direção
                    if side == "buy":
                        self._last_buy_time = row.name
                    else:
                        self._last_sell_time = row.name
                    self.last_trade_time = row.name
                    logging.info(
                        f"GATILHO V22 [{regime_tag}]: {side} @ {row['close']} | Lotes: {params['volume']}"
                    )
                    continue

                # [AUTORIZADO 03/03/2026] GATE TÉCNICO DE VENDA CONSERVADOR
                # Executa venda somente se gate técnico ativo E posição não aberta
                elif (
                    use_ai_core
                    and v22_sell_technical
                    and time_ok
                    and risk_ok
                    and limit_ok
                    and vol_stable
                    and not self.position
                ):
                    # [REC.3 - 03/03/2026] SL ADAPTATIVO: mais espaço em mercados voláteis
                    # ATR M1 WIN$ normal: 40-80pts | volátil: 100-180pts
                    # Limiar 70pts (ATR M1): distingue dia normal de dia agitado
                    multiplicador_sl = 1.5 if atr_current > 70 else 1.3
                    atr_sl = (
                        max(150.0, min(400.0, atr_current * multiplicador_sl))
                        if atr_current > 0
                        else 200.0
                    )
                    tech_sl_pts = atr_sl
                    tech_tp_pts = 250.0 if atr_current > 90 else 400.0
                    sl_tech = row["close"] + tech_sl_pts
                    tp_tech = row["close"] - tech_tp_pts

                    # [v24.3] Cálculo de Lote Dinâmico com Escalonamento
                    base_lots = self.opt_params.get("force_lots", 1)
                    if getattr(self, "_reduced_lot_mode", False):
                        # Reduz o lote para o fator configurado (ex: 50%), mínimo 1 contrato
                        final_lot = max(
                            1,
                            int(
                                base_lots
                                * self.opt_params.get("reduced_lot_factor", 0.5)
                            ),
                        )
                    else:
                        final_lot = base_lots

                    self.position = {
                        "side": "sell",
                        "entry_price": row["close"],
                        "sl": sl_tech,
                        "tp": tp_tech,
                        "lots": final_lot,  # Changed from tech_lot to final_lot
                        "index": i,
                        "time": row.name,
                        "quantile_confidence": "NORMAL",
                        "execution_mode": "TECH_GATE",  # Identificador do gate técnico
                    }
                    self.daily_trade_count += 1
                    self.last_trade_time = row.name
                    # [MELHORIA H - 03/03/2026] Cooldown independente para VENDA gate técnico
                    self._last_sell_time = (
                        row.name
                    )  # Rastreia último trade de venda separadamente
                    logging.info(
                        f"📉 [GATE TÉCNICO] VENDA @ {row['close']} | RSI={rsi:.1f} | Score_IA={ai_score:.1f} | TP={tech_tp_pts}pts | SL={tech_sl_pts:.0f}pts (ATR={atr_current:.0f})"
                    )

            # Atualizar Drawdown
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance
            current_dd = (
                (self.peak_balance - self.balance) / self.peak_balance
                if self.peak_balance > 0
                else 0
            )
            if current_dd > self.max_drawdown:
                self.max_drawdown = current_dd

            self.equity_curve.append(self.balance)
            self.timestamps.append(row.name)

        logging.info("Simulacao concluida.")
        if self.position:
            # Força o fechamento da última posição para fins de relatório final no backtest
            self._close_trade(row["close"], "END_OF_SIM", row.name)
        return self.generate_report()

    def _close_trade(self, price, reason, exit_time):
        if not self.position:
            return
        pos = self.position
        pnl_points = (
            (price - pos["entry_price"])
            if pos["side"] == "buy"
            else (pos["entry_price"] - price)
        )

        # Cálculo financeiro (Simplificado: WIN=0.20/pt, WDO=10.00/pt)
        mult = 0.20 if "WIN" in self.symbol else 10.0
        pnl_fin = pnl_points * pos["lots"] * mult

        # Auditoria Financeira
        self.balance += pnl_fin
        self.daily_pnl += pnl_fin

        # Registrar Trade
        trade_data = {
            "entry_time": pos["time"],
            "exit_time": exit_time,
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": price,
            "lots": pos["lots"],
            "pnl_pts": pnl_points,
            "pnl_fin": pnl_fin,
            "reason": reason,
            "quantile_confidence": pos.get("quantile_confidence", "NORMAL"),
            "execution_mode": pos.get("execution_mode", "LIMIT"),
        }
        self.trades.append(trade_data)

        # [v27] Sincronizar Resultado com Meta-Learner / Quarter-Kelly
        self.ai.record_result(pnl_fin)

        # Atualiza métricas de lote dinâmico tracker
        if pnl_fin > 0:
            self.consecutive_wins += 1
        else:
            self.consecutive_wins = 0

        self.position = None
        self.last_trade_time = exit_time  # Garante cooldown no backtest

    def generate_report(self):
        df_trades = pd.DataFrame(self.trades)
        if df_trades.empty:
            logging.warning("Nenhum trade realizado no período.")
            return {
                "final_balance": self.balance,
                "total_pnl": 0.0,
                "trades": [],
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": self.max_drawdown * 100,
                "shadow_signals": self.shadow_signals,
            }

        # Métricas
        win_rate = (len(df_trades[df_trades["pnl_fin"] > 0]) / len(df_trades)) * 100
        total_pnl = df_trades["pnl_fin"].sum()
        profit_factor = (
            abs(
                df_trades[df_trades["pnl_fin"] > 0]["pnl_fin"].sum()
                / df_trades[df_trades["pnl_fin"] < 0]["pnl_fin"].sum()
            )
            if any(df_trades["pnl_fin"] < 0)
            else float("inf")
        )

        # Gráficos com Plotly
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=("Curva de Equity", "Distribuição de PnL por Trade"),
        )

        # Equity
        fig.add_trace(
            go.Scatter(x=self.timestamps, y=self.equity_curve[1:], name="Capital"),
            row=1,
            col=1,
        )

        # PnL Hist
        fig.add_trace(
            go.Bar(x=df_trades.index, y=df_trades["pnl_fin"], name="PnL por Trade"),
            row=2,
            col=1,
        )

        fig.update_layout(
            height=800, title_text=f"Relatório Backtest AlphaX - {self.symbol}"
        )

        report_path = "backend/backtest_report.html"
        fig.write_html(report_path)

        print("\n" + "=" * 50)
        print(f"RELATORIO DO PASSADO ({self.symbol})")
        print("=" * 50)
        print(f"Saldo Inicial: R$ {self.initial_balance:.2f}")
        print(f"Saldo Final:   R$ {self.balance:.2f}")
        print(f"Lucro Líquido: R$ {total_pnl:.2f}")
        print(f"Total Trades:  {len(df_trades)}")
        print(f"Win Rate:      {win_rate:.1f}%")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Max Drawdown:  {self.max_drawdown * 100:.2f}%")
        print(f"\nRelatório Visual salvo em: {report_path}")
        print("=" * 50)

        return {
            "final_balance": self.balance,
            "total_pnl": total_pnl,
            "trades": df_trades.to_dict("records"),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": self.max_drawdown * 100,
            "shadow_signals": self.shadow_signals,  # Exporta oportunidades perdidas
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, default="WIN$")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--rsi_period", type=int, default=9)
    parser.add_argument("--bb_dev", type=float, default=2.0)
    parser.add_argument("--vol_spike_mult", type=float, default=1.5)
    parser.add_argument("--sl_dist", type=float, default=130.0)
    parser.add_argument("--tp_dist", type=float, default=260.0)

    args = parser.parse_args()

    # Filtra apenas os argumentos que pertencem aos opt_params ou ao init
    backtester = BacktestPro(
        symbol=args.symbol,
        n_candles=args.n,
        rsi_period=args.rsi_period,
        bb_dev=args.bb_dev,
        vol_spike_mult=args.vol_spike_mult,
        sl_dist=args.sl_dist,
        tp_dist=args.tp_dist,
    )
    asyncio.run(backtester.run())
