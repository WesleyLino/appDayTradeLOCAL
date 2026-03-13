# --- MONKEY-PATCH PARA CONFLITO ONNX/BEARTYPE (v24.4.1) ---
try:
    import sys
    import types
    if 'onnxscript' not in sys.modules:
        sys.modules['onnxscript'] = types.ModuleType('onnxscript')
    import onnxscript
    if not hasattr(onnxscript, 'values'):
        onnxscript.values = types.ModuleType('values')
        sys.modules['onnxscript.values'] = onnxscript.values
    if not hasattr(onnxscript.values, 'ParamSchema'):
        class DummyParamSchema: pass
        onnxscript.values.ParamSchema = DummyParamSchema
except Exception:
    pass
# ---------------------------------------------------------

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
from backend.microstructure_analyzer import MicrostructureAnalyzer
import json

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
            # 1. Tentar ONNX (Prioridade SOTA v24.4 AMD/DirectML)
            onnx_path = self.model_path.replace(".pth", "_optimized.onnx")
            if os.path.exists(onnx_path):
                providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
                self.ort_session = ort.InferenceSession(onnx_path, providers=providers)
                self.use_onnx = True
                logging.info(f"--- [v24.4.1] ONNX Engine Ativo ({self.ort_session.get_providers()[0]})")
                return

            # 2. Fallback para PyTorch (SOTA v22 standard)
            if os.path.exists(self.model_path):
                self.model = PatchTST(c_in=5, context_window=60, target_window=5, d_model=128, n_heads=4, n_layers=3)
                state_dict = torch.load(self.model_path, map_location='cpu')
                self.model.load_state_dict(state_dict)
                self.model.eval()
                logging.info("--- [v22.5.7] PyTorch Engine Ativo (CPU Fallback)")
        except Exception as e:
            logging.error(f"Erro ao carregar InferenceEngine: {repr(e)}")

    def check_resources(self):
        """Verifica se os arquivos de modelo necessários existem."""
        missing = []
        if not os.path.exists(self.model_path):
            # Se não tem o .pth, verifica se ao menos tem o .onnx alternativo
            onnx_path = self.model_path.replace(".pth", "_optimized.onnx")
            if not os.path.exists(onnx_path):
                missing.append(self.model_path)
        return missing

    def _neutral_output(self):
        return {"score": 0.5, "forecast_norm": 0.0, "confidence": 0.0, "uncertainty_norm": 1.0, "q50": 0.0}

    async def predict(self, dataframe):
        """Interface pública assíncrona."""
        if dataframe is None or len(dataframe) < 60:
            return self._neutral_output()
        return await asyncio.to_thread(self._predict_sync, dataframe)

    def _predict_sync(self, dataframe):
        try:
            # [v24.4.1] Sincronização de 5 Canais Obrigatórios (v22 Legacy compatibility)
            cols = ['open', 'high', 'low', 'close', 'tick_volume']
            
            # Garante que todas as colunas existem (Padding com zero se faltar)
            for c in cols:
                if c not in dataframe.columns:
                    dataframe[c] = 0.0
            
            input_data = dataframe[cols].values[-60:].astype(np.float32)
            input_tensor = np.expand_dims(input_data, axis=0) # [1, 60, 5]

            if self.use_onnx and self.ort_session:
                input_name = self.ort_session.get_inputs()[0].name
                # [AMD/DirectML] Sempre usar float32 para evitar erro de Cast
                raw_preds = self.ort_session.run(None, {input_name: input_tensor})[0]
                preds = raw_preds[0] if raw_preds.ndim == 3 else raw_preds
            elif self.model:
                with torch.no_grad():
                    raw_preds = self.model(torch.tensor(input_tensor)).numpy()
                    preds = raw_preds[0] if raw_preds.ndim == 3 else raw_preds
            else:
                return self._neutral_output()

            if preds.ndim == 2:
                q50_path = preds[:, 1]
                f_delta = float(q50_path[-1])
            else:
                f_delta = float(preds) if np.isscalar(preds) else float(preds[0])
            
            final_score = max(0.0, min(1.0, 0.5 + (f_delta / 2.0)))
            confidence = 0.85 + (abs(f_delta) * 0.1)
            
            return {
                "score": float(final_score),
                "forecast_norm": float(f_delta),
                "confidence": float(confidence),
                "uncertainty_norm": float(1.0 - confidence),
                "q10": float(preds[-1, 0]) if preds.ndim == 2 else 0.0,
                "q50": float(preds[-1, 1]) if preds.ndim == 2 else 0.0,
                "q90": float(preds[-1, 2]) if preds.ndim == 2 else 0.0
            }
        except Exception as e:
            logging.error(f"Erro na inferência: {repr(e)}")
            return self._neutral_output()

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
        self.micro_analyzer = MicrostructureAnalyzer()
        self.latest_sentiment_score = 0.0
        self.confidence_buy_threshold = 58.0
        self.confidence_sell_threshold = 42.0
        self.uncertainty_threshold = 0.4
        self.consecutive_losses = 0
        self.vwap_dist_threshold = 800.0
        self.use_h1_trend_bias = True
        self.h1_ma_period = 20
        self.confidence_relax_factor = 0.80
        self.uncertainty_threshold_base = 0.25
        self.lot_multiplier_partial = 0.25
        self.atr_confidence_relax_trigger = 100.0
        self.momentum_bypass_threshold = 81.0 # [v24.4] Thresh de ativação institucional

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

    def detect_regime(self, volatility, obi):
        """
        [v24.4.4] Identifica o regime de mercado para o main.py.
        0: Lateral, 1: Tendência, 2: Volátil
        Sensibilidade aumentada para auditoria de UI.
        """
        try:
            # [ANTIVIBE-CODING] - Thresholds calibrados para o mercado atual (Mini Índice)
            if abs(obi) > 0.85: return 1 # Fluxo direcional (era 1.2)
            if volatility > 100.0: return 2 # Volatilidade (era 150.0)
            return 0 # Mercado em consolidação
        except:
            return 0

    def identify_market_regime(self, df, h1_trend, atr, adx, bb_up, bb_down, bb_mid):
        try:
            if df is None or len(df) < 5: return 0
            last_candles = df.tail(5)
            price_change = abs(last_candles['close'].iloc[-1] - last_candles['close'].iloc[0])
            # [ANTIVIBE-CODING] Sincronizado com detect_regime (Ultra-sensível)
            if (price_change > (atr * 0.7) or h1_trend != 0):
                return 1 # Tendência (Trending)
            if atr > 100.0: return 2 # Volatilidade/Ruído (era 350)
            return 0 # Mercado em consolidação
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
        atr = kwargs.get('atr', 0.0)
        # [ANTIVIBE-CODING] Mapeamento Crítico de Regimes: 0=Lateral, 1=Tendência, 2=Volátil
        regime = int(regime)
        
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
            # [v24.3] Maior peso ao fluxo (OBI) para capturar ralis institucionais
            score_raw = (patchtst_score_val * 0.2) + (obi_score * 0.6) + (sent_score_norm * 0.2)
        
        # 3. Inicialização de Variáveis de Controle
        is_momentum_bypass = False
        is_golden_window = False
        direction = "NEUTRO"
        exec_strategy = "PASSIVA"
        
        # 4. Detecção de Janela de Ouro (Abertura B3 - Alpha de Tempo)
        if (hour == 10 and minute >= 15) or (hour == 11 and minute <= 15):
            is_golden_window = True
            logging.info("[v24.2 JANELA-DE-OURO] Ativa via Tempo (10:15-11:15).")
            # Relaxamento de incerteza na Janela de Ouro
            self.uncertainty_threshold = 0.8
        else:
            self.uncertainty_threshold = 0.4 # Default v22

        obi_abs = abs(float(obi))
        
        # [v24.4] Calibragem Fina de Risco - Sensibilidade Multi-Ativo
        is_wdo = (current_price < 15000) # [AUDIT] Identifica se é WDO (Preço ~5k) vs WIN (Preço ~130k)
        
        atr_ref = 75.0 if not is_wdo else 4.0 # Base de normalização ATR: WIN=75, WDO=4
        risk_factor = atr / atr_ref
        
        # [v24.4] Calibragem Fina de Risco
        vol_impact = risk_factor * 2.0  # Menos punitivo
        obi_relief = min(12.0, (obi_abs - 1.0) * 5.0) if obi_abs > 1.0 else 0.0
        
        # O thresh final sobe menos com a volatilidade e desce MAIS com o fluxo confirmado
        dynamic_bypass_thresh = max(self.momentum_bypass_threshold - 3.0, min(89.0, self.momentum_bypass_threshold + vol_impact - obi_relief))
        
        # Convicção Direcional (IA + Fluxo)
        is_high_conviction = (score_raw >= dynamic_bypass_thresh or score_raw <= (100.0 - dynamic_bypass_thresh))
        
        if is_golden_window and (obi_abs >= 1.5 or (float(score_raw) >= 55.0 or float(score_raw) <= 45.0)):
            is_momentum_bypass = True
            logging.info(f"[v24.4 BYPASS-DE-OURO] Ativado via Janela de Ouro! (Thresh: {dynamic_bypass_thresh:.1f})")
        elif is_high_conviction and (obi_abs >= 1.5 or is_golden_window or regime == 1):
            # Alta convicção dinâmica com suporte de fluxo ou regime
            is_momentum_bypass = True
            logging.info(f"[v24.4 MOMENTUM-BYPASS] Ativado via Fluxo/Regime! (Thresh: {dynamic_bypass_thresh:.1f})")

        # [v24] Lógica de Multiplicador de Alvos Exponenciais (Momentum Bypass)
        tp_multiplier = 1.0
        sl_multiplier = 1.0 # [v24.2] Novo multiplicador para Stop Loss em Momento

        if is_momentum_bypass:
            # Alvos Institucionais para Ralis (x8 TP / x3 SL)
            # Esses valores garantem que capturamos o movimento total sem stop curto demais
            tp_multiplier = 8.0 
            sl_multiplier = 3.0
            logging.info(f"🚀 [BYPASS-PRO] Ativado! Score={score_raw:.1f}, OBI={obi_abs:.1f}, Regime={regime}")
        else:
            # Multiplicador padrão do SOTA para ganhos estendidos
            tp_multiplier = 1.5
            # [v24.2.1] Extensão em Tendência (Regime 1): x1.15 adicional
            if regime == 1:
                tp_multiplier *= 1.15
                if current_vol > 0:
                    logging.info(f"📈 [REGIME-1] Alvos Normais. Score={score_raw:.1f}, OBI={obi_abs:.1f}, Bypass=OFF")
            sl_multiplier = 1.0 # Mantém Stop Loss padrão se não for momentum bruto

        # 6. Decisão de Direção e Multiplicadores de Alvo
        if is_momentum_bypass:
            exec_strategy = "MOMENTUM"
            direction = "COMPRA" if (score_raw >= 50 or obi > 0) else "VENDA"
        else:
            # [v24.2.1] Relaxamento Dinâmico de Confiança para Baixa Volatilidade (ATR < 60)
            # Permite capturar sinais em mercados lentos mas direcionais
            buy_thresh = self.confidence_buy_threshold
            sell_thresh = self.confidence_sell_threshold
            
            atr_limit = 60.0 if not is_wdo else 3.5
            if 0 < atr < atr_limit:
                relax = float(getattr(self, 'confidence_relax_factor', 0.75))
                buy_thresh = 50.0 + (buy_thresh - 50.0) * relax
                sell_thresh = 50.0 - (50.0 - sell_thresh) * relax
                logging.info(f"💎 [RELAX-V24] Ativo (ATR={atr:.1f}): Buy={buy_thresh:.1f}, Sell={sell_thresh:.1f}")

            if score_raw >= buy_thresh:
                direction = "COMPRA"
            elif score_raw <= sell_thresh:
                direction = "VENDA"
            exec_strategy = "SNIPER" if direction != "NEUTRO" else "PASSIVA"

        # 7. Avaliação de Vetos
        vwap_veto = False
        dist_vwap = abs(current_price - vwap)
        
        # [v24.4] Sincronia de Precisão: Threshold de VWAP dinâmico (WIN: 2% do preço, WDO: 40 pts)
        limit_eff = (current_price * 0.02) if not is_wdo else 40.0
        
        # [v24.4.3] Trava de Sanidade Reforçada Dinâmica: Aceita até 6% de distância em ralis 2026
        max_valid_dist = (current_price * 0.06) if not is_wdo else 300.0
        
        # Log de Auditoria de Veto (Apenas se VWAP for válido para evitar alarmes falsos em warmup)
        if vwap > 0 and (dist_vwap > (current_price * 0.01)):
            logging.info(f"[AUDIT-VWAP] Price: {current_price:.1f} | VWAP: {vwap:.1f} | Dist: {dist_vwap:.1f} | MaxPermitida: {max_valid_dist:.1f}")

        if vwap <= 0:
            vwap_veto = False
            # [ANTIVIBE-CODING] Em warmup, o VWAP pode ser 0. Forçamos vwap=price para neutralizar dist_vwap.
            dist_vwap = 0.0
            logging.debug("⚠️ VWAP não disponível (0.0). Neutralizando distância para evitar veto.")
        elif dist_vwap > max_valid_dist:
            vwap_veto = False
            logging.warning(f"🛡️ [SANITY-TRAP] VWAP Anômalo Detectado ({dist_vwap:.1f}). Ignorando veto para evitar travamento institucional.")
        elif is_momentum_bypass or is_golden_window or regime == 1 or float(score_raw) >= 60.0:
            vwap_veto = False # Momentum e Convicção Alta ignoram VWAP
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
            direction = "AGUARDAR"
            exec_strategy = "PASSIVA"
        
        return {
            "score": float(score_raw),
            "direction": direction,
            "execution_strategy": exec_strategy,
            "is_momentum_bypass": is_momentum_bypass,
            "lot_multiplier": 1.0,
            "tp_multiplier": tp_multiplier,
            "sl_multiplier": sl_multiplier, # [v24.2] Sincronizado para RiskManager
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

    def analyze(self, book, ticks_df):
        """Proxy para MicrostructureAnalyzer."""
        return self.micro_analyzer.analyze(book, ticks_df)

    def calculate_wen_ofi(self, book):
        """Proxy para MicrostructureAnalyzer."""
        return self.micro_analyzer.calculate_wen_ofi(book)

    async def update_sentiment(self):
        """Lê o sentimento gerado pelo NewsSentimentWorker."""
        path = os.path.join("data", "news_sentiment.json")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.latest_sentiment_score = float(data.get("score", 0.0))
                    return self.latest_sentiment_score
        except Exception as e:
            logging.error(f"Erro ao ler sentimento em AICore: {repr(e)}")
        return 0.0
