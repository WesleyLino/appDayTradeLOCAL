"""
RL Shadow Monitor — Fase 4 do AI Enhancement Roadmap
======================================================
Monitora posições abertas via MT5 e recomenda ações de saída
(HOLD / CLOSE_NOW / TIGHTEN_STOP) usando o PPOAgent em modo
SHADOW (apenas loga recomendações, nunca executa ordens).

Executar como processo paralelo:
    python backend/rl_shadow_monitor.py

Logs em: logs/rl_shadow.log
"""

import time
import logging
import os
import sys
import numpy as np
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importações guardadas para não travar se não houver MT5
try:
    import MetaTrader5 as mt5

    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

from backend.rl_agent import PPOAgent

# ── Logging ──────────────────────────────────────────────────────────────────
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "rl_shadow.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("rl_shadow")

# ── Constantes ────────────────────────────────────────────────────────────────
# Ações: 0=HOLD, 1=CLOSE_NOW, 2=TIGHTEN_STOP
ACTION_NAMES = {0: "HOLD", 1: "CLOSE_NOW", 2: "TIGHTEN_STOP"}
INPUT_DIM = 8  # features de estado da posição
N_ACTIONS = 3

# Thresholds configuráveis (não afetam produção)
SHADOW_CYCLE_SECS = 10  # intervalo de observação em segundos


def build_state(position: dict, current_price: float, atr: float = 50.0) -> np.ndarray:
    """
    Constrói vetor de estado normalizado para o PPOAgent a partir de uma posição MT5.

    Features (8 dimensões):
        0: P&L normalizado pelo SL (quanto do stop já foi consumido)
        1: Tempo desde abertura (em minutos, normalizado para 60min)
        2: Distância ao TP normalizada pelo ATR
        3: Distância ao SL normalizada pelo ATR
        4: Volume relativo (lotes / 3.0 — baseline produção)
        5: Lucro em R$ normalizado (por 300 = 10% do capital)
        6: Sinal de direção (1=compra, -1=venda)
        7: Volatilidade implícita (ATR / preço médio)
    """
    sl = position.get("sl", 0)
    tp = position.get("tp", 0)
    price_open = position.get("price_open", current_price)
    volume = position.get("volume", 1.0)
    profit = position.get("profit", 0.0)
    pos_type = position.get("type", 0)  # 0=BUY, 1=SELL

    direction = 1.0 if pos_type == 0 else -1.0
    dist_sl = abs(current_price - sl) / (atr + 1e-8)
    dist_tp = abs(tp - current_price) / (atr + 1e-8)
    sl_pct = (profit / (abs(price_open - sl) * volume + 1e-8)) if sl != 0 else 0.0
    time_open = position.get("time_open_mins", 0) / 60.0  # normaliza para 1h
    vol_rel = volume / 3.0
    profit_n = profit / 300.0
    vol_impl = atr / (current_price + 1e-8)

    state = np.array(
        [
            np.clip(sl_pct, -2.0, 2.0),
            np.clip(time_open, 0.0, 2.0),
            np.clip(dist_tp, 0.0, 5.0),
            np.clip(dist_sl, 0.0, 5.0),
            np.clip(vol_rel, 0.0, 2.0),
            np.clip(profit_n, -2.0, 2.0),
            direction,
            np.clip(vol_impl, 0.0, 0.05) * 20,  # escala 0-1
        ],
        dtype=np.float32,
    )

    return state


def get_open_positions_mt5() -> list:
    """Retorna posições abertas do MT5 como lista de dicts."""
    if not MT5_AVAILABLE or not mt5.initialize():
        return []
    positions = mt5.positions_get(symbol="WIN$")
    if positions is None:
        return []
    result = []
    tick = mt5.symbol_info_tick(positions[0].symbol) if positions else None
    now_ts = tick.time if tick else int(time.time() - 10800)
    for p in positions:
        time_open_mins = (now_ts - p.time) / 60.0
        result.append(
            {
                "ticket": p.ticket,
                "type": p.type,  # 0=BUY, 1=SELL
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "time_open_mins": time_open_mins,
            }
        )
    return result


def get_current_price_mt5() -> float:
    """Retorna o último preço bid do WIN$."""
    if not MT5_AVAILABLE:
        return 0.0
    tick = mt5.symbol_info_tick("WIN$")
    return tick.bid if tick else 0.0


def run_shadow_loop():
    """Loop principal do monitor em shadow mode."""
    logger.info("🔮 RL Shadow Monitor iniciado. Modo: SHADOW (apenas observação)")
    logger.info(
        f"   Frequência de análise: {SHADOW_CYCLE_SECS}s | Ações: {ACTION_NAMES}"
    )

    agent = PPOAgent(input_dim=INPUT_DIM, n_actions=N_ACTIONS)

    # Tentar carregar pesos pré-treinados se existirem
    weights_path = os.path.join(os.path.dirname(__file__), "rl_shadow_weights.pth")
    if os.path.exists(weights_path):
        import torch

        agent.policy.load_state_dict(torch.load(weights_path, map_location="cpu"))
        agent.policy_old.load_state_dict(torch.load(weights_path, map_location="cpu"))
        logger.info(f"✅ Pesos RL carregados de: {weights_path}")
    else:
        logger.info(
            "⚠️  Sem pesos pré-treinados. Agent operando com política aleatória (Bootstrap)."
        )

    while True:
        try:
            positions = get_open_positions_mt5()
            current_price = get_current_price_mt5()

            if not positions:
                logger.debug("Sem posições abertas. Aguardando...")
            else:
                for pos in positions:
                    state = build_state(pos, current_price)
                    action, log_prob = agent.select_action(state)
                    action_name = ACTION_NAMES.get(action, "UNKNOWN")

                    pnl_str = f"R$ {pos['profit']:+.2f}"
                    logger.info(
                        f"[RL SHADOW] Ticket #{pos['ticket']} | "
                        f"Tipo={'BUY' if pos['type'] == 0 else 'SELL'} | "
                        f"P&L={pnl_str} | "
                        f"Aberto há {pos['time_open_mins']:.1f}min | "
                        f"Recomenda: {action_name} (log_prob={float(log_prob):.3f})"
                    )

        except Exception as e:
            logger.error(f"❌ Erro no ciclo shadow: {e}")

        time.sleep(SHADOW_CYCLE_SECS)


if __name__ == "__main__":
    run_shadow_loop()
