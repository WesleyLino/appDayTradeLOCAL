# --- MONKEY-PATCH PARA CONFLITO ONNX/BEARTYPE (v24.4.1) ---
try:
    import sys
    import types

    if "onnxscript" not in sys.modules:
        sys.modules["onnxscript"] = types.ModuleType("onnxscript")
    import onnxscript

    if not hasattr(onnxscript, "values"):
        onnxscript.values = types.ModuleType("values")
        sys.modules["onnxscript.values"] = onnxscript.values
    if not hasattr(onnxscript.values, "ParamSchema"):

        class DummyParamSchema:
            pass

        onnxscript.values.ParamSchema = DummyParamSchema
except Exception:
    pass
# ---------------------------------------------------------

import os
import logging
import numpy as np
import asyncio
import torch
import onnxruntime as ort
import time
from backend.models import PatchTST
from backend.microstructure_analyzer import MicrostructureAnalyzer
import json

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


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
                providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                sess_options = ort.SessionOptions()
                sess_options.log_severity_level = 4  # Silencia erros C++ puros no terminal do usuário
                self.ort_session = ort.InferenceSession(onnx_path, sess_options=sess_options, providers=providers)
                self.use_onnx = True
                logging.info(
                    f"--- [v24.4.1] ONNX Engine Ativo ({self.ort_session.get_providers()[0]}). Model: {onnx_path}"
                )
            elif os.path.exists(self.model_path):
                logging.warning(f"--- [v24.4.1] ONNX Model not found at {onnx_path}. Using PyTorch fallback.")
                self.pytorch_c_in = 8
                self.model = PatchTST(
                    c_in=self.pytorch_c_in,
                    context_window=60,
                    target_window=5,
                    d_model=128,
                    n_heads=4,
                    n_layers=3,
                )
                state_dict = torch.load(self.model_path, map_location="cpu")
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
        return {
            "score": 0.5,
            "forecast_norm": 0.0,
            "confidence": 0.0,
            "uncertainty_norm": 1.0,
            "q50": 0.0,
        }

    async def predict(self, dataframe):
        """Interface pública assíncrona."""
        if dataframe is None:
            logging.warning("AI_CORE: DataFrame is None")
            return self._neutral_output()
        if len(dataframe) < 60:
            logging.warning(f"AI_CORE: DataFrame too short ({len(dataframe)} < 60)")
            return self._neutral_output()
        return await asyncio.to_thread(self._predict_sync, dataframe)

    def _predict_sync(self, dataframe):
        try:
            # [v24.4.1] Sincronização de Canais (v22=5, v24=8)
            is_8_channels = False
            if self.use_onnx and self.ort_session and self.ort_session.get_inputs()[0].shape[2] == 8:
                is_8_channels = True
            elif self.model and getattr(self, "pytorch_c_in", 5) == 8:
                is_8_channels = True

            if is_8_channels:
                cols = [
                    "open",
                    "high",
                    "low",
                    "close",
                    "tick_volume",
                    "cvd_normal",
                    "ofi_normal",
                    "trap_index",
                ]
            else:
                cols = ["open", "high", "low", "close", "tick_volume"]

            # Garante que todas as colunas existem (Padding com zero se faltar para evitar quebra)
            for c in cols:
                if c not in dataframe.columns:
                    # [v24.4] Se faltar métricas de microestrutura, inicializa com neutro
                    dataframe[c] = 0.0

            # Previne falhas E_FAIL(17) no DirectML por Inf/NaN
            input_df = dataframe[cols].replace([np.inf, -np.inf], np.nan)
            input_data = input_df.bfill().ffill().fillna(0.0).values[-60:].astype(np.float32)
            input_tensor = np.expand_dims(input_data, axis=0)  # [1, 60, N]

            if self.use_onnx and self.ort_session:
                try:
                    input_name = self.ort_session.get_inputs()[0].name
                    # [AMD/DirectML] Sempre usar float32 para evitar erro de Cast
                    raw_preds = self.ort_session.run(None, {input_name: input_tensor})[0]
                    preds = raw_preds[0] if raw_preds.ndim == 3 else raw_preds
                except Exception as e_onnx:
                    # Fallback to PyTorch and safely extract pybind11 C++ error which might be cp1252 encoded
                    err_msg = ""
                    if isinstance(e_onnx, UnicodeDecodeError) and hasattr(e_onnx, "object"):
                        err_msg = e_onnx.object.decode("cp1252", errors="replace")
                    else:
                        err_msg = repr(e_onnx)
                    logging.warning(f"ONNX Run falhou, tentando PT fallback. Erro: {err_msg}")
                    
                    if not self.model:
                        logging.warning("Carregando modelo PyTorch de emergência na CPU devido a queda na GPU...")
                        try:
                            self.pytorch_c_in = 8
                            self.model = PatchTST(
                                c_in=self.pytorch_c_in,
                                context_window=60,
                                target_window=5,
                                d_model=128,
                                n_heads=4,
                                n_layers=3,
                            )
                            state_dict = torch.load(self.model_path, map_location="cpu", weights_only=False)  # [FIX-FALLBACK] .pt contém tensores GPU (_rebuild_device_tensor_from_numpy), weights_only=True bloqueia corretamente
                            self.model.load_state_dict(state_dict)
                            self.model.eval()
                            self.use_onnx = False  # Desativa ONNX permanentemente para evitar spam de erro de GPU
                        except Exception as eload:
                            logging.error(f"Falha gravíssima ao carregar Fallback: {eload}")

                    if self.model:
                        with torch.no_grad():
                            raw_preds = self.model(torch.tensor(input_tensor)).numpy()
                            preds = raw_preds[0] if raw_preds.ndim == 3 else raw_preds
                    else:
                        logging.warning("AI_CORE: ONNX failed and No PyTorch model loaded for fallback")
                        return self._neutral_output()
            elif self.model:
                with torch.no_grad():
                    raw_preds = self.model(torch.tensor(input_tensor)).numpy()
                    preds = raw_preds[0] if raw_preds.ndim == 3 else raw_preds
            else:
                logging.warning("AI_CORE: No ONNX and No PyTorch model loaded")
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
                "q90": float(preds[-1, 2]) if preds.ndim == 2 else 0.0,
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
        self.momentum_bypass_threshold = (
            68.0  # [v24.5] Thresh de ativação institucional Sniper - Perfil 3k
        )
        self.bluechip_bias_threshold = 0.25
        self.use_bluechip_bias = True

    async def predict_with_patchtst(self, engine, data):
        if engine is None:
            return {"score": 50.0}
        res = await engine.predict(data)
        res["score"] = res.get("score", 0.5) * 100.0
        return res

    def update_h1_trend(self, h1_data):
        if h1_data is None or len(h1_data) < 2:
            self.h1_trend = 0
            return
        last_close = h1_data["close"].iloc[-1]
        ma20 = (
            h1_data["close"].rolling(20).mean().iloc[-1]
            if len(h1_data) >= 20
            else last_close
        )
        if last_close > ma20 * 1.002:
            self.h1_trend = 1
        elif last_close < ma20 * 0.998:
            self.h1_trend = -1
        else:
            self.h1_trend = 0

    def detect_regime(self, volatility, obi):
        """
        [v24.4.4] Identifica o regime de mercado para o main.py.
        0: Lateral, 1: Tendência, 2: Volátil
        Sensibilidade aumentada para auditoria de UI.
        """
        try:
            # [ANTIVIBE-CODING] - Thresholds calibrados para o mercado atual (Mini Índice)
            if abs(obi) > 0.85:
                return 1  # Fluxo direcional (era 1.2)
            if volatility > 100.0:
                return 2  # Volatilidade (era 150.0)
            return 0  # Mercado em consolidação
        except:
            return 0

    def identify_market_regime(self, df, h1_trend, atr, adx, bb_up, bb_down, bb_mid):
        try:
            if df is None or len(df) < 5:
                return 0
            last_candles = df.tail(5)
            price_change = abs(
                last_candles["close"].iloc[-1] - last_candles["close"].iloc[0]
            )
            # [ANTIVIBE-CODING] Sincronizado com detect_regime (Ultra-sensível)
            if price_change > (atr * 0.7) or h1_trend != 0:
                return 1  # Tendência (Trending)
            if atr > 100.0:
                return 2  # Volatilidade/Ruído (era 350)
            return 0  # Mercado em consolidação
        except:
            return 0

    def calculate_decision(self, **kwargs):
        """
        [v24.2] Lógica de Decisão SOTA 11/03 - Ultrassensível.
        """
        # 1. Recuperação de Parâmetros
        patchtst_score_in = kwargs.get("score", kwargs.get("patchtst_score", 50.0))
        obi = kwargs.get("obi", 0.0)
        sentiment_score = kwargs.get("sentiment", 0.0)
        regime = kwargs.get("regime", 0)
        current_price = kwargs.get("current_price", 0.0)
        vwap = kwargs.get("vwap", 0.0)
        current_vol = kwargs.get("current_vol", 0.0)
        avg_vol_20 = kwargs.get("avg_vol_20", 1.0)
        hour = kwargs.get("hour", 10)
        minute = kwargs.get("minute", 0)
        atr = kwargs.get("atr", 0.0)
        # [ANTIVIBE-CODING] Mapeamento Crítico de Regimes: 0=Lateral, 1=Tendência, 2=Volátil
        regime = int(regime)

        # 2. Normalização de Score (FUSÃO SOTA v22)
        if isinstance(patchtst_score_in, dict):
            patchtst_score_val = float(patchtst_score_in.get("score", 50.0))
            uncertainty = float(patchtst_score_in.get("uncertainty_norm", 0.0))
        else:
            patchtst_score_val = float(patchtst_score_in)
            uncertainty = 0.0

        if patchtst_score_val <= 1.0:
            patchtst_score_val *= 100.0

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
            score_raw = (
                (patchtst_score_val * 0.2) + (obi_score * 0.6) + (sent_score_norm * 0.2)
            )

        # 3. Inicialização de Variáveis de Controle
        is_momentum_bypass = False
        is_golden_window = False
        direction = "NEUTRAL"
        exec_strategy = "PASSIVA"

        # 4. Detecção de Janela de Ouro (Abertura B3 - Alpha de Tempo)
        # [v24.5] Expansão para 10:00 - 11:30 para capturar o rali pós-abertura consolidado
        if (hour == 10) or (hour == 11 and minute <= 30):
            is_golden_window = True
            logging.info(
                f"[v24.5 JANELA-DE-OURO] Ativa via Tempo ({hour:02d}:{minute:02d})."
            )
            # Relaxamento de incerteza na Janela de Ouro (Alta Confiança Institucional)
            self.uncertainty_threshold = 0.85  # [v24.5] Aumentado de 0.8
        elif hour == 9:
            is_opening_window = True
            logging.info(
                "[v24.4.1 ABERTURA-VIGOROSA] Janela de Abertura (09:00-10:00)."
            )
            self.uncertainty_threshold = 0.6
        else:
            self.uncertainty_threshold = 0.4

        # [v24.4.1] Fusão de Scores com Vigor de Abertura
        is_opening_window = hour == 9
        if is_opening_window:
            score_raw = (
                (patchtst_score_val * 0.4) + (obi_score * 0.4) + (sent_score_norm * 0.2)
            )
        else:
            if is_golden_window or regime == 1:
                # [v24.5] Redução do rigor de OBI em ralis (Peso 0.5 em vez de 0.6 para evitar dependência tóxica)
                score_raw = (
                    (patchtst_score_val * 0.3)
                    + (obi_score * 0.5)
                    + (sent_score_norm * 0.2)
                )
            elif obi_abs < 0.1:
                score_raw = (patchtst_score_val * 0.7) + (sent_score_norm * 0.3)
            else:
                score_raw = (
                    (patchtst_score_val * 0.2)
                    + (obi_score * 0.6)
                    + (sent_score_norm * 0.2)
                )

        # [v24.4.1] Barreira de Entrada Dinâmica
        opening_discount = 5.0 if (is_opening_window or is_golden_window) else 0.0

        # [v24.4] Calibragem Fina de Risco - Sensibilidade Multi-Ativo
        is_wdo = current_price < 15000
        atr_ref = 75.0 if not is_wdo else 4.0
        risk_factor = atr / atr_ref

        vol_impact = risk_factor * 2.0
        obi_relief = min(12.0, (obi_abs - 1.0) * 5.0) if obi_abs > 1.0 else 0.0

        dynamic_bypass_thresh = max(
            self.momentum_bypass_threshold - 3.0 - opening_discount,
            min(
                89.0,
                self.momentum_bypass_threshold
                + vol_impact
                - obi_relief
                - opening_discount,
            ),
        )

        # [v24.5] Convicção Direcional (IA + Fluxo + Aceleração)
        # Momentum Bypass Pro: Se score >= threshold dinâmico, ignora RSI esticado
        cvd_accel = kwargs.get("cvd_accel", 0.0)
        is_institutional_sweep = (score_raw >= self.momentum_bypass_threshold and cvd_accel >= 0.1) or (
            score_raw <= (100.0 - self.momentum_bypass_threshold) and cvd_accel <= -0.1
        )

        is_high_conviction = score_raw >= dynamic_bypass_thresh or score_raw <= (
            100.0 - dynamic_bypass_thresh
        )

        golden_thresh = self.momentum_bypass_threshold + 7.0
        if is_golden_window and (
            obi_abs >= 1.8 or (float(score_raw) >= golden_thresh or float(score_raw) <= (100.0 - golden_thresh))
        ):
            is_momentum_bypass = True  # [v24.6-ANTILOSS] Threshold elevado via JSON (ex: 68+7=75%)
            logging.info(
                f"[v24.5 BYPASS-DE-OURO] Ativado via Janela de Ouro! (Score: {score_raw:.1f})"
            )
        elif is_institutional_sweep:
            is_momentum_bypass = True
            logging.info(
                f"🚀 [v24.5 MOMENTUM-PRO] Sweep Institucional Detectado (Score: {score_raw:.1f} | Accel: {cvd_accel:.2f})"
            )
        elif is_high_conviction and (
            obi_abs >= 1.5 or is_golden_window or is_opening_window or regime == 1
        ):
            is_momentum_bypass = True
            logging.info(
                f"[v24.4 MOMENTUM-BYPASS] Ativado via Fluxo/Regime/Abertura! (Thresh: {dynamic_bypass_thresh:.1f})"
            )

        # [MELHORIA C - DIAS MORTOS] Curva adaptativa no crivo da IA Core para Scalping Lateral
        # Em dias sem volume concentrado (regime==0, obi_abs < 1.0, ATR normal/baixo),
        # autoriza trades puramente pelo núcleo preditivo do PatchTST caso atinja grande convicção cruzada.
        is_lateral_bypass = False
        if regime == 0 and obi_abs < 1.0:
            # Exige certeza de >=60 ou <=40. Uma score de 60 na rede é alta probabilidade dadas as compressões.
            if patchtst_score_val >= 60.0 or patchtst_score_val <= 40.0:
                is_lateral_bypass = True
                logging.info(
                    f"🦇 [LATERAL-SCALP-BYPASS] Ativado via IA Core puro! (PatchTST: {patchtst_score_val:.1f})"
                )

        # [v24] Lógica de Multiplicador de Alvos Exponenciais (Momentum Bypass)
        tp_multiplier = 1.0
        sl_multiplier = 1.0  # [v24.2] Novo multiplicador para Stop Loss em Momento

        if is_momentum_bypass:
            # Alvos Institucionais para Ralis (x8 TP / x3 SL)
            # Esses valores garantem que capturamos o movimento total sem stop curto demais
            tp_multiplier = 8.0
            sl_multiplier = 3.0
            logging.info(
                f"🚀 [BYPASS-PRO] Ativado! Score={score_raw:.1f}, OBI={obi_abs:.1f}, Regime={regime}"
            )
        else:
            # Multiplicador padrão do SOTA para ganhos estendidos
            tp_multiplier = 1.5
            # [v24.2.1] Extensão em Tendência (Regime 1): x1.15 adicional
            if regime == 1:
                tp_multiplier *= 1.15
                if current_vol > 0:
                    logging.info(
                        f"📈 [REGIME-1] Alvos Normais. Score={score_raw:.1f}, OBI={obi_abs:.1f}, Bypass=OFF"
                    )
            sl_multiplier = 1.0  # Mantém Stop Loss padrão se não for momentum bruto

        # 6. Decisão de Direção e Multiplicadores de Alvo
        if is_momentum_bypass or is_lateral_bypass:
            exec_strategy = "MOMENTUM" if is_momentum_bypass else "LATERAL_SCALP"
            if patchtst_score_val > 50:
                direction = "BUY"
            elif patchtst_score_val < 50:
                direction = "SELL"
            else:
                direction = "BUY" if obi > 0 else "SELL"  # Desempate pelo fluxo
        else:
            # [v24.2.1] Relaxamento Dinâmico de Confiança para Baixa Volatilidade (ATR < 60)
            # Permite capturar sinais em mercados lentos mas direcionais
            buy_thresh = self.confidence_buy_threshold
            sell_thresh = self.confidence_sell_threshold

            atr_limit = 60.0 if not is_wdo else 3.5
            if 0 < atr < atr_limit and obi_abs < 1.2:
                relax = float(getattr(self, "confidence_relax_factor", 0.75))
                buy_thresh = 50.0 + (buy_thresh - 50.0) * relax
                sell_thresh = 50.0 - (50.0 - sell_thresh) * relax
                logging.info(
                    f"💎 [RELAX-V24] Ativo (ATR={atr:.1f}, OBI={obi_abs:.2f}): Buy={buy_thresh:.1f}, Sell={sell_thresh:.1f}"
                )
            elif 0 < atr < atr_limit and obi_abs >= 1.2:
                logging.info(
                    f"🛡️ [ANTI-SANGRIA] Relaxamento evitado pois Fluxo direcional forte (OBI={obi_abs:.2f} >= 1.2) mesmo com ATR baixo."
                )

            if score_raw >= buy_thresh:
                direction = "BUY"
            elif score_raw <= sell_thresh:
                direction = "SELL"
            exec_strategy = "SNIPER" if direction != "NEUTRAL" else "PASSIVA"

        # 7. Avaliação de Vetos
        vwap_veto = False
        dist_vwap = abs(current_price - vwap)

        # [v24.4.1] Sincronia de Precisão: Threshold de VWAP dinâmico
        limit_eff = (current_price * 0.02) if not is_wdo else 40.0

        # [v24.4.1] Relaxamento VWAP em Baixa Volatilidade (Reversões Precoces)
        atr_limit = 60.0 if not is_wdo else 3.5
        if 0 < atr < atr_limit:
            limit_eff *= 1.20  # Aumenta tolerância em 20% para capturar reversões
            logging.info(
                f"💎 [VWAP-FLEX] Baixa Volatilidade ({atr:.1f}). Tolerância expandida: {limit_eff:.1f}"
            )

        # [v24.4.3] Trava de Sanidade Reforçada Dinâmica: Aceita até 6% de distância em ralis 2026
        max_valid_dist = (current_price * 0.06) if not is_wdo else 300.0

        # Log de Auditoria de Veto (Apenas se VWAP for válido para evitar alarmes falsos em warmup)
        if vwap > 0 and (dist_vwap > (current_price * 0.01)):
            logging.info(
                f"[AUDIT-VWAP] Price: {current_price:.1f} | VWAP: {vwap:.1f} | Dist: {dist_vwap:.1f} | MaxPermitida: {max_valid_dist:.1f}"
            )

        if vwap <= 0:
            vwap_veto = False
            # [ANTIVIBE-CODING] Em warmup, o VWAP pode ser 0. Forçamos vwap=price para neutralizar dist_vwap.
            dist_vwap = 0.0
            logging.debug(
                "⚠️ VWAP não disponível (0.0). Neutralizando distância para evitar veto."
            )
        elif dist_vwap > max_valid_dist:
            vwap_veto = False
            logging.warning(
                f"🛡️ [SANITY-TRAP] VWAP Anômalo Detectado ({dist_vwap:.1f}). Ignorando veto para evitar travamento institucional."
            )
        elif (
            is_momentum_bypass
            or is_golden_window
            or is_opening_window
            or regime == 1
            or float(score_raw) >= 60.0
        ):
            vwap_veto = False  # Momentum, Convicção Alta e ABERTURA ignoram VWAP
        else:
            if obi_abs >= 2.0:
                limit_eff *= 2.0
            if float(dist_vwap) > float(limit_eff):
                vwap_veto = True

        # [MELHORIA DA BLINDAGEM INSTITUCIONAL H1]
        if self.use_h1_trend_bias and self.h1_trend != 0 and direction != "NEUTRAL":
            if direction == "SELL" and self.h1_trend == 1:
                target_sell_thresh = max(5.0, 50.0 - ((50.0 - self.confidence_sell_threshold) * 1.5))
                if float(score_raw) <= target_sell_thresh:
                    logging.info(f"⚡ [H1 BLINDAGEM OVERRIDE] VENDA contra-tendência permitida por Super Convicção! ({score_raw:.1f} <= {target_sell_thresh:.1f})")
                else:
                    logging.warning(f"⛔ [H1 BLINDAGEM] VENDA abortada. Requer Convicção de {target_sell_thresh:.1f} contra Macro de ALTA.")
                    direction = "NEUTRAL"
                    exec_strategy = "PASSIVA"
            elif direction == "BUY" and self.h1_trend == -1:
                target_buy_thresh = min(95.0, 50.0 + ((self.confidence_buy_threshold - 50.0) * 1.5))
                if float(score_raw) >= target_buy_thresh:
                    logging.info(f"⚡ [H1 BLINDAGEM OVERRIDE] COMPRA contra-tendência permitida por Super Convicção! ({score_raw:.1f} >= {target_buy_thresh:.1f})")
                else:
                    logging.warning(f"⛔ [H1 BLINDAGEM] COMPRA abortada. Requer Convicção de {target_buy_thresh:.1f} contra Macro de BAIXA.")
                    direction = "NEUTRAL"
                    exec_strategy = "PASSIVA"

        # 8. RSI Relaxado
        if regime == 1 or is_momentum_bypass:
            rsi_buy_trigger = 38.0
            rsi_sell_trigger = 62.0
        else:
            rsi_buy_trigger = 32.0
            rsi_sell_trigger = 72.0  # [MELHORIA-RSI] Maior rigor para vendas em consolidação

        # 9. Veto BlueChip Bias (Influência Institucional PETR/VALE/ITUB)
        bluechip_veto = False
        if getattr(self, "use_bluechip_bias", False) and direction != "NEUTRAL":
            score_bc = getattr(self, "latest_sentiment_score", 0.0)
            thresh_bc = getattr(self, "bluechip_bias_threshold", 0.25)
            
            if direction == "SELL" and score_bc > thresh_bc:
                bluechip_veto = True
                logging.warning(f"⛔ [BLUECHIP-BIAS] VENDA abortada. Sentimento BlueChips é ALTA ({score_bc:.2f} > {thresh_bc:.2f})")
            elif direction == "BUY" and score_bc < -thresh_bc:
                bluechip_veto = True
                logging.warning(f"⛔ [BLUECHIP-BIAS] COMPRA abortada. Sentimento BlueChips é BAIXA ({score_bc:.2f} < -{thresh_bc:.2f})")

        # Vetos Finais (Com Bypass de Sanidade v24.5 + MELHORIA-1)
        veto_reason = None
        if vwap_veto:
            veto_reason = "DIST_VWAP"
        elif bluechip_veto:
            veto_reason = "BLUECHIP_BIAS"

        # [MELHORIA-1 v2] Threshold de Incerteza Condicional — Fusão Temporal + OBI
        # Princípio: eff_threshold = max(threshold_por_horario, bonus_obi)
        # Garante que janelas permissivas (Janela de Ouro=0.85) não sejam reduzidas pelo OBI.
        # A MELHORIA-1 ADICIONA permissividade — nunca reduz.
        #   is_momentum_bypass → 0.65 ou o temporal se maior (Janela de Ouro sobrepõe)
        #   OBI >= 0.3 no horário normal → 0.55 (melhoria sobre 0.40 padrão)
        #   OBI < 0.3 no horário normal → 0.40 padrão (conservador)
        #   Janela de Ouro (10-11:30) → self.uncertainty_threshold = 0.85 (já muito permissivo)
        if is_momentum_bypass:
            # Momentum bypass: usa o maior entre 0.65 e o threshold temporal atual
            eff_uncertainty_thresh = max(0.65, self.uncertainty_threshold)
        elif obi_abs >= 0.3:
            # OBI confirma direção: MELHORIA-1 aumenta para 0.55, mas respeita janelas mais generosas
            eff_uncertainty_thresh = max(0.55, self.uncertainty_threshold)
            logging.debug(
                f"[MELHORIA-1] Uncertainty threshold: max(0.55, {self.uncertainty_threshold:.2f}) = {eff_uncertainty_thresh:.2f} (OBI={obi_abs:.2f})"
            )
        else:
            # Sem fluxo direcional → usa threshold temporal puro (0.40 normal, 0.85 Janela de Ouro)
            eff_uncertainty_thresh = self.uncertainty_threshold

        if uncertainty > eff_uncertainty_thresh and not veto_reason:
            veto_reason = "UNCERTAINTY"
        elif vwap_veto and not is_momentum_bypass and not veto_reason:
            veto_reason = "VWAP_DISTANT"

        if veto_reason:
            if current_vol > 0:  # Reduz log spam
                logging.warning(
                    f"[DEBUG-AI] Veto: {veto_reason} | Score: {score_raw:.1f} | Bypass: {is_momentum_bypass} | OBI: {obi_abs:.2f} | Thresh: {eff_uncertainty_thresh:.2f} | Uncertainty: {uncertainty:.2f}"
                )
            direction = "WAIT"
            exec_strategy = "PASSIVA"

        # [FIX #37] Breakdown de contribuição para log de execução em main.py
        total_weight = (0.4 if is_opening_window else (0.3 if (is_golden_window or regime == 1) else (0.7 if obi_abs < 0.1 else 0.2)))
        obi_weight   = (0.4 if is_opening_window else (0.5 if (is_golden_window or regime == 1) else (0.0 if obi_abs < 0.1 else 0.6)))
        sent_weight  = 0.2

        return {
            "score": float(score_raw),
            "direction": direction,
            "execution_strategy": exec_strategy,
            "execution_mode": exec_strategy,       # [COMPAT] alias para backtest_pro.py
            "is_momentum_bypass": is_momentum_bypass,
            "is_lateral_bypass": is_lateral_bypass,
            "is_golden_window": is_golden_window,
            "lot_multiplier": 1.0,
            "tp_multiplier": tp_multiplier,
            "sl_multiplier": sl_multiplier,
            "veto": veto_reason,
            "reason": veto_reason,
            "h1_trend": self.h1_trend,
            "quantile_confidence": "HIGH" if is_momentum_bypass else "NORMAL",
            "rsi_buy_trigger": rsi_buy_trigger,
            "rsi_sell_trigger": rsi_sell_trigger,
            "use_partial": True,                   # [COMPAT] habilita saídas parciais
            "uncertainty": max(0.0, min(1.0, abs(score_raw - 50.0) / 50.0 * -1 + 1)),  # 50=max incerteza, 0/100=certeza
            "breakdown": {                         # [FIX #37] Log de execução main.py L1597-1599
                "patchtst_contribution": (patchtst_score_val - 50.0) / 100.0 * total_weight,
                "obi_contribution":      (obi_score - 50.0)          / 100.0 * obi_weight,
                "sentiment_contribution":(sent_score_norm - 50.0)    / 100.0 * sent_weight,
            },
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
        """Proxy para MicrostructureAnalyzer com proteção anti-quebra."""
        if hasattr(self, "micro_analyzer") and hasattr(self.micro_analyzer, "analyze"):
            return self.micro_analyzer.analyze(book, ticks_df)
        return {"imbalance": 0.0, "spread": 5.0, "volume_ratio": 1.0, "liquidity_score": 0.5}

    def calculate_wen_ofi(self, book):
        """Proxy para MicrostructureAnalyzer com proteção anti-quebra."""
        if hasattr(self, "micro_analyzer") and hasattr(self.micro_analyzer, "calculate_wen_ofi"):
            return self.micro_analyzer.calculate_wen_ofi(book)
        return 0.0

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
