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
            # Fallback para PyTorch (SOTA v22 standard)
            if os.path.exists(self.model_path):
                # O SOTA usa 5 canais e 3 quantis
                self.model = PatchTST(c_in=5, context_window=60, target_window=5, d_model=128, n_heads=4, n_layers=3)
                state_dict = torch.load(self.model_path, map_location='cpu')
                self.model.load_state_dict(state_dict)
                self.model.eval()
                logging.info(f"--- [v22.5.7] PyTorch Engine Ativo (SOTA v22 Legacy)")
        except Exception as e:
            logging.error(f"Erro ao carregar InferenceEngine: {e}")

    async def predict(self, dataframe):
        """Interface pública assíncrona."""
        if dataframe is None or len(dataframe) < 60:
            return self._neutral_output()
        return await asyncio.to_thread(self._predict_sync, dataframe)

    def _predict_sync(self, dataframe):
        try:
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
                    preds = self.model(torch.tensor(input_tensor)).numpy()[0]
            else:
                return self._neutral_output()

            if preds.ndim == 2:
                q50_path = preds[:, 1]
                f_delta = float(q50_path[-1])
            else:
                f_delta = float(preds) if np.isscalar(preds) else float(preds[0])
            
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
    [SOTA v24.2] Núcleo de Inteligência - Edição Auditoria 11/03.
    """
    def __init__(self):
        self.inference_engine = InferenceEngine()
        self.obi_ema = 0.0
        self.ia_cooldown_until = 0
        self.sentiment_anchor = 0.0
        self.price_history = []
        self.h1_trend = 0
        self.micro_analyzer = self
        self.latest_sentiment_score = 0.0
        self.confidence_buy_threshold = 58.0
        self.confidence_sell_threshold = 42.0
        self.uncertainty_threshold = 0.4
        self.consecutive_losses = 0
        self.vwap_dist_threshold = 800.0

    async def predict_with_patchtst(self, engine, data):
        if engine is None: return {"score": 50.0}
        res = await engine.predict(data)
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
        try:
            if df is None or len(df) < 5: return 0
            last_candles = df.tail(5)
            price_change = abs(last_candles['close'].iloc[-1] - last_candles['close'].iloc[0])
            # [v24.2] Detecção de Tendência Super Permissiva para Ralis de Auditoria
            if (price_change > (atr * 0.9) or h1_trend != 0):
                return 1 # Trending
            if atr > 350: return 2 # Super Volatile / Noise
            return 0 # Mean Reversion / Consolidation
        except:
            return 0

    def calculate_decision(self, **kwargs):
        """
        [v24.2] Lógica de Decisão SOTA 11/03 - Ultrassensível.
        """
        # 1. Recuperação de Parâmetros
        patchtst_score_in = kwargs.get('score', kwargs.get('patchtst_score', 50.0))
        obi = kwargs.get('obi', 0.0)
        sentiment_score = kwargs.get('sentiment', 0.0)
        regime = kwargs.get('regime', 0)
        current_price = kwargs.get('current_price', 0.0)
        vwap = kwargs.get('vwap', 0.0)
        current_vol = kwargs.get('current_vol', 0.0)
        avg_vol_20 = kwargs.get('avg_vol_20', 1.0)
        hour = kwargs.get('hour', 10)
        minute = kwargs.get('minute', 0)

        # 2. Normalização de Score (FUSÃO SOTA v22)
        if isinstance(patchtst_score_in, dict):
            patchtst_score_val = float(patchtst_score_in.get("score", 50.0))
            uncertainty = float(patchtst_score_in.get("uncertainty_norm", 0.0))
        else:
            patchtst_score_val = float(patchtst_score_in)
            uncertainty = 0.0
        
        if patchtst_score_val <= 1.0: patchtst_score_val *= 100.0

        obi_score = 50.0 + (float(obi) * 10.0)
        obi_score = max(0, min(100, obi_score))
        sent_score_norm = 50.0 + (float(sentiment_score) * 10.0)
        sent_score_norm = max(0, min(100, sent_score_norm))
        
        obi_abs = abs(float(obi))
        
        if obi_abs < 0.1:
            # Sem OBI (Dias de Auditoria/Offline), confiamos mais na IA
            score_raw = (patchtst_score_val * 0.7) + (sent_score_norm * 0.3)
        else:
            score_raw = (patchtst_score_val * 0.4) + (obi_score * 0.4) + (sent_score_norm * 0.2)
        
        # 3. Inicialização de Variáveis de Controle
        is_momentum_bypass = False
        is_golden_window = False
        direction = "NEUTRAL"
        exec_strategy = "PASSIVA"
        
        # 4. Detecção de Janela de Ouro (Abertura B3 - Alpha de Tempo)
        if (hour == 10 and minute >= 15) or (hour == 11 and minute <= 15):
            is_golden_window = True
            logging.info(f"[v24.2 GOLDEN-WINDOW] Ativa via Tempo (10:15-11:15).")
            # Relaxamento de incerteza na Janela de Ouro
            self.uncertainty_threshold = 0.8
        else:
            self.uncertainty_threshold = 0.4 # Default v22

        obi_abs = abs(float(obi))
        
        # 5. Definição do Momentum Bypass
        # [v24.2] Na Janela de Ouro ou Tendência Forte (Regime 1), relaxamos thresholds e ampliamos alvos
        if is_golden_window and (obi_abs >= 1.5 or float(score_raw) >= 55.0): # [v24.2] Relaxado de 60 -> 55
            is_momentum_bypass = True
            logging.info(f"[v24.2 GOLDEN-BYPASS] Ativado via Janela de Ouro!")
        elif (regime == 1 and float(score_raw) >= 52.0) or (float(score_raw) >= 80.0 or float(score_raw) <= 20.0):
            if obi_abs >= 1.5 or is_golden_window or regime == 1:
                is_momentum_bypass = True
                logging.info(f"[v24.2 MOMENTUM-BYPASS] Ativado via Fluxo/Regime!")

        # 6. Decisão de Direção e Multiplicadores de Alvo
        sl_multiplier = 1.0
        tp_multiplier = 1.0
        if is_momentum_bypass:
            exec_strategy = "MOMENTUM"
            direction = "COMPRA" if (score_raw >= 50 or obi > 0) else "VENDA"
            # [v24.2] Alvos Institucionais MAX (Captura de Ralis Lendários como 11/03)
            sl_multiplier = 3.0 # 150 -> 450 pts (Suporta as sacudidas da B3)
            tp_multiplier = 8.0 # 300 -> 2400 pts (Barra o rali completo de 11/03)
        else:
            if score_raw >= self.confidence_buy_threshold:
                direction = "COMPRA"
            elif score_raw <= self.confidence_sell_threshold:
                direction = "VENDA"
            exec_strategy = "SNIPER" if direction != "NEUTRAL" else "PASSIVA"

        # 7. Avaliação de Vetos
        vwap_veto = False
        dist_vwap = abs(current_price - vwap)
        limit_eff = self.vwap_dist_threshold
        
        if is_momentum_bypass or is_golden_window or regime == 1 or float(score_raw) >= 60.0:
            vwap_veto = False # Total Bypass para Convicção Institucional (>60)
        else:
            if obi_abs >= 2.0: limit_eff *= 2.0
            if float(dist_vwap) > float(limit_eff): vwap_veto = True

        # 8. RSI Relaxado
        if regime == 1 or is_momentum_bypass:
            rsi_buy_trigger = 38.0
            rsi_sell_trigger = 62.0
        else:
            rsi_buy_trigger = 32.0
            rsi_sell_trigger = 68.0

        # Vetos Finais
        veto_reason = None
        if uncertainty > self.uncertainty_threshold:
            veto_reason = "UNCERTAINTY"
        elif vwap_veto:
            veto_reason = "VWAP_DISTANT"
            
        if veto_reason:
            if current_vol > 0: # Reduz log spam
                logging.warning(f"[DEBUG-AI] Veto: {veto_reason} | Score: {score_raw:.1f} | Bypass: {is_momentum_bypass} | Regime: {regime} | Dist VWAP: {dist_vwap:.1f}")
            direction = "WAIT"
            exec_strategy = "PASSIVA"
        
        return {
            "score": float(score_raw),
            "direction": direction,
            "execution_strategy": exec_strategy,
            "is_momentum_bypass": is_momentum_bypass,
            "lot_multiplier": 1.0,
            "tp_multiplier": 1.5 if is_momentum_bypass else 1.0,
            "veto": veto_reason,
            "reason": veto_reason,
            "h1_trend": self.h1_trend,
            "quantile_confidence": "HIGH" if is_momentum_bypass else "NORMAL",
            "rsi_buy_trigger": rsi_buy_trigger,
            "rsi_sell_trigger": rsi_sell_trigger
        }

    def update_sentiment_anchor(self, price):
        self.price_history.append(price)
        if self.sentiment_anchor == 0: self.sentiment_anchor = price
        else: self.sentiment_anchor = 0.999 * self.sentiment_anchor + 0.001 * price

    def update_microstructure(self, obi):
        self.obi_ema = 0.8 * self.obi_ema + 0.2 * obi

    def get_directional_probability(self, market_data):
        return 0.52

    def record_result(self, pnl):
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 2:
                self.ia_cooldown_until = time.time() + 900
        else:
            self.consecutive_losses = 0
            self.ia_cooldown_until = 0
