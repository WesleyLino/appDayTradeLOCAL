import os
import logging
import numpy as np
import asyncio
import torch
import torch.nn as nn
import onnxruntime as ort
import gc
import time
from backend.models import PatchTST

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class InferenceEngine:
    """
    [AMD OPTIMIZED] Motor de inferência híbrido.
    Prioriza ONNX Runtime para aceleração na GPU AMD.
    """
    def __init__(self, model_path=None):
        self.model_path = model_path or "backend/models/sota_model_win.pth"
        self.ort_session = None
        self.model = None
        self.use_onnx = False
        self._load_engine()

    def _load_engine(self):
        try:
            # Desativado temporariamente para auditoria de estabilidade
            # onnx_path = self.model_path.replace(".pth", ".onnx")
            # if os.path.exists(onnx_path):
            #     providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
            #     self.ort_session = ort.InferenceSession(onnx_path, providers=providers)
            #     self.use_onnx = True
            #     logging.info(f"--- [v22.5.7] ONNX Engine Ativo (AMD Accelerated)")
            #     return

            # Fallback para PyTorch
            if os.path.exists(self.model_path):
                # O SOTA usa 5 canais e 3 quantis
                self.model = PatchTST(c_in=5, context_window=60, target_window=5, d_model=128, n_heads=4, n_layers=3)
                state_dict = torch.load(self.model_path, map_location='cpu')
                self.model.load_state_dict(state_dict)
                self.model.eval()
                logging.info(f"--- [v22.5.7] PyTorch Engine Ativo (CPU Fallback)")
        except Exception as e:
            logging.error(f"Erro ao carregar InferenceEngine: {e}")

    async def predict(self, dataframe):
        """Interface pública assíncrona."""
        if dataframe is None or len(dataframe) < 60:
            return self._neutral_output()
        return await asyncio.to_thread(self._predict_sync, dataframe)

    def _predict_sync(self, dataframe):
        try:
            # Seleção de colunas para o modelo SOTA (5 canais standard ou OHLCV)
            cols = ['open', 'high', 'low', 'close', 'tick_volume']
            if not all(c in dataframe.columns for c in cols):
                return self._neutral_output()

            input_data = dataframe[cols].values[-60:].astype(np.float32)
            input_tensor = np.expand_dims(input_data, axis=0) # [1, 60, 5]

            if self.use_onnx and self.ort_session:
                input_name = self.ort_session.get_inputs()[0].name
                preds = self.ort_session.run(None, {input_name: input_tensor})[0]
            elif self.model:
                with torch.no_grad():
                    # PatchTST retorna [batch, target, quantiles] -> pegamos q50 (índice 1)
                    preds = self.model(torch.tensor(input_tensor)).numpy()[0]
            else:
                return self._neutral_output()

            # Extração de Score (Inclinacão da predição central q50)
            if preds.ndim == 2:
                q50_path = preds[:, 1]
                f_delta = float(q50_path[-1])
            else:
                f_delta = float(preds) if np.isscalar(preds) else float(preds[0])
            
            # Score de 0.0 a 1.0 (0.5 é neutro)
            final_score = max(0.0, min(1.0, 0.5 + (f_delta / 2.0)))
            
            return {
                "score": float(final_score),
                "forecast_norm": float(f_delta),
                "confidence": 0.85 + (abs(f_delta) * 0.1),
                "q10": float(preds[-1, 0]) if preds.ndim == 2 else 0.0,
                "q50": float(preds[-1, 1]) if preds.ndim == 2 else 0.0,
                "q90": float(preds[-1, 2]) if preds.ndim == 2 else 0.0
            }
        except Exception as e:
            logging.error(f"Erro na inferência: {e}")
            return self._neutral_output()

    def _neutral_output(self):
        return {"score": 0.5, "forecast_norm": 0.0, "confidence": 0.0, "q50": 0.0}

class AICore:
    """
    [SOTA v22.5.7] Núcleo de Inteligência para WIN$ e WDO$.
    """
    def __init__(self):
        self.inference_engine = InferenceEngine()
        self.obi_ema = 0.0
        self.ia_cooldown_until = 0
        self.sentiment_anchor = 0.0
        self.price_history = []
        self.h1_trend = 0
        self.micro_analyzer = self # Alias para compatibilidade
        self.opening_rigor_enabled = True
        self.latest_sentiment_score = 0.0
        # [SOTA V22 GOLDEN] Thresholds dinâmicos (Sincronizados via SniperBot)
        self.confidence_buy_threshold = 65.0
        self.confidence_sell_threshold = 35.0
        self.uncertainty_threshold = 0.4
        self.consecutive_losses = 0 # [SOTA v24] Contador para cooldown dinâmico
        self.vwap_dist_threshold = 400.0 # [v24.2] Default de segurança

    async def predict_with_patchtst(self, engine, data):
        """Método de interface para o BacktestPro."""
        if engine is None: return {"score": 50.0}
        res = await engine.predict(data)
        # Converte score 0-1 para 0-100 para o backtester
        res['score'] = res.get('score', 0.5) * 100.0
        return res

    def update_h1_trend(self, h1_data):
        if h1_data is None or len(h1_data) < 2:
            self.h1_trend = 0
            return
        last_close = h1_data['close'].iloc[-1]
        ma20 = h1_data['close'].rolling(20).mean().iloc[-1] if len(h1_data) >= 20 else last_close
        if last_close > ma20 * 1.002: self.h1_trend = 1
        elif last_close < ma20 * 0.998: self.h1_trend = -1
        else: self.h1_trend = 0

    def identify_market_regime(self, df, h1_trend, atr, adx, bb_up, bb_down, bb_mid):
        """
        [SOTA v23] Classificador de Regime Híbrido.
        Retorna: 1 (Trending), 0 (Sideways), 2 (Volatile)
        """
        try:
            if df is None or len(df) < 5: return 0
            
            # 1. Detecção de Momentum (Aceleração de Preço e Volume)
            last_candles = df.tail(5)
            price_change = abs(last_candles['close'].iloc[-1] - last_candles['close'].iloc[0])
            avg_vol = last_candles['tick_volume'].mean()
            prev_vol = df['tick_volume'].tail(20).head(15).mean()
            
            # Se o preço андou mais que 1.5x o ATR e volume subiu 30% em 5 min
            if price_change > (atr * 1.5) and avg_vol > (prev_vol * 1.3):
                return 1 # Trending / Breakout
            
            # 2. Detecção de Volatilidade Excessiva (Riscos)
            if atr > 250 or adx > 45:
                return 2 # Volatile
                
            # 3. Detecção de Lateralidade (Choppy)
            bb_width = (bb_up - bb_down)
            if bb_width < (atr * 2.0) and adx < 20:
                return 0 # Sideways
                
            return 0 # Default para Sideways (Segurança)
        except Exception as e:
            logging.error(f"Erro identify_market_regime: {e}")
            return 0

    def calculate_decision(self, obi=0.0, sentiment=0.0, patchtst_score=50.0, regime=0, **kwargs):
        """
        [SOTA v23] Lógica de decisão Evoluída.
        Suporta Modo MOMENTUM (Bypass de Indicadores) para Score > 85%.
        """
        if isinstance(patchtst_score, dict):
            score_raw = float(patchtst_score.get("score", 0.5))
            confidence = float(patchtst_score.get("confidence", 0.0))
        else:
            score_raw = float(patchtst_score)
            confidence = 0.0
        
        if score_raw <= 1.0:
            score_raw *= 100.0
        
        # [v24] Volume-Weighted Score Bonus
        vol_bonus = 0.0
        avg_vol_20 = float(kwargs.get('avg_vol_20', 0.0))
        current_vol = float(kwargs.get('current_vol', 0.0))
        if avg_vol_20 > 0 and current_vol > (avg_vol_20 * 2.0):
            vol_bonus = 5.0
            score_raw = float(min(100.0, score_raw + vol_bonus))
            logging.info(f"[v24 VOLUME-BOOST] +5 pts aplicados. Volume={current_vol:.0f} > 2x Media={avg_vol_20:.0f}")

        direction = "NEUTRAL"
        exec_strategy = "PASSIVA"
        
        # [v24.1] Janela de Ouro (Time-of-Day Alpha) 10:15-11:15
        # Período de alta liquidez B3 + NY. Se Volume > 1.5x Média, relaxamos o threshold.
        hour = kwargs.get('hour', 0)
        minute = kwargs.get('minute', 0)
        is_golden_window = False
        momentum_threshold = 85.0 # [v24.1] Fallback Seguro

        if (hour == 10 and minute >= 15) or (hour == 11 and minute <= 15):
             if current_vol > (avg_vol_20 * 1.5):
                is_golden_window = True
                momentum_threshold = 75.0 # [v24.1] Destrava operações de momentum institutional
                logging.info(f"[v24.1 GOLDEN-WINDOW] Ativo! Threshold reduzido p/ 75% | Vol: {current_vol:.0f}")

        # [v24.1] Elastic Momentum Bypass (Score >= 84% + OBI 2.0x)
        obi_abs = abs(obi)
        if not is_golden_window:
            if score_raw >= 84.0 or score_raw <= 16.0:
                if obi_abs >= 2.0: # Reduzido de 2.5x para 2.0x (Sweet Spot)
                    momentum_threshold = 84.0
                    logging.info(f"[v24.1 ELASTIC-BYPASS] Threshold reduzido para 84% devido ao OBI {obi_abs:.2f}")

        is_momentum_bypass = False
        if score_raw >= momentum_threshold or score_raw <= (100.0 - momentum_threshold):
            is_momentum_bypass = True
            exec_strategy = "MOMENTUM"
            direction = "COMPRA" if score_raw >= momentum_threshold else "VENDA"

        # Lógica Sniper Padrão (Se não houver bypass)
        if not is_momentum_bypass:
            if score_raw >= self.confidence_buy_threshold:
                direction = "COMPRA"
            elif score_raw <= self.confidence_sell_threshold:
                direction = "VENDA"
            
            exec_strategy = "SNIPER" if direction != "NEUTRAL" else "PASSIVA"

        # [v24.2] GATILHOS ASSIMÉTRICOS (RSI DINÂMICO) POR REGIME
        # Se regime for Tendência (1), relaxamos o RSI para capturar ralis institucionais
        if regime == 1:
            rsi_buy_trigger = 38.0
            rsi_sell_trigger = 62.0
            logging.info(f"[v24.2 TREND-RSI] Gatilhos relaxados: Buy=38, Sell=62 | Regime={regime}")
        else:
            rsi_buy_trigger = 32.0 # Default SOTA v22
            rsi_sell_trigger = 68.0

        # [v24.2] FLEXIBILIZAÇÃO VWAP (OBI BOOST)
        # Se houver forte desequilíbrio no book (OBI > 3.0), permitimos maior distância da VWAP.
        vwap = kwargs.get('vwap')
        current_price = kwargs.get('current_price')
        vwap_veto = False
        
        if vwap is not None and current_price is not None:
            dist_vwap = abs(current_price - vwap)
            limit_eff = self.vwap_dist_threshold
            
            # OBI Boost: Dobra o limite se o fluxo for massivo
            if abs(obi) >= 3.0:
                limit_eff *= 2.0
                logging.info(f"[v24.2 VWAP-FLEX] OBI={obi:.1f} massivo. Limite VWAP expandido para {limit_eff:.0f}")
            
            if dist_vwap > limit_eff:
                vwap_veto = True
                logging.info(f"[v24.2 VWAP-VETO] Preço muito distante ({dist_vwap:.0f} > {limit_eff:.0f}). Veto aplicado.")

        # Vetos de Segurança (Mesmo no Momentum, mantemos vetos de incerteza e VWAP)
        uncertainty = patchtst_score.get("uncertainty_norm", 0.0) if isinstance(patchtst_score, dict) else 0.0
        veto_reason = None
        
        if uncertainty > self.uncertainty_threshold:
            veto_reason = "UNCERTAINTY"
        elif vwap_veto:
            veto_reason = "VWAP_DISTANT"
            
        if veto_reason:
            direction = "WAIT" # [v24.2] Retorna WAIT para logar reason no BacktestPro
            exec_strategy = "PASSIVA"
        
        return {
            "score": float(score_raw),
            "direction": direction,
            "execution_strategy": exec_strategy,
            "is_momentum_bypass": is_momentum_bypass,
            "lot_multiplier": 1.0,
            "tp_multiplier": 1.5 if exec_strategy == "MOMENTUM" else 1.0,
            "veto": veto_reason,
            "reason": veto_reason, # [v24.2] Sincronia com auditoria do BacktestPro
            "h1_trend": self.h1_trend,
            "quantile_confidence": "HIGH" if is_momentum_bypass else "NORMAL",
            "rsi_buy_trigger": rsi_buy_trigger,
            "rsi_sell_trigger": rsi_sell_trigger
        }

    def update_sentiment_anchor(self, price):
        self.price_history.append(price)
        if self.sentiment_anchor == 0: 
            self.sentiment_anchor = price
        else: 
            self.sentiment_anchor = 0.999 * self.sentiment_anchor + 0.001 * price

    def update_microstructure(self, obi):
        self.obi_ema = 0.8 * self.obi_ema + 0.2 * obi

    def get_directional_probability(self, market_data):
        """Retorna probabilidade de continuação (Trend-Following)."""
        return 0.52 # Base conservadora

    def record_result(self, pnl):
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 2:
                self.ia_cooldown_until = time.time() + 900
        else:
            self.consecutive_losses = 0
            self.ia_cooldown_until = 0
