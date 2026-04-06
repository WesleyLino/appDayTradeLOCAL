from fastapi import FastAPI, WebSocket

from dotenv import load_dotenv

from datetime import datetime, timedelta, timezone

import time as time_module

import os

import json

import logging

import asyncio

import traceback

from typing import Optional, List

from fastapi.middleware.cors import CORSMiddleware

import pandas as pd

import numpy as np


# --- CONFIGURAÇÃO DE LOGS OPERACIONAIS ---

import logging.handlers

from logging.handlers import RotatingFileHandler

import sys

import io


# Forçar UTF-8 para o stdout no Windows para evitar quedas por emojis

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

log_file = "backend/trading_bridge.log"

file_handler = logging.FileHandler(
    log_file, encoding="utf-8"
)

file_handler.setFormatter(log_formatter)


# StreamHandler robusto para UTF-8

stream_handler = logging.StreamHandler(sys.stdout)

stream_handler.setFormatter(log_formatter)


logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


# [ANTIVIBE-CODING] - Buffer circular para o Dashboard

trade_logs = []

MAX_LOGS = 50

log_id_counter = 0


def add_operational_log(msg: str, log_type: str = "info"):

    global trade_logs, log_id_counter

    log_id_counter += 1

    # Sanitização extra para garantir que o msg seja string e não cause crashes no JSON do WebSocket

    try:
        clean_msg = str(msg).encode("utf-8", "ignore").decode("utf-8")

    except:
        clean_msg = "[LOG ERROR] Mensagem corrompida"

    timestamp = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%H:%M:%S")

    trade_logs.insert(
        0,
        {
            "id": f"{time_module.time()}-{log_type}-{log_id_counter}",
            "time": timestamp,
            "msg": clean_msg,
            "type": log_type,
        },
    )

    if len(trade_logs) > MAX_LOGS:
        del trade_logs[MAX_LOGS:]


def sanitize_log(e):
    """Protege contra UnicodeDecodeError em logs de exceções."""

    try:
        return str(e).encode("utf-8", "replace").decode("utf-8")

    except:
        return "Unknown error (encoding failure)"


# Inicialização do Log

add_operational_log("Sistema HFT Sniper Inicializado", "info")

load_dotenv()


# --- MONKEY-PATCH PARA CONFLITO ONNX/BEARTYPE (v24.4.1) ---
# Deve ser executado antes de qualquer import do beartype ou torch.onnx
try:
    import sys
    import types

    # Criar módulos/atributos fictícios para satisfazer a verificação de tipos do beartype
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

from backend.mt5_bridge import MT5Bridge

from backend.risk_manager import RiskManager

from backend.ai_core import AICore, InferenceEngine

from backend.persistence import PersistenceManager

from backend.rl_agent import PPOAgent  # HFT v2.0

from backend.microstructure_analyzer import MicrostructureAnalyzer  # HFT v2.0

from backend.news_collector import NewsCollector

from backend.data_collector import DataCollector

# Configuração de Logs Unificada já definida no topo (RotatingFileHandler)


from backend.sentiment_analyzer import SentimentAnalyzer

from backend.calendar_manager import CalendarManager

from backend.news_sentiment_worker import NewsSentimentWorker

from backend.market_data_worker import (
    MarketDataWorker,
)  # Novo Worker de Dados de Mercado

from pydantic import BaseModel


class OrderRequest(BaseModel):
    side: str

    volume: float = 1.0


class SniperStatus(BaseModel):
    running: bool

    consecutive_wins: int

    trade_count: int

    last_trade_time: Optional[str] = None


app = FastAPI()


# [ANTIVIBE-CODING] - Liberação de CORS para Sincronização Dinâmica (v3.2)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://10.0.0.169:3000",  # IP de Rede Detectado
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Inicialização Global de Componentes (HFT v2.1) ---

# [ANTIVIBE-CODING] - Carregamento de Parâmetros Bloqueados V22
# [v24.5] PARÂMETROS BLOQUEADOS (GOLDEN PROFILE) - SOTA SNIPER
LOCKED_PARAMS_FILE = os.path.join("backend", "v24_locked_params.json")
locked_config = {}
if os.path.exists(LOCKED_PARAMS_FILE):
    try:
        with open(LOCKED_PARAMS_FILE, "r") as f:
            locked_config = json.load(f)
            logging.info("🛡️ Parâmetros V22 Bloqueados carregados com sucesso.")
    except Exception as e:
        logging.error(f"⚠️ Falha ao carregar parâmetros bloqueados: {e}")

bridge = MT5Bridge()

# [v24.5] Blindagem de Capital: Limite de R$ 150,00 sobre Capital Base de R$ 500,00.
risk = RiskManager(max_daily_loss=150.0, initial_balance=500.0)

ai = AICore()

persistence = PersistenceManager()

rl_agent = PPOAgent(input_dim=7, n_actions=3)  # Global para evitar lag na conexão

micro_analyzer = MicrostructureAnalyzer()  # Global


# --- ALPHA-X: SNIPER BOT INTEGRATION ---

from backend.bot_sniper_win import SniperBotWIN

# Sniper compartilha os mesmos componentes de infra para economizar recursos

sniper_bot = SniperBotWIN(
    bridge=bridge, risk=risk, ai=ai, log_callback=add_operational_log
)

bot_task = None  # Task para rodar o loop do bot


weights_path = os.path.join(os.getcwd(), "backend", "patchtst_weights_sota.pth")

if not os.path.exists(weights_path):
    # Tentar caminho alternativo

    weights_path = "backend/patchtst_weights_sota.pth"

if not os.path.exists(weights_path):
    weights_path = os.path.join(
        os.getcwd(), "backend", "patchtst_weights.pth"
    )  # Fallback Legado


collector = DataCollector("WIN$")

# inference = InferenceEngine(weights_path) # Moved to startup_event

inference = None


# Novas Camadas de IA

news_collector = NewsCollector()

sentiment_engine = SentimentAnalyzer()

calendar = CalendarManager()


import sys


@app.on_event("startup")
async def startup_event():

    try:
        global inference

        logging.info("Iniciando Inicialização do Servidor SOTA...")

        # Conexão MT5 (Refatorado para não ser bloqueante)

        # [FIX] Reseta o estado de pânico a cada inicialização para evitar bloqueio permanente
        persistence.save_state("panic_status", "IDLE")
        logging.info("[OK] Estado de pânico resetado para: IDLE")

        logging.info("Conectando ao MT5 Bridge...")

        connected = await asyncio.to_thread(bridge.connect)

        if not connected:
            logging.warning(
                "MT5 Bridge não conectado na inicialização. Tentando reconectar..."
            )

            # A reconexão acontece no loop principal, mas podemos logar aqui.

        else:
            try:
                _acc = bridge.mt5.account_info()
                login_info = _acc.login if _acc else "(conta nao disponivel)"

                logging.info(f"[OK] MT5 Bridge conectado: {login_info}")

            except:
                logging.info("[OK] MT5 Bridge conectado.")

        # Atalho Global de Pânico: Ctrl+Q para zerar tudo

        # Verificar recursos críticos

        print("DEBUG: Instanciando InferenceEngine...", file=sys.stderr)

        inference = InferenceEngine(weights_path)

        print("DEBUG: Verificando recursos...", file=sys.stderr)

        missing_resources = inference.check_resources()

        if missing_resources:
            logging.critical(f"RECURSOS FALTANDO: {missing_resources}")

            # Poderíamos travar o startup, mas melhor avisar e rodar em modo degradado

        print("DEBUG: Injetando dependência...", file=sys.stderr)

        # Injeção de Dependência (opcional, já que passamos no loop, mas boa prática)

        ai.inference_engine = inference

        # Iniciar NewsSentimentWorker em background

        try:
            sentiment_worker = NewsSentimentWorker(
                interval=120
            )  # 2 minutos para testes de dinamismo

            asyncio.create_task(sentiment_worker.run())

            logging.info("🚀 NewsSentimentWorker iniciado com sucesso.")

            add_operational_log("Worker de Sentimento (Gemini) Ativado", "success")

        except Exception as e:
            logging.error(f"Erro ao iniciar NewsSentimentWorker: {e}")

        # Iniciar MarketDataWorker em background (HFT Optimization)

        try:
            market_worker = MarketDataWorker(
                bridge=bridge, calendar=calendar, interval=10
            )

            asyncio.create_task(market_worker.run())

            logging.info("🚀 MarketDataWorker iniciado com sucesso.")

            add_operational_log("Worker de Dados Macro/BlueChips Ativado", "success")

        except Exception as e:
            logging.error(f"Erro ao iniciar MarketDataWorker: {e}")

        # [NEW] CARREGAMENTO DE PARÂMETROS HIGH GAIN (SOTA v3)

        try:
            hp_path = os.path.join("backend", "high_gain_parameters.json")

            if os.path.exists(hp_path):
                with open(hp_path, "r") as f:
                    hp = json.load(f)

                    ai.uncertainty_threshold_base = hp.get("threshold", 0.25)

                    ai.lot_multiplier_partial = hp.get("multiplier", 0.25)

                    logging.info(
                        f"🏆 PARÂMETROS HIGH GAIN CARREGADOS: Threshold={ai.uncertainty_threshold_base}, Mult={ai.lot_multiplier_partial}"
                    )

                    add_operational_log(
                        f"Calibragem High Gain Ativada (Thr: {ai.uncertainty_threshold_base})",
                        "success",
                    )

        except Exception as e:
            logging.error(f"Erro ao carregar High Gain Params: {e}")

        # Iniciar a background task que sustenta o robô principal (Modo Autônomo)
        asyncio.create_task(autonomous_bot_loop())
        logging.info(
            "🚀 Autonomous Bot Loop instanciado com sucesso como Background Task."
        )

        print("DEBUG: INICIALIZAÇÃO FINALIZADA", file=sys.stderr)

    except Exception:
        print("ERRO CRÍTICO NA INICIALIZAÇÃO:", file=sys.stderr)

        traceback.print_exc(file=sys.stderr)

        logging.critical("ERRO CRÍTICO NA INICIALIZAÇÃO", exc_info=True)

        # sys.exit(1) # Let uvicorn handle it? No, explicit exit is better if stuck.


async def panic_close_all():
    """Zera todas as posições abertas imediatamente (Execução Assíncrona)."""
    global _panic_in_progress

    # Evita spam do botão de pânico se já estiver ativado

    current_status = await asyncio.to_thread(persistence.get_state, "panic_status")

    if current_status == "CLOSED_ALL":
        return

    logging.warning("!!! BOTÃO DE PÂNICO ACIONADO !!!")

    if bridge.connected:

        # [FIX #PANIC-SYNC] Ativa flag ANTES de fechar para que FLIP-5 não trate
        # o desaparecimento das posições como fechamento externo (SL/TP falso positivo).
        _panic_in_progress = True

        def _close_all_sync():

            mt5 = bridge.mt5

            # [FIX #MP-C] Cancelar TODAS as ordens pendentes antes de fechar posições
            # Previne que ordens LIMIT HFT sejam preenchidas pós-pânico
            pending_orders = mt5.orders_get()
            if pending_orders:
                for order in pending_orders:
                    cancel_req = {
                        "action": mt5.TRADE_ACTION_REMOVE,
                        "order": order.ticket,
                    }
                    mt5.order_send(cancel_req)
                logging.warning(f"PÂNICO: {len(pending_orders)} ordens pendentes canceladas.")

            positions = mt5.positions_get()

            if positions:
                for pos in positions:
                    # B3 Netting: Enviar ordem oposta via close_position (Centralizado)
                    bridge.close_position(pos.ticket)

            return True

        await asyncio.to_thread(_close_all_sync)

        await asyncio.to_thread(persistence.save_state, "panic_status", "CLOSED_ALL")

        # [FIX #PANIC-SYNC] Desativa flag após todas as posições terem sido fechadas
        _panic_in_progress = False
        logging.info("[PANIC-SYNC] Flag de pânico desativada. FLIP-5 retoma monitoramento normal.")


@app.on_event("shutdown")
async def shutdown_event():

    bridge.disconnect()


# [ANTIVIBE-CODING] - Variáveis Globais de Conexão Frontend

active_websockets: List[WebSocket] = []

latest_market_packet = None

# [FIX #PANIC-SYNC] Flag global: ativo durante panic_close_all para suprimir
# falsos disparos do FLIP-5, que detectaria os fechamentos do pânico como SL/TP externos.
_panic_in_progress: bool = False

# [FIX #DUAL-BOT-LOCK] Lock global compartilhado entre main.py e SniperBotWIN.
# Ambos verificam e atualizam esta variável para garantir que apenas UM sistema
# coloque ordens por vez, eliminando a race condition de ordens simultâneas.
_global_order_lock_until: float = 0.0
GLOBAL_ORDER_LOCK_SEC: float = 12.0  # 2s de margem extra sobre ORDER_LOCK_SEC=10s

# [FIX #CONSEC-LOSS-BREAKER] Circuit Breaker de Perdas Consecutivas.
# Cada SL externo detectado (FLIP-5) incrementa o contador.
# O cooldown cresce exponencialmente para prevenir reentradas destrutivas
# em downtrends acelerados (vide logs 14:56-14:57: 5 ordens em 71s).
# Tabela de cooldown: 1 SL=10s, 2 SL=60s, 3 SL=180s (3min), 4+ SL=600s (10min).
_consecutive_sl_hits: int = 0
_CONSEC_SL_COOLDOWNS: list = [10, 60, 180, 600]  # backoff exponencial em segundos


# [ANTIVIBE-CODING] - Background Task (Independente do WebSocket Cliente)


async def autonomous_bot_loop():
    global latest_market_packet
    global _global_order_lock_until  # [FIX #DUAL-BOT-LOCK]
    global _consecutive_sl_hits       # [FIX #CONSEC-LOSS-BREAKER]
    logging.info(
        "🚀 Background Task: Loop Autônomo inicializado e operando de forma independente."
    )

    try:
        # Configurações de Risco/Filtros (Failsafe)

        cvd_threshold = 1000

        safe_dist = 50.0

        # Loop Principal

        last_cleanup_time = 0

        last_trailing_check = 0

        # [FIX #FLIP-2] Cooldown pós-fechamento: evita flip-flop imediato de sinal
        last_close_time = 0  # timestamp do último fechamento de posição
        POST_CLOSE_COOLDOWN_SEC = 60.0  # [MELHORIA ABSOLUTA] 60s entre fechamento e próxima entrada para esfriar book

        # [FIX #FLIP-4] Lock de Ordem Ativa: bloqueia novas ordens por ORDER_LOCK_SEC
        # após qualquer place_limit_order ser enviada, INDEPENDENTE do positions_get.
        # Resolve a race condition de 72ms: limit é enviada mas positions_get ainda
        # retorna vazio até o MT5 confirmar internamente o fill (B3 netting).
        _order_lock_until = 0.0  # timestamp até o qual novas ordens estão bloqueadas
        ORDER_LOCK_SEC = 10.0    # 10s de lock após qualquer ordem enviada

        last_heartbeat = time_module.time()

        # Variáveis de Estado Persistentes no Loop

        symbol = "WIN$"  # Inicial

        # [FIX #FLIP-5] Rastreamento de tickets para detectar fechamentos externos (SL/TP MT5)
        # Quando um ticket some do positions_get sem o bot ter chamado close_position,
        # o cooldown e o lock são ativados imediatamente (SL/TP hit externo).
        # [FIX #FLIP5-INIT] Inicializa com posições JÁ abertas (se houver) para evitar
        # que uma posição pré-existente seja tratada como SL/TP externo na 1ª iteração.
        try:
            _init_positions = bridge.mt5.positions_get()
            _tracked_position_tickets: set = (
                set(p.ticket for p in _init_positions) if _init_positions else set()
            )
            if _tracked_position_tickets:
                logging.info(
                    f"[FLIP5-INIT] {len(_tracked_position_tickets)} posição(ões) pré-existente(s) carregada(s) no rastreador: {_tracked_position_tickets}"
                )
        except Exception:
            _tracked_position_tickets: set = set()

        # [FIX #TREND-ALIGN] Histórico de preços para detectar tendência recente
        # Bloqueia BUY em tendência de queda e SELL em tendência de alta (momentum)
        _price_history: list = []  # lista circular de preços recentes (max 10 ticks)
        _TREND_LOOKBACK = 8        # ticks analisados para verificar direção
        _TREND_MIN_MOVE = 40.0     # movímento mínimo em pontos para vetar direção

        # [FIX #ORDER-RETRY] Lock após falha de envio (evita spam a cada 400ms)
        ORDER_FAIL_LOCK_SEC = 5.0  # 5s de lock após qualquer falha de order_send

        returns_history = []

        prev_total_profit = 0.0

        current_day = datetime.now().day

        # Helper para carregar contexto em background (HFT Optimization)

        def load_market_context():

            ctx_path = os.path.join("data", "market_context.json")

            if os.path.exists(ctx_path):
                try:
                    with open(ctx_path, "r", encoding="utf-8") as f:
                        return json.load(f)

                except:
                    pass

            return {}

        # [HFT] Inicialização de Variáveis de Ciclo

        loop_count = 0

        data_60 = pd.DataFrame()

        multi_data = pd.DataFrame()

        account_info = None

        wen_ofi_val = 0.0

        cvd_val = 0.0  # [ANTIVIBE-CODING] Inicialização segura

        vol_reason = ""

        settlement_price = 0.0

        bluechips = {}  # Changed from pd.DataFrame() to dict for consistency with packet

        macro_change = {"score": 0.0, "reason": "No data"}

        daily_rates = None

        current_symbol = "WIN$"

        current_atr = 0.0

        avg_atr = 0.0

        ai_confidence = 0.0

        volatility = 0.0

        regime = 0

        prev_total_profit = 0.0

        prev_daily_realized = 0.0  # [REFINAMENTO 26/02] Tracking para Cooldown de IA

        session_limits = {
            "lower": 0,
            "upper": 0,
            "ref": 0,
        }  # [HFT v3] Persistent session limits

        partially_closed_tickets = set()  # [FASE 2] Evitar duplo-fechamento parcial

        # [FIX #MP-A] Inicialização segura para evitar UnboundLocalError no primeiro tick nulo
        last_price = 0.0
        last_valid_price = 0.0
        # Inicialização de sentimento para cobrir iterações antes do ciclo lento
        sentiment_score = 0.0
        headlines = []

        # [PAUSA PARCIAL] Controle de Volatilidade de Abertura (H-L Extremo)
        dia_pausado_vol = False
        hl_abertura_cache = None
        dia_abertura_cache = None

        logging.info("Entrando no loop principal do WebSocket...")

        while True:
            start_time = time_module.perf_counter()

            now = datetime.now()

            logging.debug(f"--- HEARTBEAT [{now}] ---")

            current_hour = now.hour

            logging.debug("Step 1: Check Conexao")

            # --- 0. CHECK CONEXíO MT5 ---

            if not bridge.check_connection():
                logging.warning("MT5 desconectado. Tentando reconectar...")

                # [FIX #MP-H] bridge.connect() e síncrona — envolve em thread para nao bloquear o event loop
                if await asyncio.to_thread(bridge.connect):
                    logging.info("Reconectado ao MT5 com sucesso!")

                else:
                    if time_module.time() - last_heartbeat > 30.0:
                        logging.error(
                            "Conexão MT5 perdida ou Terminal instável. Pausando execução..."
                        )

                    await asyncio.sleep(5)

                    last_heartbeat = time_module.time()

                    continue

            try:
                # --- 1. DETECÇíO DE SÍMBOLO (Ciclo Médio: 1s) ---

                if loop_count % 5 == 1 or not symbol:
                    logging.debug("Step 3: Obtendo simbolo")

                    new_symbol = await asyncio.to_thread(
                        bridge.get_current_symbol, "WIN"
                    )

                    if new_symbol and new_symbol != symbol:
                        logging.info(f"Símbolo detectado: {new_symbol}")

                        symbol = new_symbol

                        # Garante que o MT5 passe a gravar os ticks do ativo correlacionado inter-mercados

                        cross_sub = "WDO$" if "WIN" in symbol.upper() else "WIN$"

                        await asyncio.to_thread(
                            bridge.mt5.symbol_select, cross_sub, True
                        )

                        logging.info(
                            f"Símbolo Secundário (Arbitragem) inscrito no Market Watch: {cross_sub}"
                        )

                logging.debug(f"Step 4: Simbolo Ativo: {symbol}")

                # Se ainda não temos símbolo válido, espera e tenta de novo

                if not symbol:
                    logging.warning("Nenhum símbolo detectado. Aguardando...")

                    await asyncio.sleep(1)

                    continue

                # 1. Coleta de Dados Estratificada (HFT Optimization)

                # Ciclo Rápido (Sempre): Tick & Book

                # Ciclo Lento (A cada 5 iterações): OHLC Histórico, Multi-Ativo, Conta

                if "loop_count" not in locals():
                    loop_count = 0

                loop_count += 1

                # Determinar ativo correlacionado para Arbitragem Estatística (WIN vs WDO)
                cross_symbol = "WDO$" if "WIN" in symbol.upper() else "WIN$"

                # Coleta Ultra-Rápida (Prioridade 1) incluindo Cross-Asset
                t0 = time_module.perf_counter()
                tick_info, book, tns, cross_tns = await asyncio.gather(
                    asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol),
                    asyncio.to_thread(bridge.get_order_book, symbol),
                    asyncio.to_thread(
                        bridge.get_time_and_sales, symbol, n_ticks=20
                    ),  # Reduzido de 50 para 20
                    asyncio.to_thread(
                        bridge.get_time_and_sales, cross_symbol, n_ticks=20
                    ),  # Reduzido de 50 para 20
                )
                dt_gather_fast = (time_module.perf_counter() - t0) * 1000
                logging.debug(f"P1 Gather Time: {dt_gather_fast:.2f}ms")

                if tick_info:
                    last_price = tick_info.last
                    last_valid_price = last_price
                else:
                    last_price = last_valid_price
                    logging.warning("Tick Info falhou. Usando ultimo preco valido.")

                # Coleta Otimizada (HFT v2.1)
                # Somente o estritamente necessário para o sinal e execução entra no loop principal
                if loop_count % 5 == 1 or "data_60" not in locals():
                    # 1.1 Coleta Essencial (MT5 Rapid)
                    data_60, account_info, daily_realized = await asyncio.gather(
                        asyncio.to_thread(bridge.get_market_data, symbol, n_candles=150),
                        asyncio.to_thread(
                            bridge.get_account_info
                        ),  # Otimizado: USA CACHE
                        asyncio.to_thread(
                            bridge.get_daily_realized_profit
                        ),  # Otimizado: USA CACHE
                    )

                    # [REFINAMENTO 26/02] Detecção de Fechamento de Trade para Cooldown
                    if daily_realized != prev_daily_realized:
                        pnl_trade = daily_realized - prev_daily_realized
                        ai.record_result(pnl_trade)
                        prev_daily_realized = daily_realized

                    # [SOTA v2.1] Sincronização de 8 Canais (PatchTST Pipeline)
                    if data_60 is not None and not data_60.empty:
                        multi_data = data_60.copy()
                        # Preencher colunas de microestrutura para atingir os 8 canais requeridos
                        # Nota: CVD e OFI atuais são usados para preencher o histórico se ausente
                        if "cvd" not in multi_data.columns:
                            multi_data["cvd"] = (
                                cvd_val if "cvd_val" in locals() else 0.0
                            )
                        if "ofi" not in multi_data.columns:
                            multi_data["ofi"] = (
                                wen_ofi_val if "wen_ofi_val" in locals() else 0.0
                            )
                        if "volume_ratio" not in multi_data.columns:
                            multi_data["volume_ratio"] = 1.0

                        expected_cols = [
                            "open",
                            "high",
                            "low",
                            "close",
                            "tick_volume",
                            "cvd",
                            "ofi",
                            "volume_ratio",
                        ]
                        for col in expected_cols:
                            if col not in multi_data.columns:
                                multi_data[col] = 0.0
                        multi_data = multi_data[expected_cols]

                        # [FIX #COL-MISMATCH] Normaliza colunas para o contrato do ONNX v24 (8 canais)
                        # ONNX espera: cvd_normal, ofi_normal, trap_index
                        # multi_data tem: cvd, ofi, volume_ratio
                        cvd_scale = max(1.0, multi_data["cvd"].abs().max()) if "cvd" in multi_data.columns else 1.0
                        ofi_scale = max(1.0, multi_data["ofi"].abs().max()) if "ofi" in multi_data.columns else 1.0
                        multi_data["cvd_normal"] = (multi_data["cvd"] / cvd_scale) if "cvd" in multi_data.columns else 0.0
                        multi_data["ofi_normal"] = (multi_data["ofi"] / ofi_scale) if "ofi" in multi_data.columns else 0.0
                        multi_data["trap_index"] = multi_data.get("volume_ratio", pd.Series([1.0] * len(multi_data))) - 1.0

                        curr_len = len(multi_data)
                        if 0 < curr_len < 60:
                            needed = 60 - curr_len
                            padding = pd.concat([multi_data.iloc[[0]]] * needed)
                            multi_data = pd.concat([padding, multi_data]).reset_index(drop=True)
                            logging.info(f"💾 [DATA-SYNC] Padding de {needed} candles aplicado → total={len(multi_data)}")

                        multi_data = multi_data.tail(60)

                # 1.2 Atuallização via Cache (Background Worker) - SEMPRE ATUALIZAR (HFT Optimization)
                ctx = load_market_context()  # [ANTIVIBE-CODING]
                bluechips = ctx.get("bluechips", {})
                synthetic_idx = ctx.get("synthetic_index", 0.0)
                macro_change = ctx.get(
                    "macro", {"score": 0.0, "reason": "Dados de background"}
                )
                vol_expected = ctx.get("calendar", {}).get("volatility_expected", False)
                vol_reason = ctx.get("calendar", {}).get("reason", "")
                # [REVISÃO FINAL] Sincronia Multi-Ativo (WIN e WDO)
                inst_symbol = "WIN$" if ("WIN" in symbol or "IND" in symbol) else "WDO$"
                settlement_price = ctx.get("settlements", {}).get(
                    inst_symbol, ctx.get("settlement_price", 0.0)
                )
                real_vwap = ctx.get("vwaps", {}).get(inst_symbol, ctx.get("vwap", 0.0))

                # [PRO-ADJUST] Data Rescue: Se os dados de background falharem, tentar resgate direto
                if settlement_price <= 0 or real_vwap <= 0:
                    try:
                        sym = bridge.get_current_symbol(
                            "WIN" if "WIN" in inst_symbol else "WDO"
                        )
                        if settlement_price <= 0:
                            settlement_price = bridge.get_settlement_price(sym)
                        if real_vwap <= 0:
                            real_vwap = bridge.get_vwap(sym)
                    except:
                        pass

                # [MT5-INTEG] Novos dados de alta fidelidade publicados pelo MarketDataWorker
                htf_bias = ctx.get("htf_bias", "NEUTRAL")  # Viés tendência H1
                real_cvd_ctx = ctx.get("real_cvd", 0.0)  # CVD via ticks reais
                wdo_win_signal = ctx.get(
                    "wdo_win_signal", "NEUTRO"
                )  # Correlação WDO-WIN
                low_liquidity = ctx.get(
                    "low_liquidity", False
                )  # Flag de baixa liquidez
                commission_today = ctx.get("commission_today", 0.0)  # Custo real do dia

                if loop_count % 5 == 1:
                    # Multi-data fallback (usado para correlações/índices sintéticos)
                    # No HFT v2.1, o worker deveria prover isso, mas para manter compatibilidade:
                    if "multi_data" not in locals():
                        multi_data = (
                            pd.DataFrame()
                        )  # Será populado conforme necessário no futuro pelo worker

                    # Inicialização segura para evitar UnboundLocalError
                    if "sentiment_score" not in locals():
                        sentiment_score = 0.0
                        headlines = []  # Agora será uma lista de objetos ou strings

                    # 1.3 Coleta de Dados Macro/Sentimento (Background Files)
                    if loop_count % 20 == 1:
                        logging.debug(
                            "Iniciando leitura de Sentimento e Macro do Cache..."
                        )

                        # Carregar Sentimento do Arquivo (NewsSentimentWorker)
                        try:
                            sentiment_path = os.path.join("data", "news_sentiment.json")
                            if os.path.exists(sentiment_path):
                                with open(sentiment_path, "r", encoding="utf-8") as f:
                                    sent_data = json.load(f)
                                    sentiment_score = float(sent_data.get("score", 0.0))
                                    # PRIORIDADE: Lista de Notícias Detalhada. FALLBACK: Resumo fact_check.
                                    news = sent_data.get("news", [])
                                    headlines = (
                                        news
                                        if news
                                        else [
                                            sent_data.get(
                                                "fact_check",
                                                "Nenhum resumo de notícias disponível",
                                            )
                                        ]
                                    )
                                    ai.latest_sentiment_score = sentiment_score
                                    # [SOTA v5] Sincronizar Âncora de Sentimento no Ciclo Lento
                                    if last_price > 0:
                                        ai.update_sentiment_anchor(last_price)
                                    logging.debug(
                                        f"Sentimento carregado: {sentiment_score} | Notícias: {len(news)}"
                                    )
                            else:
                                # [MELHORIA-2] Fallback de Sentimento: CVD + Blue Chips
                                # Quando Gemini está indisponível (rate limit), usa dados locais
                                # real_cvd_ctx e synthetic_idx sempre definidos no escopo principal (linhas 758/730)
                                _cvd_proxy = float(real_cvd_ctx) if real_cvd_ctx else 0.0
                                _syn_proxy = float(synthetic_idx) if synthetic_idx else 0.0
                                # Normaliza CVD para [-1, 1] assumindo range máximo de 500 ticks
                                _cvd_norm = max(-1.0, min(1.0, _cvd_proxy / 500.0))
                                # Fallback ponderado (máx 0.30 de impacto no score, conservador)
                                sentiment_score = round((_cvd_norm * 0.4 + _syn_proxy * 0.6) * 0.30, 4)
                                headlines = ["[FALLBACK LOCAL] Sentimento calculado via CVD + Blue Chips (Gemini indisponível)"]
                                ai.latest_sentiment_score = sentiment_score
                                logging.warning(
                                    f"[SENTIMENTO-FALLBACK] Gemini indisponível. CVD={_cvd_proxy:.0f} Syn={_syn_proxy:.4f} → Score={sentiment_score:.4f}"
                                )
                        except Exception as e:
                            logging.error(f"Erro ao ler news_sentiment.json: {e}")
                            # [MELHORIA-2] Fallback por exceção (ex: arquivo corrompido)
                            # real_cvd_ctx e synthetic_idx sempre no escopo principal
                            _cvd_proxy = float(real_cvd_ctx) if real_cvd_ctx else 0.0
                            _cvd_norm = max(-1.0, min(1.0, _cvd_proxy / 500.0))
                            _syn_proxy = float(synthetic_idx) if synthetic_idx else 0.0
                            sentiment_score = round((_cvd_norm * 0.4 + _syn_proxy * 0.6) * 0.30, 4)
                            ai.latest_sentiment_score = sentiment_score
                            headlines = []

                        # Nota: Settlement e Volatilidade agora vêm do context_json atualizado pelo MarketDataWorker
                        daily_rates = await asyncio.to_thread(
                            bridge.mt5.copy_rates_from_pos,
                            symbol,
                            bridge.mt5.TIMEFRAME_D1,
                            0,
                            2,
                        )
                        logging.debug("Leitura de Cache Macro concluída.")

                    logging.debug(f"Coleta Lenta executada (Loop {loop_count})")

                # 1.1 Processamento de Conta e Risco
                if account_info is None:
                    if risk.dry_run:
                        # [SIMULATION] Create synthetic account if MT5 info is missing
                        account = {
                            "balance": 500.0,
                            "equity": 500.0 + daily_realized,
                            "profit": 0.0,
                            "margin": 0.0,
                            "margin_free": 500.0,
                            "currency": "BRL",
                        }
                    else:
                        logging.warning(
                            f"AGUARDE: account_info indisponível para {symbol}. Tentando novamente..."
                        )
                        await asyncio.sleep(1)
                        continue
                else:
                    account = account_info._asdict()

                floating_profit = account_info.profit if account_info else 0.0
                total_daily_profit = daily_realized + floating_profit

                # [SIMULATION] Override balance/equity with virtual values when in Dry Run
                if risk.dry_run:
                    virtual_capital = 500.0
                    account["balance"] = virtual_capital
                    account["equity"] = virtual_capital + total_daily_profit
                    logging.debug(
                        f"[SIM] Saldo Virtual Ativo: {account['balance']} | Equity: {account['equity']}"
                    )

                # Validação de Risco Diário
                risk_ok, risk_msg = risk.check_daily_loss(total_daily_profit)

                # Validação de Dados de Mercado (Fail-Safe)
                if not isinstance(data_60, pd.DataFrame):
                    logging.warning(
                        f"WAIT: data_60 não é DataFrame ({type(data_60)}). Ignorando iteração."
                    )
                    await asyncio.sleep(1)
                    continue

                if data_60.empty:
                    logging.warning(
                        f"WAIT: Dados Históricos vazios para {symbol}. Ignorando iteração."
                    )
                    await asyncio.sleep(1)
                    continue

                # --- ALPHA-X: PSR & RELIABILITY ---
                ai_predict_data = {}
                ai_confidence = 0.0
                volatility = current_atr / last_price if last_price > 0 else 0
                # Usamos um epsilon de 0.01 (B3 Tick Min) para evitar ruído estatístico
                pnl_diff = total_daily_profit - prev_total_profit
                if abs(pnl_diff) > 0.01:
                    returns_history.append(pnl_diff)
                    prev_total_profit = total_daily_profit

                # Manter histórico manejável (últimos 1000 retornos)
                if len(returns_history) > 1000:
                    returns_history.pop(0)

                reliability_ok, current_psr = risk.validate_reliability(returns_history)
                # ----------------------------------

                # Validação de Horário
                time_allowed = risk.is_time_allowed()

                latency_ms = (time_module.perf_counter() - start_time) * 1000
                if latency_ms > 300:  # Sincronizado com o alerta do Frontend
                    logging.warning(f"ALERTA DE ALTA LATÊNCIA: {latency_ms:.2f}ms")

                # Heartbeat Log (1 min)
                if time_module.time() - last_heartbeat > 60:
                    status_prefix = " [DRY-RUN]" if risk.dry_run else ""
                    logging.info(
                        f"HEARTBEAT{status_prefix}: {symbol} | PnL Dia: {total_daily_profit:.2f} | Risco: {'OK' if risk_ok else 'TRAVADO'} | Latência: {latency_ms:.1f}ms"
                    )
                    last_heartbeat = time_module.time()

                # 1.2 Calcular ATR (Average True Range)
                current_atr = 0.0
                avg_atr = 0.0
                if data_60 is not None and len(data_60) >= 28:
                    high_low = data_60["high"] - data_60["low"]
                    current_atr = high_low.rolling(window=14).mean().iloc[-1]
                    avg_atr = high_low.mean()
                # [PAUSA PARCIAL - 03/03/2026] VERIFICA VOLATILIDADE M1 NA ABERTURA (Live)
                hoje = now.date()
                if dia_abertura_cache != hoje:
                    dia_pausado_vol = False
                    hl_abertura_cache = None
                    dia_abertura_cache = hoje

                if hl_abertura_cache is None:
                    inicio_dia = datetime(now.year, now.month, now.day, 9, 0, 0)
                    try:
                        rates_hoje = await asyncio.to_thread(
                            bridge.mt5.copy_rates_range,
                            symbol,
                            bridge.mt5.TIMEFRAME_M1,
                            inicio_dia,
                            now,
                        )
                        if rates_hoje is not None and len(rates_hoje) >= 10:
                            df_hoje = pd.DataFrame(rates_hoje)
                            if "high" in df_hoje.columns and "low" in df_hoje.columns:
                                hl_10 = (
                                    df_hoje["high"].iloc[:10] - df_hoje["low"].iloc[:10]
                                )
                                hl_abertura_cache = float(hl_10.mean())
                                if hl_abertura_cache > 250.0:
                                    dia_pausado_vol = True
                                    add_operational_log(
                                        f"⚠️ [PAUSA VOLATILIDADE] H-L abert={hl_abertura_cache:.1f}pts (limiar=250).",
                                        "warning",
                                    )
                                    logging.warning(
                                        f"⚠️ [PAUSA VOLATILIDADE] H-L abertura={hl_abertura_cache:.1f}pts (limiar=250.0). Operações PAUSADAS."
                                    )
                            else:
                                logging.debug(
                                    "Início do dia aguardando colunas OHLC consistentes."
                                )
                    except Exception as e:
                        logging.error(f"Erro ao calcular H-L abertura (Live): {e}")

                if dia_pausado_vol and 0 < current_atr < 80.0:
                    dia_pausado_vol = False
                    add_operational_log(
                        f"✅ [PAUSA VOLATILIDADE] ATR={current_atr:.1f}pts normalizou. Retomando.",
                        "info",
                    )
                    logging.info(
                        f"✅ [PAUSA VOLATILIDADE] ATR={current_atr:.1f}pts normalizou. Retomando operações."
                    )

                # 2. Processar Lógica de IA e Risco
                logging.debug("Iniciando processamento de IA...")
                
                # [v24.5] Sinais SOTA de Microestrutura
                # OBI Ratio (1.0 = Neutro, 1.5 = Compradores, 0.7 = Vendedores)
                obi = micro_analyzer.calculate_pure_obi(book)
                # OFI Delta (Muda fluxo de ordens)
                wen_ofi_val = micro_analyzer.calculate_wen_ofi(book)
                # CVD Tape (Agressão Instantânea)
                cvd_val = micro_analyzer.calculate_cvd(tns)

                # Inferência SOTA Multi-Ativo (usa multi_data sincronizado)
                logging.debug("Executando inferência SOTA...")

                # [FIX #FAST-CYCLE-PAD] Garantir 60 linhas e colunas corretas em TODOS os ciclos
                sota_input = multi_data
                if sota_input is None or sota_input.empty or len(sota_input) < 60:
                    logging.debug(
                        f"SOTA: multi_data insuficiente ({len(sota_input) if sota_input is not None else 0} linhas). Gerando buffer de segurança."
                    )
                    if data_60 is not None and not data_60.empty:
                        base_val = data_60["close"].values
                        if len(base_val) < 60:
                            base_val = np.pad(base_val, (60 - len(base_val), 0), "edge")
                        else:
                            base_val = base_val[-60:]
                    else:
                        base_val = np.zeros(60)

                    # [FIX #COL-MISMATCH] Buffer de segurança já com nomes corretos do ONNX
                    cvd_norm = float(cvd_val) / max(1.0, abs(float(cvd_val)))
                    ofi_norm = float(obi) / max(1.0, abs(float(obi)))
                    sota_input = pd.DataFrame(
                        {
                            "open": base_val,
                            "high": base_val,
                            "low": base_val,
                            "close": base_val,
                            "tick_volume": np.zeros(60),
                            "cvd_normal": np.full(60, cvd_norm),
                            "ofi_normal": np.full(60, ofi_norm),
                            "trap_index": np.zeros(60),
                        }
                    )
                    logging.debug("[FAST-CYCLE-PAD] Buffer de segurança gerado com 60 candles.")

                ai_predict_data = await inference.predict(sota_input)
                ai_confidence = (
                    ai_predict_data.get("confidence", 0.0)
                    if isinstance(ai_predict_data, dict)
                    else 0.0
                )
                logging.debug(f"Inferência concluída. Confidence: {ai_confidence}")

                # Validação de Condição de Mercado (Estágio 2)
                volatility = (
                    data_60["close"].std()
                    if data_60 is not None and not data_60.empty
                    else 0.0
                )
                regime = ai.detect_regime(volatility, obi)
                # macro_change movido para o ciclo lento

                # [SOTA v5] Cálculo de Spread Normalizado (WIN: 5 pts = 1.0)
                live_spread = 1.0
                if tick_info:
                    live_spread = (
                        tick_info.ask - tick_info.bid
                    ) / 5.0  # Normalizado para escala SOTA v5

                # --- HFT v2.0: CVD Turbo (Otimizado: Usar tns do gather P1) ---
                # Reutilizando tns já capturado no início do loop para evitar nova chamada MT5
                cvd_val = micro_analyzer.calculate_cvd(tns)

                # Rastreamento de Agressão Cruzada (WDO/WIN) para Veto Inter-Mercados
                cross_cvd = (
                    micro_analyzer.calculate_cvd(cross_tns)
                    if cross_tns is not None
                    else 0.0
                )

                # Normalização da Agressão Cruzada para a IA (Threshold base do WDO = 50.0)
                # Assim, um CVD de 75 no WDO gera wdo_aggression_norm de 1.5, triggando o veto.
                wdo_aggression_norm = (
                    (cross_cvd / 50.0) if "WIN" in symbol.upper() else 0.0
                )

                # [ANTIVIBE-CODING] Override de Controle Manual de Notícias
                effective_sentiment = (
                    ai.latest_sentiment_score
                    if (getattr(risk, "enable_news_filter", True))
                    else 0.0
                )

                # Score Final (0-100) e Direção
                decision = ai.calculate_decision(
                    obi=obi,
                    sentiment=effective_sentiment,
                    score=ai_predict_data,
                    regime=regime,
                    atr=current_atr,
                    volatility=volatility,
                    hour=current_hour,
                    minute=now.minute,
                    current_price=last_price,
                    vwap=real_vwap,  # INJETANDO VWAP REAL
                    spread=live_spread,
                    wdo_aggression=wdo_aggression_norm,
                    loop_count=loop_count,
                )
                # [PAUSA PARCIAL] Bloqueio final antes de aplicar qualquer heurística
                if dia_pausado_vol:
                    decision["direction"] = "WAIT"
                    decision["reason"] = "ATR_DIA_PAUSADO"

                ai_total_score = decision["score"]
                ai_direction = decision["direction"]

                # --- ALPHA-X: OFI Ponderado (SOTA) ---
                # wen_ofi_val já calculado no topo para performance

                if wen_ofi_val > 500 and ai_direction == "BUY":
                    ai_total_score = min(100.0, ai_total_score + 4.0)
                elif wen_ofi_val < -500 and ai_direction == "SELL":
                    ai_total_score = min(100.0, ai_total_score + 4.0)

                # --- ALPHA-X: PSR RELIABILITY VETO ---
                if not reliability_ok and len(returns_history) >= 30:
                    logging.warning(
                        f"VETO ALPHA-X: PSR insuficiente ({current_psr:.4f})"
                    )
                    ai_total_score = 50.0
                    ai_direction = "NEUTRAL"

                cvd_threshold = 50.0 if "WDO" in symbol or "DOL" in symbol else 500.0

                if cvd_val > cvd_threshold and ai_direction == "BUY":
                    ai_total_score = min(100.0, ai_total_score + 5.0)
                    if ai_total_score > 80:
                        logging.info(
                            f"GATILHO CVD (+5.0): Fluxo Comprador Forte ({cvd_val:.0f})"
                        )
                elif cvd_val < -cvd_threshold and ai_direction == "SELL":
                    ai_total_score = min(100.0, ai_total_score + 5.0)
                    if ai_total_score > 80:
                        logging.info(
                            f"GATILHO CVD (+5.0): Fluxo Vendedor Forte ({cvd_val:.0f})"
                        )

                # --- FASE 5: SUITE DE MICROESTRUTURA HFT B3 ---
                current_hhmm = datetime.now().strftime("%H:%M")

                # 5.1 Bloqueio de Leilão
                auction_block = False
                if "09:55" <= current_hhmm <= "10:10":
                    auction_block = True
                    ai_total_score = 50.0
                    ai_direction = "NEUTRAL"

                # 5.2 NY Open Boost
                if "10:30" <= current_hhmm <= "11:30" and not auction_block:
                    ai_total_score = min(100.0, ai_total_score + 5.0)

                # 5.3 Defesa de Ajuste (Settlement Trap) - Otimizado: USA CACHE
                # settlement_price buscado no ciclo lento

                # Obter preço atual do TICK já capturado no gather (P1)
                # Reutilizando last_price já definido

                safe_dist = 3.0 if "WDO" in symbol or "DOL" in symbol else 50.0

                if settlement_price > 0 and not auction_block and last_price > 0:
                    dist = last_price - settlement_price

                    # [VWAP-FIX] Trava de Sanidade Dinâmica: Veto só se for plausível (4% do preço para WIN)
                    max_plausible_dist = (
                        50.0
                        if "WDO" in symbol or "DOL" in symbol
                        else (last_price * 0.04)
                    )

                    settlement_veto = False
                    settlement_msg = ""

                    if abs(dist) < max_plausible_dist:
                        # Veto COMPRA: Preço logo abaixo do ajuste (Resistência)
                        if ai_direction == "BUY" and -safe_dist < dist < 0:
                            settlement_veto = True
                            settlement_msg = f"Ajuste funcionando como Resistência (Dist: {dist:.1f})"
                        # Veto VENDA: Preço logo acima do ajuste (Suporte)
                        elif ai_direction == "SELL" and 0 < dist < safe_dist:
                            settlement_veto = True
                            settlement_msg = (
                                f"Ajuste funcionando como Suporte (Dist: {dist:.1f})"
                            )

                    if settlement_veto:
                        logging.warning(
                            f"DEFESA HFT: Veto de Ajuste ({settlement_price}). {settlement_msg}"
                        )
                        ai_total_score = 50.0
                        ai_direction = "NEUTRAL"
                        decision["score"] = 50.0
                        decision["direction"] = "NEUTRAL"
                        decision["veto"] = f"SETTLEMENT_VETO: {settlement_msg}"

                # 5b.1 Pinning (Opções)
                today_dt = datetime.now()

                if today_dt.weekday() == 4 and 15 <= today_dt.day <= 21:
                    if "10:00" <= current_hhmm <= "16:00" and regime == 0:
                        logging.info("ALERTA DE PINNING: Vencimento de Opções.")

                        ai_total_score = max(40.0, min(60.0, ai_total_score))

                # 5b.2 Gap Trap Protection - Otimizado: USA CACHE

                try:
                    # Reutilizar daily_rates buscado no ciclo lento

                    if daily_rates is not None and len(daily_rates) == 2:
                        prev_close = daily_rates[0]["close"]

                        today_open = daily_rates[1]["open"]

                        gap_pct = (
                            ((today_open - prev_close) / prev_close) * 100
                            if prev_close > 0
                            else 0
                        )

                        if gap_pct > 0.5 and cvd_val > 0 and ai_direction == "SELL":
                            logging.warning(
                                f"GAP TRAP VETO: Alta ({gap_pct:.2f}%) + Fluxo Comprador."
                            )

                            ai_total_score = 50.0

                            ai_direction = "NEUTRAL"
                            decision["score"] = 50.0
                            decision["direction"] = "NEUTRAL"
                            decision["veto"] = (
                                f"GAP_TRAP: Alta ({gap_pct:.1f}%) + Fluxo Comprador"
                            )
                        elif gap_pct < -0.5 and cvd_val < 0 and ai_direction == "BUY":
                            logging.warning(
                                f"GAP TRAP VETO: Baixa ({gap_pct:.2f}%) + Fluxo Vendedor."
                            )

                            ai_total_score = 50.0

                            ai_direction = "NEUTRAL"
                            decision["score"] = 50.0
                            decision["direction"] = "NEUTRAL"
                            decision["veto"] = (
                                f"GAP_TRAP: Baixa ({gap_pct:.1f}%) + Fluxo Vendedor"
                            )

                except Exception as gap_e:
                    logging.error(f"Erro Gap Trap: {gap_e}")

                # --- FASE 3: HARD VETO (Anti-Alucinação) ---

                veto_active = False

                veto_reason = ""

                if ai_direction == "BUY" and cvd_val < -cvd_threshold:
                    veto_active = True

                    veto_reason = f"DIVERGÊNCIA: IA Compra vs CVD Venda ({cvd_val:.0f})"

                elif ai_direction == "SELL" and cvd_val > cvd_threshold:
                    veto_active = True

                    veto_reason = f"DIVERGÊNCIA: IA Venda vs CVD Compra ({cvd_val:.0f})"

                # Blue Chips Influence - Otimizado: USA CACHE

                # bluechips buscado no ciclo lento

                # synthetic_idx = micro_analyzer.calculate_synthetic_index(bluechips) # [DÉJÀ VU] Comentado para usar o valor oficial do MarketDataWorker

                # Se Blue Chips estão fortemente contra, reduz o score
                if ai_direction == "BUY" and synthetic_idx < -0.05:
                    if getattr(risk, "enable_macro_filter", True):
                        penalty = (
                            abs(synthetic_idx) * 100
                        )  # ex: 0.1% contra -> -10 pontos
                        ai_total_score = max(50.0, ai_total_score - penalty)
                        if synthetic_idx < -0.2:  # Hard Veto se queda for > 0.2%
                            veto_active = True
                            veto_reason = f"VETO QUANT EXTREMO: Blue Chips Caindo Forte ({synthetic_idx:.2f}%)"
                elif ai_direction == "SELL" and synthetic_idx > 0.05:
                    if getattr(risk, "enable_macro_filter", True):
                        penalty = abs(synthetic_idx) * 100
                        ai_total_score = max(50.0, ai_total_score - penalty)
                        if synthetic_idx > 0.2:  # Hard Veto se alta for > 0.2%
                            veto_active = True
                            veto_reason = f"VETO QUANT EXTREMO: Blue Chips Subindo Forte ({synthetic_idx:.2f}%)"

                if veto_active:
                    logging.warning(f"🛑 {veto_reason}")

                    ai_total_score = 50.0

                    ai_direction = "NEUTRAL"
                    decision["score"] = 50.0
                    decision["direction"] = "NEUTRAL"
                    decision["veto"] = veto_reason

                # --- FASE 5b: FILTROS HTF E LIQUIDEZ [MT5-INTEG] ---

                # [MT5-INTEG #3] Filtro HTF H1: reduz score quando sinal vai contra tendência horária
                if htf_bias == "BULL" and ai_direction == "SELL":
                    ai_total_score = max(50.0, ai_total_score - 3.0)
                    logging.debug("[HTF-FILTRO] H1 BULL, sinal SELL penalizado -3.0pts")
                elif htf_bias == "BEAR" and ai_direction == "BUY":
                    ai_total_score = max(50.0, ai_total_score - 3.0)
                    logging.debug("[HTF-FILTRO] H1 BEAR, sinal BUY penalizado -3.0pts")

                # [MT5-INTEG #6] Filtro de Baixa Liquidez: bloqueia entrada em dias rasos
                if low_liquidity and not auction_block:
                    logging.warning(
                        "[LIQUIDEZ] Volume D1 abaixo de 60% da media. Operacao bloqueada por baixa liquidez."
                    )
                    add_operational_log(
                        "VETO: Baixa Liquidez D1 — Volume abaixo de 60% da media 10D",
                        "warning",
                    )
                    ai_total_score = 50.0
                    ai_direction = "NEUTRAL"
                    decision["score"] = 50.0
                    decision["direction"] = "NEUTRAL"
                    decision["veto"] = "BAIXA_LIQUIDEZ_D1"

                # [MT5-INTEG #4] Correlação WDO-WIN: sinal DIVERGENTE reduz score
                if wdo_win_signal == "DIVERGENTE" and ai_direction in ["BUY", "SELL"]:
                    ai_total_score = max(50.0, ai_total_score - 4.0)
                    logging.debug(
                        "[WDO-WIN] Correlacao DIVERGENTE. Score penalizado -4.0pts"
                    )

                # [MT5-INTEG #2] CVD Real: se disponivel e a favor, reforca confirmacao
                if abs(real_cvd_ctx) > 50:
                    if (ai_direction == "BUY" and real_cvd_ctx > 0) or (
                        ai_direction == "SELL" and real_cvd_ctx < 0
                    ):
                        ai_total_score = min(100.0, ai_total_score + 2.0)
                        logging.debug(
                            f"[CVD-REAL] Tick CVD confirma direcao ({real_cvd_ctx:.0f}). +2.0pts"
                        )

                # --- FIM DOS FILTROS HTF E LIQUIDEZ ---

                market_condition = risk.validate_market_condition(
                    symbol, regime, current_atr, avg_atr, spread=live_spread
                )

                market_ok = market_condition["allowed"]

                # --- RL SHADOW MODE ---

                try:
                    rl_state = [
                        current_atr,
                        obi,
                        effective_sentiment,
                        ai_confidence,
                        volatility,
                        cvd_val,
                        synthetic_idx,
                    ]

                    action, log_prob = rl_agent.select_action(rl_state)

                    actions_map = {0: "BUY", 1: "SELL", 2: "HOLD"}

                    suggested = actions_map.get(action, "UNKNOWN")

                    if ai_total_score > 70:
                        logging.info(
                            f"🤖 [RL SHADOW] Sugestão: {suggested} | Decisão Atual: {ai_direction}"
                        )

                except Exception as rl_e:
                    logging.debug(f"Erro RL Shadow: {rl_e}")

                # --- [FIX #FLIP-5 v2] DETECÇÃO DE FECHAMENTO EXTERNO — RODA A CADA TICK ---
                # CORRIGIDO: antes estava dentro do bloco de 1s (trailing check),
                # causando janela de até 1s onde FLIP-3 via positions=0 e liberava nova entrada.
                # Agora roda a cada ~250ms, ANTES do FLIP-3, garantindo lock imediato pós-SL/TP.
                try:
                    _tick_positions = await asyncio.to_thread(
                        bridge.mt5.positions_get, symbol=symbol
                    )
                    _current_tickets = (
                        set(p.ticket for p in _tick_positions) if _tick_positions else set()
                    )
                    _externally_closed = _tracked_position_tickets - _current_tickets
                    # [FIX #PANIC-SYNC] Não dispara lock/cooldown se pânico estiver em andamento:
                    # o desaparecimento das posições é INTENCIONAL (fechamento pelo próprio bot).
                    if _externally_closed and not _panic_in_progress:
                        last_close_time = time_module.time()  # [FIX #FLIP-2]

                        # [FIX #CONSEC-LOSS-BREAKER] Backoff exponencial por SL consecutivo.
                        # Cada stop externo em sequência aumenta o cooldown:
                        # 1° SL=10s, 2°=60s, 3°=180s (3min), 4°+=600s (10min).
                        _consecutive_sl_hits = min(_consecutive_sl_hits + 1, len(_CONSEC_SL_COOLDOWNS))
                        _sl_cooldown = _CONSEC_SL_COOLDOWNS[_consecutive_sl_hits - 1]
                        _order_lock_until = time_module.time() + _sl_cooldown
                        _global_order_lock_until = time_module.time() + _sl_cooldown + 2.0

                        for _tk in _externally_closed:
                            logging.warning(
                                f"🚨 [FLIP-5 v3] Ticket #{_tk} fechado por SL/TP externo. "
                                f"SL consecutivo #{_consecutive_sl_hits}. "
                                f"Lock=**{_sl_cooldown:.0f}s** (backoff exponencial). "
                                f"Próximo SL locks: {_CONSEC_SL_COOLDOWNS}"
                            )
                    elif _externally_closed and _panic_in_progress:
                        logging.debug(
                            f"[FLIP-5] Tickets {_externally_closed} fechados pelo PÂNICO. Lock suprimido."
                        )
                    _tracked_position_tickets = _current_tickets
                except Exception as _flip5_err:
                    logging.debug(f"[FLIP-5] Erro em tick-level positions_get: {_flip5_err}")


                # --- TRAILING STOP (1s Check) ---

                if time_module.time() - last_trailing_check > 1.0:
                    last_trailing_check = time_module.time()

                    try:
                        # Reutiliza _tick_positions capturado acima pelo FLIP-5 (evita 2ª chamada MT5)
                        # [FIX #DIR-BUG] dir() retorna atributos do objeto/módulo, NÃO variáveis locais de coroutine.
                        # locals() é o método correto para verificar se a variável existe no escopo atual.
                        positions = _tick_positions if '_tick_positions' in locals() else await asyncio.to_thread(
                            bridge.mt5.positions_get, symbol=symbol
                        )

                        # _tracked_position_tickets já atualizado pelo FLIP-5 acima
                        _current_tickets = (
                            set(p.ticket for p in positions) if positions else set()
                        )

                        if positions:
                            for pos in positions:
                                # --- ALPHA-X: TRIPLE BARRIER (TIME EXIT) ---

                                # Se a posição estiver aberta há mais de 15 minutos e não atingiu SL/TP, fechamos.

                                # Pos.time é em segundos (timestamp) do broker MT5.
                                # [FIX #TIMEZONE-BUG] O servidor é UTC-3. time_module.time() é UTC. 
                                # A divergência era de 180 minutos. Puxando tick.time temos referencial seguro.
                                current_tick_pos = await asyncio.to_thread(
                                    bridge.mt5.symbol_info_tick, pos.symbol
                                )
                                pos_now_ts = current_tick_pos.time if current_tick_pos else int(time_module.time() - 10800)
                                
                                elapsed_sec = pos_now_ts - pos.time

                                # 🛡️ [FIX CRÍTICO] GRACE PERIOD (Escudo Anti-Whipsaw 50ms)
                                # Bloqueia qualquer fechamento por Velocity Limit, Time Barrier ou Trailing Stop
                                # nos primeiros 3 segundos. Isso impede que o spread inicial negativo
                                # seja interpretado como exaustão de lucro/momento.
                                if elapsed_sec < 3.0:
                                    continue

                                pos_age_min = elapsed_sec / 60

                                if pos_age_min > 15.0:
                                    logging.warning(
                                        f"SAÍDA POR TEMPO ALPHA-X: Posição {pos.ticket} aberta há {pos_age_min:.1f} min. Fechando a mercado."
                                    )

                                    # [FIX #FLIP-5-SYNC] Remove ticket ANTES de close_position.
                                    # Evita que FLIP-5 (próxima iteração) detecte o desaparecimento
                                    # como fechamento *externo* e dispare lock duplo redundante.
                                    _tracked_position_tickets.discard(pos.ticket)

                                    await asyncio.to_thread(
                                        bridge.close_position, pos.ticket
                                    )

                                    last_close_time = pos_now_ts  # [FIX #FLIP-2] Cooldown
                                    _order_lock_until = pos_now_ts + ORDER_LOCK_SEC  # [FIX #FLIP-4] Lock
                                    _global_order_lock_until = pos_now_ts + GLOBAL_ORDER_LOCK_SEC  # [FIX #DUAL-BOT-LOCK]
                                    
                                    # O lucro neste ponto precisa ser calculado se quisermos o reset
                                    current_price = last_price
                                    if pos.type == bridge.mt5.POSITION_TYPE_BUY:
                                        profit_pts = current_price - pos.price_open
                                    else:
                                        profit_pts = pos.price_open - current_price

                                    # [FIX #CONSEC-LOSS-BREAKER] Reset se saída foi lucrativa
                                    if profit_pts > 0:
                                        _consecutive_sl_hits = 0
                                        logging.info("✅ [CONSEC-RESET] Operação lucrativa. Contador de SL zerado.")
                                    logging.info(f"🔒 [ALPHA-X] Lock local+global ({ORDER_LOCK_SEC:.0f}s/{GLOBAL_ORDER_LOCK_SEC:.0f}s) ativado após fechamento por tempo.")

                                    continue

                                is_wdo = "WDO" in symbol or "DOL" in symbol

                                # Gatilho e Step puxados do RiskManager (v22 Gold)

                                trigger_pts = (
                                    risk.trailing_trigger if not is_wdo else 5.0
                                )

                                # [MELHORIA-4] Step proporcional ao ATR (25% do ATR atual)
                                # Era fixo em 5 pts (4-6% do ATR), causando saída prematura por ruído normal
                                # Range normal do WIN: ATR 80-120 pts → Step 20-30 pts (adequado)
                                _atr_ref = float(current_atr) if current_atr and current_atr > 0 else 80.0
                                step_pts = max(10.0, round(_atr_ref * 0.25)) if not is_wdo else 2.0

                                current_price = last_price

                                # Cálculo de lucro atual para o Tick
                                if pos.type == bridge.mt5.POSITION_TYPE_BUY:
                                    profit_pts = current_price - pos.price_open
                                else:
                                    profit_pts = pos.price_open - current_price

                                # --- FASE 2: VELOCITY LIMIT ---

                                is_velocity_limit, vel_reason = (
                                    risk.check_velocity_limit(profit_pts, elapsed_sec)
                                )

                                if is_velocity_limit:
                                    logging.warning(
                                        f"⚡ SAÍDA POR LIMITE DE VELOCIDADE: Posição {pos.ticket} fechada precocemente devido a exaustão. Motivo: {vel_reason}"
                                    )

                                    # [FIX #FLIP-5-SYNC] Mesma correção do ALPHA-X: remove ticket
                                    # antes de fechar para não gerar lock duplo via FLIP-5.
                                    _tracked_position_tickets.discard(pos.ticket)

                                    await asyncio.to_thread(
                                        bridge.close_position, pos.ticket
                                    )

                                    last_close_time = time_module.time()  # [FIX #FLIP-2] Cooldown
                                    _order_lock_until = time_module.time() + ORDER_LOCK_SEC  # [FIX #FLIP-4] Lock
                                    _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC  # [FIX #DUAL-BOT-LOCK]
                                    logging.info(f"⚡ [VELOCITY] Lock local+global ({ORDER_LOCK_SEC:.0f}s/{GLOBAL_ORDER_LOCK_SEC:.0f}s) ativado após fechamento por exaustão.")

                                    continue

                                # --- FASE 2: SCALED EXITS (PARTIAL TAKE PROFIT) ---

                                if pos.ticket not in partially_closed_tickets:
                                    if (
                                        profit_pts >= risk.partial_profit_points
                                        and pos.volume > risk.partial_volume
                                    ):
                                        logging.info(
                                            f"🎯 LUCRO PARCIAL: Atingiu {profit_pts:.1f} pts. Fechando {risk.partial_volume} lotes de {pos.volume}."
                                        )

                                        success = await asyncio.to_thread(
                                            bridge.close_partial_position,
                                            pos.ticket,
                                            risk.partial_volume,
                                        )

                                        if success:
                                            partially_closed_tickets.add(pos.ticket)
                                            # [FIX] Parcial também atualiza last_close_time:
                                            # FLIP-5 detecta por ticket (ticket permanece),
                                            # mas last_close_time evita nova entrada total após saida parcial.
                                            last_close_time = time_module.time()
                                            logging.info(f"🎯 [PARCIAL] last_close_time atualizado ({risk.partial_volume} lotes fechados).")

                                            # Break-even automático pós parcial

                                            if (
                                                pos.type == bridge.mt5.POSITION_TYPE_BUY
                                                and pos.sl < pos.price_open
                                            ):
                                                await asyncio.to_thread(
                                                    bridge.update_sltp,
                                                    pos.ticket,
                                                    pos.price_open,
                                                    pos.tp,
                                                )

                                                logging.info(
                                                    f"🛡️ BREAKEVEN ACIONADO (Pos Parcial BUY): SL em {pos.price_open}"
                                                )

                                            elif (
                                                pos.type
                                                == bridge.mt5.POSITION_TYPE_SELL
                                                and (
                                                    pos.sl > pos.price_open
                                                    or pos.sl == 0
                                                )
                                            ):
                                                await asyncio.to_thread(
                                                    bridge.update_sltp,
                                                    pos.ticket,
                                                    pos.price_open,
                                                    pos.tp,
                                                )

                                                logging.info(
                                                    f"🛡️ BREAKEVEN ACIONADO (Pos Parcial SELL): SL em {pos.price_open}"
                                                )

                                        continue

                                # --- Lógica Original Trailing Stop & Break Even ---

                                be_pts = risk.be_trigger if pos.type == bridge.mt5.POSITION_TYPE_BUY else getattr(risk, 'be_sell_trigger', risk.be_trigger)

                                if pos.type == bridge.mt5.POSITION_TYPE_BUY:
                                    if profit_pts >= trigger_pts:
                                        new_sl = current_price - step_pts

                                        if new_sl > pos.sl:
                                            new_sl = risk._apply_anti_violinada(
                                                symbol, new_sl, "buy"
                                            )

                                            await asyncio.to_thread(
                                                bridge.update_sltp,
                                                pos.ticket,
                                                new_sl,
                                                pos.tp,
                                            )

                                            logging.info(
                                                f"TRAILING STOP (BUY): SL movido para {new_sl}"
                                            )
                                    elif profit_pts >= be_pts and pos.sl < pos.price_open:
                                        await asyncio.to_thread(
                                            bridge.update_sltp,
                                            pos.ticket,
                                            pos.price_open,
                                            pos.tp,
                                        )
                                        logging.info(f"🛡️ BREAKEVEN ACIONADO ANTES DO TRAILING (BUY): SL em {pos.price_open}")

                                elif pos.type == bridge.mt5.POSITION_TYPE_SELL:
                                    if profit_pts >= trigger_pts:
                                        new_sl = current_price + step_pts

                                        if pos.sl == 0 or new_sl < pos.sl:
                                            new_sl = risk._apply_anti_violinada(
                                                symbol, new_sl, "sell"
                                            )

                                            await asyncio.to_thread(
                                                bridge.update_sltp,
                                                pos.ticket,
                                                new_sl,
                                                pos.tp,
                                            )

                                            logging.info(
                                                f"TRAILING STOP (SELL): SL movido para {new_sl}"
                                            )
                                    elif profit_pts >= be_pts and (pos.sl > pos.price_open or pos.sl == 0):
                                        await asyncio.to_thread(
                                            bridge.update_sltp,
                                            pos.ticket,
                                            pos.price_open,
                                            pos.tp,
                                        )
                                        logging.info(f"🛡️ BREAKEVEN ACIONADO ANTES DO TRAILING (SELL): SL em {pos.price_open}")

                    except Exception as e:
                        logging.error(f"Erro no Trailing/Time Stop: {e}")

                if risk.should_force_close():
                    await panic_close_all()
                    logging.warning("Check Force Close: 17:50 atingido.")

                # --- LÓGICA DE DECISÃO DE TRADE ---
                # [MELHORIA-2] Threshold relaxado para 65% durante Modo Momentum Pós-Evento
                if getattr(risk, "post_event_momentum", False):
                    _threshold_buy = 65  # Mais permissivo nos 10 min pós-evento
                    _threshold_sell = 35
                    logging.debug(
                        f"⚡ [MOMENTUM] Threshold relaxado: Buy>={_threshold_buy} / Sell<={_threshold_sell}"
                    )
                else:
                    # [MELHORIA-ELITE] Threshold Adaptativo por Regime
                    if regime == 0:  # LATERAL: Exige maior assertividade (+5 pontos)
                        _threshold_buy = 85
                        _threshold_sell = 15
                        logging.debug("🛑 [REGIME LATERAL] Threshold elevado para 85/15.")
                    else:
                        _threshold_buy = 80  # [SNIPER MODE] Padrao V22
                        _threshold_sell = 20

                is_threshold_met = (
                    ai_total_score >= _threshold_buy
                    or ai_total_score <= _threshold_sell
                )

                # [FIX #FLIP-2] Cooldown pós-fechamento
                _cooldown_remaining = POST_CLOSE_COOLDOWN_SEC - (time_module.time() - last_close_time)
                if _cooldown_remaining > 0:
                    logging.debug(
                        f"⏳ [COOLDOWN] Aguardando {_cooldown_remaining:.1f}s antes da próxima entrada."
                    )

                # [FIX #FLIP-3 v2] Guard de Posição Aberta — FAIL-SAFE
                # CORRIGIDO: Era fail-open (se positions_get falhasse → permitia entrada)
                # Agora: fail-safe (se falhar → bloqueia entrada por segurança)
                try:
                    _open_positions = await asyncio.to_thread(
                        bridge.mt5.positions_get, symbol=symbol
                    )
                    # MT5 pode retornar None, () ou tuple com posições
                    _has_open_position = bool(_open_positions and len(_open_positions) > 0)

                    # Fallback: se retornou vazio mas o lock ainda está ativo (ordem recém enviada),
                    # assume que a posição ainda não apareceu no positions_get por latência MT5
                    if not _has_open_position and _order_lock_until > time_module.time():
                        _has_open_position = True  # Conservador: lock ativo = posição provável
                        logging.debug("[FLIP-3] Lock ativo → assume posição aberta por segurança.")

                except Exception as _pos_err:
                    # FAIL-SAFE: qualquer erro em positions_get → BLOQUEIA entrada
                    _has_open_position = True
                    logging.warning(
                        f"⚠️ [FLIP-3 FAIL-SAFE] positions_get falhou ({_pos_err}). Bloqueando entrada por segurança."
                    )

                if _has_open_position:
                    logging.info(  # INFO ao invés de DEBUG para aparecer nos logs
                        f"🛑 [FLIP-3 GUARD] Posição aberta detectada em {symbol}. Nova entrada bloqueada."
                    )


                # [FIX #FLIP-4] Verificar lock de ordem ativa
                _order_locked = time_module.time() < _order_lock_until
                if _order_locked:
                    _lock_remaining = _order_lock_until - time_module.time()
                    logging.debug(
                        f"🔒 [FLIP-4 LOCK] Ordem em trânsito. Bloqueando nova entrada por {_lock_remaining:.1f}s."
                    )

                # [FIX #TREND-ALIGN] Registrar preço atual no histórico circular
                _price_history.append(float(last_price))
                if len(_price_history) > 10:
                    _price_history.pop(0)

                # [FIX #TREND-ALIGN] Filtro de Alinhamento de Tendência
                # Veta BUY se preço caiu _TREND_MIN_MOVE pts nos últimos _TREND_LOOKBACK ticks
                # Veta SELL se preço subiu _TREND_MIN_MOVE pts nos últimos _TREND_LOOKBACK ticks
                _trend_veto = False
                if len(_price_history) >= _TREND_LOOKBACK and is_threshold_met:
                    _recent = _price_history[-_TREND_LOOKBACK:]
                    _price_delta = _recent[-1] - _recent[0]
                    if ai_direction == "BUY" and _price_delta <= -_TREND_MIN_MOVE:
                        _trend_veto = True
                        logging.info(
                            f"🚧 [TREND-ALIGN] BUY vetado: preço caiu {abs(_price_delta):.0f}pts "
                            f"nos últimos {_TREND_LOOKBACK} ticks ({_recent[0]:.0f} → {_recent[-1]:.0f})"
                        )
                    elif ai_direction == "SELL" and _price_delta >= _TREND_MIN_MOVE:
                        _trend_veto = True
                        logging.info(
                            f"🚧 [TREND-ALIGN] SELL vetado: preço subiu {_price_delta:.0f}pts "
                            f"nos últimos {_TREND_LOOKBACK} ticks ({_recent[0]:.0f} → {_recent[-1]:.0f})"
                        )

                # [FIX #DUAL-BOT-LOCK] Verificar se o Sniper (ou outra instância) não bloqueou o sistema
                _global_locked = time_module.time() < _global_order_lock_until
                if _global_locked:
                    _gl_remaining = _global_order_lock_until - time_module.time()
                    logging.debug(f"🔒 [DUAL-BOT-LOCK] Sistema bloqueado pelo lock global por {_gl_remaining:.1f}s.")

                if (
                    risk.allow_autonomous
                    and is_threshold_met
                    and risk_ok
                    and market_ok
                    and time_allowed
                    and _cooldown_remaining <= 0  # [FIX #FLIP-2] Bloqueia re-entrada durante cooldown
                    and not _has_open_position    # [FIX #FLIP-3] Bloqueia se já há posição aberta
                    and not _order_locked         # [FIX #FLIP-4] Bloqueia durante lock de ordem em trânsito
                    and not _trend_veto           # [FIX #TREND-ALIGN] Bloqueia contra tendência recente
                    and not _global_locked        # [FIX #DUAL-BOT-LOCK] Bloqueia se Sniper atuou recentemente
                ):
                    if ai_direction in ["BUY", "SELL"]:
                        side = "buy" if ai_direction == "BUY" else "sell"

                        macro_ok, macro_msg = risk.check_macro_filter(
                            side, macro_change.get("score", 0.0)
                        )

                        if not macro_ok:
                            logging.warning(f"AUTÔNOMO BLOQUEADO: {macro_msg}")

                        else:
                            # EXECUÇÃO AUTORIZADA

                            brk = decision.get("breakdown", {})

                            side_pt = "COMPRA" if side == "buy" else "VENDA"
                            log_msg = (
                                f"🚀 [SCORE MACRO: {ai_total_score:.1f}] Disparando {side_pt} | "
                                f"Sent: {brk.get('sentiment_contribution', 0) * 100:+.1f} | "
                                f"Blue: {synthetic_idx * 100:+.2f}% | "
                                f"OBI: {brk.get('obi_contribution', 0) * 100:+.1f}"
                            )

                            logging.info(log_msg)

                            is_sniper = False

                            is_high_conviction = (
                                ai_total_score > 90 or ai_total_score < 10
                            )

                            if is_high_conviction:
                                if (side == "buy" and cvd_val >= 300) or (
                                    side == "sell" and cvd_val <= -300
                                ):
                                    is_sniper = True

                            if is_sniper:
                                order_type = (
                                    bridge.mt5.ORDER_TYPE_BUY_LIMIT
                                    if side == "buy"
                                    else bridge.mt5.ORDER_TYPE_SELL_LIMIT
                                )

                                # [FIX #PRE-ORDER-GATE] Verificacao live de posicao ANTES de enviar.
                                # _has_open_position pode estar stale se fill ocorreu dentro do ciclo.
                                _live_positions = await asyncio.to_thread(
                                    bridge.mt5.positions_get, symbol=symbol
                                )
                                if _live_positions:
                                    logging.warning(
                                        f"[PRE-ORDER-GATE] Posicao JA ABERTA detectada live "
                                        f"({len(_live_positions)} pos). Abortando Sniper. "
                                        f"Tickets: {[p.ticket for p in _live_positions]}"
                                    )
                                    add_operational_log(
                                        "[PRE-ORDER-GATE] Entrada bloqueada: posicao aberta em tempo real.",
                                        "warning",
                                    )
                                    continue

                                logging.info("MODO SNIPER: ORDEM LIMITE AGRESSIVA")

                                tick_info = await asyncio.to_thread(
                                    bridge.mt5.symbol_info_tick, symbol
                                )

                                if tick_info is None:
                                    logging.warning("[SNIPER] symbol_info_tick retornou None. Abortando ordem.")
                                    continue

                                current_order_price = (
                                    tick_info.ask if side == "buy" else tick_info.bid
                                )

                                point_value = (
                                    10.0 if "WDO" in symbol or "DOL" in symbol else 0.20
                                )

                                # [MT5-INTEG #5] Usa equity no sizing quando ha pos. aberta
                                sizing_balance = (
                                    account.get("equity", account["balance"])
                                    if account.get("equity", 0) > 0
                                    else account["balance"]
                                )
                                sota_lots = risk.calculate_volatility_sizing(
                                    sizing_balance, current_atr, point_value
                                )

                                # [SOTA v5] Aplicar Multiplicador de Lotes da IA (Exposição Parcial)

                                ai_multiplier = decision.get("lot_multiplier", 1.0)

                                tp_multiplier = decision.get("tp_multiplier", 1.0)

                                final_lots = max(1, int(sota_lots * ai_multiplier))

                                params = risk.get_order_params(
                                    symbol,
                                    order_type,
                                    current_order_price,
                                    final_lots,
                                    current_atr=current_atr,
                                    regime=regime,
                                    tp_multiplier=tp_multiplier,
                                )

                                params["symbol"] = symbol

                                params["comment"] = "SNIPER AUTOMÁTICO"

                                # 🛡️ [FIX CRÍTICO] PRE-LOCK: Trava o sistema local e globalmente ANTES 
                                # de ceder o processamento para a rede, bloqueando o SniperBotWIN.
                                _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC

                                if risk.dry_run:
                                    side_pt = "COMPRA" if side == "buy" else "VENDA"
                                    logging.warning(
                                        f"DRY-RUN: Simulando Ordem SNIPER LIMIT {side_pt} de {final_lots} lotes @ {current_order_price}"
                                    )

                                    class MockResult:
                                        retcode = bridge.mt5.TRADE_RETCODE_DONE

                                        price = current_order_price

                                        order = 888888

                                    result = MockResult()

                                else:
                                    result = await asyncio.to_thread(
                                        bridge.place_limit_order,
                                        symbol,
                                        order_type,
                                        current_order_price,
                                        final_lots,
                                        sl=params["sl"],
                                        tp=params["tp"],
                                        comment="SNIPER_LIMITE_AUTO",
                                    )

                                if (
                                    result
                                    and result.retcode == bridge.mt5.TRADE_RETCODE_DONE
                                ):
                                    # [FIX #FLIP-4] Ativar lock imediatamente após ordem aceita
                                    _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                    # [FIX #DUAL-BOT-LOCK] Propagar lock para o Sniper também
                                    _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC
                                    logging.info(
                                        f"🔒 [FLIP-4+DUAL] Lock local+global ativo: {ORDER_LOCK_SEC:.0f}s/{ GLOBAL_ORDER_LOCK_SEC:.0f}s (Sniper ticket={result.order})"
                                    )
                                    order_ticket = result.order

                                    mode_tag = (
                                        "SIMULATION_SNIPER"
                                        if risk.dry_run
                                        else "AUTO_SNIPER"
                                    )

                                    filled = False

                                    # [DRY-RUN FIX] Em simulação, curto-circuita o polling real.
                                    # Tickets fictícios (888888) jamais existem no MT5 real.
                                    if risk.dry_run:
                                        filled = True
                                        logging.warning(
                                            f"DRY-RUN: Sniper simulado como FILLED (ticket fictício={order_ticket})"
                                        )
                                    else:
                                        # [FIX #POLL-INSTANT] Verifica IMEDIATAMENTE antes do 1º sleep
                                        status_imediato = await asyncio.to_thread(
                                            bridge.check_order_status, order_ticket
                                        )
                                        if status_imediato == "FILLED":
                                            filled = True
                                            logging.info(
                                                f"[POLL-INSTANT] Sniper {order_ticket} já preenchido antes do 1º sleep!"
                                            )

                                        if not filled:
                                            for _ in range(6):
                                                await asyncio.sleep(0.5)

                                                status = await asyncio.to_thread(
                                                    bridge.check_order_status, order_ticket
                                                )

                                                if status == "FILLED":
                                                    filled = True
                                                    break

                                    if filled:
                                        persistence.save_trade(
                                            symbol,
                                            side,
                                            current_order_price,
                                            final_lots,
                                            mode_tag,
                                        )

                                        persistence.save_state(
                                            "last_auto_trade",
                                            f"{side} at {current_order_price}",
                                        )

                                        side_pt = "COMPRA" if side == "buy" else "VENDA"
                                        msg_log = f"TRADE SUCESSO: {side_pt} {final_lots} lotes @ {current_order_price}"

                                        add_operational_log(msg_log, "success")

                                        logging.info(
                                            f"TRADE SUCESSO ({mode_tag}): Sniper preenchido."
                                        )

                                    else:
                                        logging.warning(
                                            f"Sniper TTL Expirado. Verificando race condition para {order_ticket}..."
                                        )

                                        cancel_ok = await asyncio.to_thread(
                                            bridge.cancel_order, order_ticket
                                        )

                                        if not cancel_ok:
                                            # [FIX #LOCK-CANCEL-FAIL v2] cancel falhou: pode ser fill OU cancel externo.
                                            # NUNCA assumir fill sem verificar positions_get primeiro.
                                            await asyncio.sleep(0.3)
                                            pos_check = await asyncio.to_thread(
                                                bridge.mt5.positions_get, ticket=order_ticket
                                            )

                                            # [FIX #BELT-SUSPENDERS] Fallback por simbolo:
                                            # Em contas MT5 netting, o ticket de POSICAO pode diferir
                                            # do ticket de ORDEM LIMIT preenchida → pos_check retorna
                                            # vazio incorretamente. Verificar por simbolo como 2a linha de defesa.
                                            if not pos_check:
                                                pos_check_sym = await asyncio.to_thread(
                                                    bridge.mt5.positions_get, symbol=symbol
                                                )
                                                if pos_check_sym:
                                                    pos_check = pos_check_sym
                                                    logging.warning(
                                                        f"[BELT-SUSPENDERS Sniper] Posicao NAO encontrada por ticket={order_ticket}, "
                                                        f"MAS encontrada por simbolo={symbol}. Tratando como fill."
                                                    )

                                            if pos_check:
                                                # Posição real confirmada → fill legítimo
                                                _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                                _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC  # [FIX #DUAL-BOT-LOCK]
                                                logging.warning(
                                                    f"🔒 [LOCK-CANCEL-FAIL] Sniper: FILL REAL confirmado via positions_get "
                                                    f"para {order_ticket}. Lock local={ORDER_LOCK_SEC:.0f}s / global={GLOBAL_ORDER_LOCK_SEC:.0f}s."
                                                )
                                                race_status = await asyncio.to_thread(
                                                    bridge.check_order_status, order_ticket
                                                )
                                                if race_status == "FILLED":
                                                    side_pt = "COMPRA" if side == "buy" else "VENDA"
                                                    add_operational_log(
                                                        f"SNIPER VITÓRIA (RACE): {side_pt} {final_lots} lotes @ {current_order_price}",
                                                        "success",
                                                    )
                                                    persistence.save_trade(
                                                        symbol, side, current_order_price,
                                                        final_lots, "AUTO_SNIPER_RACE",
                                                    )
                                                    logging.info(
                                                        f"SNIPER RACE CONDITION: Ordem {order_ticket} preenchida no TTL!"
                                                    )
                                                else:
                                                    add_operational_log(
                                                        f"Sniper: Posição detectada mas status nao FILLED para {order_ticket}. Lock ativo.",
                                                        "warning",
                                                    )
                                            else:
                                                # [FIX #EXT-LOCK-UPGRADE] Sem posicao real confirmada.
                                                # Aumentado de 2s para ORDER_LOCK_SEC (10s): 2s era insuficiente
                                                # para bloquear o proximo ciclo de sinal do loop principal,
                                                # causando ordens multiplas em cascata (vide logs 14:42:11-17).
                                                _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                                _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC  # [FIX #DUAL-BOT-LOCK]
                                                logging.warning(
                                                    f"[LOCK-CANCEL-EXT] Sniper {order_ticket}: cancel falhou "
                                                    f"SEM POSICAO REAL. Lock conservador {ORDER_LOCK_SEC:.0f}s local+global ativado."
                                                )
                                                add_operational_log(
                                                    f"Sniper TTL: {order_ticket} cancelado externamente. Lock conservador {ORDER_LOCK_SEC:.0f}s.",
                                                    "warning",
                                                )
                                        else:
                                            add_operational_log(
                                                f"Sniper TTL: {order_ticket} cancelado (sem fill).",
                                                "info",
                                            )

                                else:
                                    msg = (
                                        result.comment
                                        if hasattr(result, "comment")
                                        else "Tempo_Esgotado/Nulo"
                                    )

                                    # [FIX #ALGO-OFF] Detectar AutoTrading desabilitado (10027)
                                    if result and getattr(result, "retcode", 0) == 10027:
                                        logging.critical(
                                            "🚨 [ALGOTRADING-OFF] AutoTrading desabilitado no MT5! "
                                            "Pausando 30s. Reative AlgoTrading no terminal MT5."
                                        )
                                        add_operational_log(
                                            "CRÍTICO: AutoTrading desabilitado (10027). Pausando 30s. Reative no MT5.",
                                            "error",
                                        )
                                        await asyncio.sleep(30)
                                    else:
                                        # [FIX #ORDER-RETRY] Lock curto após falha: evita spam de retry a 400ms
                                        _order_lock_until = time_module.time() + ORDER_FAIL_LOCK_SEC
                                        logging.error(
                                            f"Falha Crítica na Execução Sniper: {msg} — Lock {ORDER_FAIL_LOCK_SEC:.0f}s ativado."
                                        )

                                    add_operational_log(
                                        f"Falha Execução Sniper: {msg}", "error"
                                    )

                            else:
                                order_type = (
                                    bridge.mt5.ORDER_TYPE_BUY_LIMIT
                                    if side == "buy"
                                    else bridge.mt5.ORDER_TYPE_SELL_LIMIT
                                )

                                # [FIX #PRE-ORDER-GATE] Verificacao live de posicao antes de enviar HFT.
                                _live_positions_hft = await asyncio.to_thread(
                                    bridge.mt5.positions_get, symbol=symbol
                                )
                                if _live_positions_hft:
                                    logging.warning(
                                        f"[PRE-ORDER-GATE/HFT] Posicao JA ABERTA detectada live "
                                        f"({len(_live_positions_hft)} pos). Abortando HFT. "
                                        f"Tickets: {[p.ticket for p in _live_positions_hft]}"
                                    )
                                    add_operational_log(
                                        "[PRE-ORDER-GATE/HFT] Entrada bloqueada: posicao aberta em tempo real.",
                                        "warning",
                                    )
                                    continue

                                logging.info(
                                    "ENTRADA PASSIVA: ORDEM LIMITE (Topo do Book)"
                                )

                                tick_info = await asyncio.to_thread(
                                    bridge.mt5.symbol_info_tick, symbol
                                )

                                if tick_info is None:
                                    logging.warning("[PASSIVO] symbol_info_tick retornou None. Abortando ordem.")
                                    continue

                                limit_price = (
                                    tick_info.bid if side == "buy" else tick_info.ask
                                )

                                valid_comp, reason_comp = await asyncio.to_thread(
                                    bridge.validate_order_compliance,
                                    symbol,
                                    limit_price,
                                )

                                if not valid_comp:
                                    logging.warning(
                                        f"VARREDURA Compliance: {reason_comp}"
                                    )

                                else:
                                    point_value = (
                                        10.0
                                        if "WDO" in symbol or "DOL" in symbol
                                        else 0.20
                                    )

                                    # [MT5-INTEG #5] Usa equity no sizing quando ha pos. aberta
                                    sizing_balance = (
                                        account.get("equity", account["balance"])
                                        if account.get("equity", 0) > 0
                                        else account["balance"]
                                    )
                                    sota_lots = risk.calculate_volatility_sizing(
                                        sizing_balance, current_atr, point_value
                                    )

                                    # [SOTA v3] Aplicar Multiplicador de Lotes da IA (Exposição Parcial)

                                    ai_multiplier = decision.get("lot_multiplier", 1.0)

                                    # [FIX #MP-E] vol_step pertence a symbol_info(), nao a tick_info()
                                    # tick_info.volume_step nao existe — sempre caia no fallback 1.0
                                    _sym_info = await asyncio.to_thread(bridge.mt5.symbol_info, symbol)
                                    vol_step = (
                                        _sym_info.volume_step
                                        if _sym_info and hasattr(_sym_info, "volume_step")
                                        else 1.0
                                    )

                                    final_lots = (
                                        round((sota_lots * ai_multiplier) / vol_step)
                                        * vol_step
                                    )

                                    final_lots = max(vol_step, final_lots)

                                    logging.info(
                                        f"[SOTA] HFT Limit: {final_lots} lotes @ {limit_price}"
                                    )

                                    params = risk.get_order_params(
                                        symbol,
                                        order_type,
                                        limit_price,
                                        final_lots,
                                        current_atr=current_atr,
                                        regime=regime,
                                    )

                                    params["symbol"] = symbol

                                    params["comment"] = "AUTO_HFT_LIMIT"

                                    # 🛡️ [FIX CRÍTICO] PRE-LOCK: Trava o sistema local e globalmente ANTES da chamada de rede.
                                    _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                    _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC

                                    if risk.dry_run:
                                        side_pt = "COMPRA" if side == "buy" else "VENDA"
                                        logging.warning(
                                            f"DRY-RUN: Simulando Ordem LIMIT {side_pt} de {final_lots} lotes @ {limit_price}"
                                        )

                                        class MockResultLimit:
                                            retcode = bridge.mt5.TRADE_RETCODE_DONE

                                            order = 999999

                                        result = MockResultLimit()

                                    else:
                                        result = await asyncio.to_thread(
                                            bridge.place_limit_order,
                                            symbol,
                                            order_type,
                                            limit_price,
                                            final_lots,
                                            sl=params["sl"],
                                            tp=params["tp"],
                                            comment="AUTO HFT LIMIT",
                                        )

                                    if (
                                        result
                                        and result.retcode
                                        == bridge.mt5.TRADE_RETCODE_DONE
                                    ):
                                        # [FIX #FLIP-4] Ativar lock imediatamente após ordem passiva aceita
                                        _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                        # [FIX #DUAL-BOT-LOCK] Propagar lock para o Sniper também
                                        _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC
                                        logging.info(
                                            f"🔒 [FLIP-4+DUAL] Lock local+global ativo: {ORDER_LOCK_SEC:.0f}s/{GLOBAL_ORDER_LOCK_SEC:.0f}s (PASSIVO ticket={result.order})"
                                        )
                                        order_ticket = result.order

                                        mode_tag = (
                                            "SIMULACAO_LIMITE_PENDENTE"
                                            if risk.dry_run
                                            else "PENDENTE"
                                        )

                                        logging.info(
                                            f"Ordem {mode_tag} Aberta: {order_ticket}. Aguardando 5s..."
                                        )

                                        filled = False

                                        # [DRY-RUN FIX] Em simulação, curto-circuita o polling real.
                                        # Tickets fictícios (999999) jamais existem no MT5 real.
                                        if risk.dry_run:
                                            filled = True
                                            side_pt = "COMPRA" if side == "buy" else "VENDA"
                                            logging.warning(
                                                f"DRY-RUN: HFT LIMIT simulado como FILLED (ticket fictício={order_ticket})"
                                            )
                                            add_operational_log(
                                                f"HFT FILL (SIMULADO): {side_pt} {final_lots} lotes @ {limit_price}",
                                                "success",
                                            )
                                            persistence.save_trade(
                                                symbol, side, limit_price,
                                                final_lots, "SIMULACAO_LIMIT_FILLED",
                                            )
                                        else:
                                            # [FIX #POLL-INSTANT] Verifica IMEDIATAMENTE antes do 1º sleep
                                            status_imediato = await asyncio.to_thread(
                                                bridge.check_order_status, order_ticket
                                            )
                                            if status_imediato == "FILLED":
                                                filled = True
                                                logging.info(
                                                    f"[POLL-INSTANT] HFT {order_ticket} já preenchido antes do 1º sleep!"
                                                )
                                                side_pt = "COMPRA" if side == "buy" else "VENDA"
                                                add_operational_log(
                                                    f"HFT FILL INSTANT: {side_pt} {final_lots} lotes @ {limit_price}",
                                                    "success",
                                                )
                                                persistence.save_trade(
                                                    symbol, side, limit_price,
                                                    final_lots, "AUTO_LIMIT_FILLED",
                                                )

                                        if not filled:
                                            for _ in range(6):
                                                await asyncio.sleep(0.5)

                                                status = await asyncio.to_thread(
                                                    bridge.check_order_status, order_ticket
                                                )

                                                try:
                                                    hb_packet = {
                                                        "symbol": symbol,
                                                        "price": limit_price,
                                                        "obi": obi,
                                                        "sentiment": ai.latest_sentiment_score,
                                                        "logs": trade_logs,
                                                        "risk_status": {
                                                            "ai_score": ai_total_score,
                                                            "allow_autonomous": risk.allow_autonomous,
                                                            "time_ok": time_allowed,
                                                            "loss_ok": risk_ok,
                                                            "order_status": "PENDENTE_HFT",
                                                            "regime": int(regime),
                                                            "ticket": order_ticket,
                                                            "synthetic_index": float(
                                                                synthetic_idx
                                                            ),
                                                            "bluechips": bluechips
                                                            if isinstance(bluechips, dict)
                                                            else {},
                                                            "limits": session_limits,
                                                            "dry_run": risk.dry_run,
                                                        },
                                                        "account": account,
                                                        "timestamp": time_module.time(),
                                                    }

                                                    latest_market_packet = hb_packet
                                                    disconnected_ws = []
                                                    for ws in list(active_websockets):
                                                        try:
                                                            await ws.send_json(hb_packet)
                                                        except Exception:
                                                            disconnected_ws.append(ws)
                                                    for ws in disconnected_ws:
                                                        if ws in active_websockets:
                                                            active_websockets.remove(ws)
                                                except Exception:
                                                    pass

                                                if status == "FILLED":
                                                    filled = True

                                                    logging.info(
                                                        f"HFT FILL: Ordem {order_ticket} executada no spread!"
                                                    )

                                                    side_pt = (
                                                        "COMPRA"
                                                        if side == "buy"
                                                        else "VENDA"
                                                    )
                                                    add_operational_log(
                                                        f"HFT FILL: {side_pt} {final_lots} lotes @ {limit_price}",
                                                        "success",
                                                    )

                                                    persistence.save_trade(
                                                        symbol,
                                                        side,
                                                        limit_price,
                                                        final_lots,
                                                        "AUTO_LIMIT_FILLED",
                                                    )

                                                    break

                                                elif status == "CANCELED":
                                                    logging.warning(
                                                        f"Ordem {order_ticket} cancelada externamente."
                                                    )

                                                    break

                                        if not filled:
                                            logging.info(
                                                f"HFT TTL Expirado: Tentando cancelar {order_ticket}..."
                                            )

                                            cancel_success = await asyncio.to_thread(
                                                bridge.cancel_order, order_ticket
                                            )

                                            if not cancel_success:
                                                # [FIX #LOCK-CANCEL-FAIL v2] cancel falhou: pode ser fill OU cancel externo.
                                                # NUNCA assumir fill sem verificar positions_get primeiro.
                                                await asyncio.sleep(0.3)  # MT5 precisa de ~200ms para atualizar o estado
                                                pos_check = await asyncio.to_thread(
                                                    bridge.mt5.positions_get, ticket=order_ticket
                                                )

                                                # [FIX #BELT-SUSPENDERS] Fallback por simbolo:
                                                # Em contas MT5 netting, ticket de POSICAO pode diferir
                                                # do ticket de ORDEM LIMIT → verificar por simbolo.
                                                if not pos_check:
                                                    pos_check_sym = await asyncio.to_thread(
                                                        bridge.mt5.positions_get, symbol=symbol
                                                    )
                                                    if pos_check_sym:
                                                        pos_check = pos_check_sym
                                                        logging.warning(
                                                            f"[BELT-SUSPENDERS HFT] Posicao NAO encontrada por ticket={order_ticket}, "
                                                            f"MAS encontrada por simbolo={symbol}. Tratando como fill."
                                                        )

                                                if pos_check:
                                                    # Posição real confirmada → fill legítimo
                                                    _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                                    _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC  # [FIX #DUAL-BOT-LOCK]
                                                    logging.warning(
                                                        f"🔒 [LOCK-CANCEL-FAIL] HFT: FILL REAL confirmado via positions_get "
                                                        f"para {order_ticket}. Lock local={ORDER_LOCK_SEC:.0f}s / global={GLOBAL_ORDER_LOCK_SEC:.0f}s."
                                                    )
                                                    final_status = await asyncio.to_thread(
                                                        bridge.check_order_status,
                                                        order_ticket,
                                                    )
                                                    if final_status == "FILLED":
                                                        logging.info(
                                                            f"VITORIA POR CONDICAO DE CORRIDA: Ordem {order_ticket} preenchida!"
                                                        )
                                                        side_pt = (
                                                            "COMPRA"
                                                            if side == "buy"
                                                            else "VENDA"
                                                        )
                                                        add_operational_log(
                                                            f"VITORIA POR CONDICAO DE CORRIDA: {side_pt} {final_lots} lotes!",
                                                            "success",
                                                        )
                                                        persistence.save_trade(
                                                            symbol,
                                                            side,
                                                            limit_price,
                                                            final_lots,
                                                            "AUTO_LIMIT_FILLED_RACE",
                                                        )
                                                    else:
                                                        add_operational_log(
                                                            f"HFT: Posicao detectada mas status nao FILLED para {order_ticket}. Lock ativo.",
                                                            "warning",
                                                        )
                                                else:
                                                    # [FIX #EXT-LOCK-UPGRADE] Sem posicao confirmada por ticket OU simbolo.
                                                    # Aumentado de 2s para ORDER_LOCK_SEC (10s): 2s causava
                                                    # cascata de ordens multiplas (vide logs 14:42:11-17).
                                                    _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                                    _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC  # [FIX #DUAL-BOT-LOCK]
                                                    logging.warning(
                                                        f"[LOCK-CANCEL-EXT] HFT {order_ticket}: cancel falhou "
                                                        f"SEM POSICAO REAL. Lock conservador {ORDER_LOCK_SEC:.0f}s local+global ativado."
                                                    )
                                                    add_operational_log(
                                                        f"HFT TTL: {order_ticket} cancelado externamente. Lock conservador {ORDER_LOCK_SEC:.0f}s.",
                                                        "warning",
                                                    )

                                            else:
                                                add_operational_log(
                                                    f"HFT TTL: {order_ticket} cancelada (sem fill).",
                                                    "info",
                                                )

                                    else:
                                        msg = (
                                            result.comment if result else "Timeout/None"
                                        )

                                        # [FIX #ALGO-OFF] Detectar AutoTrading desabilitado (10027)
                                        if result and getattr(result, "retcode", 0) == 10027:
                                            logging.critical(
                                                "🚨 [ALGOTRADING-OFF] AutoTrading desabilitado no MT5! "
                                                "Pausando 30s. Reative AlgoTrading no terminal MT5."
                                            )
                                            add_operational_log(
                                                "CRÍTICO: AutoTrading desabilitado (10027). Pausando 30s. Reative no MT5.",
                                                "error",
                                            )
                                            await asyncio.sleep(30)
                                        else:
                                            # [FIX #ORDER-RETRY] Lock curto após qualquer falha de envio PASSIVO
                                            _order_lock_until = time_module.time() + ORDER_FAIL_LOCK_SEC
                                            logging.error(
                                                f"Falha ao enviar Limit Order: {msg} — Lock {ORDER_FAIL_LOCK_SEC:.0f}s ativado."
                                            )

                elif risk.allow_autonomous and ai_total_score >= 82:
                    if not market_ok:
                        logging.info(
                            f"SINAL FORTE BLOQUEADO: {market_condition['reason']}"
                        )

                        add_operational_log(
                            f"OPORTUNIDADE VETADA (Mercado): {market_condition['reason']}",
                            "warning",
                        )

                    elif not risk_ok:
                        logging.info(f"SINAL FORTE BLOQUEADO: {risk_msg}")

                        add_operational_log(
                            f"OPORTUNIDADE VETADA (Limites): {risk_msg}", "warning"
                        )

                    elif not time_allowed:
                        pass

                    else:
                        add_operational_log(
                            f"SINAL ANALISADO ({ai_total_score}%): Aguardando Confluência L2",
                            "info",
                        )

                # 4. Dados de Compliance e Performance (Cycle 1s)

                if loop_count % 10 == 0:
                    info = await asyncio.to_thread(bridge.mt5.symbol_info, symbol)

                    session_limits = {
                        "lower": getattr(info, "session_price_limit_min", 0.0)
                        if info
                        else 0,
                        "upper": getattr(info, "session_price_limit_max", 0.0)
                        if info
                        else 0,
                        "ref": getattr(info, "session_price_ref", 0.0) if info else 0,
                    }

                    try:
                        perf_mt5 = await asyncio.to_thread(
                            bridge.get_trading_performance
                        )

                        risk.total_trades = perf_mt5["total_trades"]

                        risk.wins = int(
                            perf_mt5["total_trades"] * (perf_mt5["win_rate"] / 100)
                        )

                        risk.gross_profit = perf_mt5["gross_profit"]

                        risk.gross_loss = perf_mt5["gross_loss"]

                        risk.daily_profit = perf_mt5["net_profit"]

                    except Exception as e:
                        logging.error(f"Erro ao sincronizar performance MT5: {repr(e)}")

                # 5. Enviar Pacote ao Frontend

                try:
                    packet = {
                        "symbol": str(symbol),
                        "price": float(last_price),
                        "obi": float(obi),
                        "ai_confidence": float(ai_total_score) / 100.0,
                        "book": book,
                        "sentiment": {
                            "score": float(sentiment_score),
                            "headlines": headlines,
                        },
                        "macro": macro_change
                        if isinstance(macro_change, dict)
                        else {"score": float(macro_change), "reason": "S&P 500"},
                        "calendar": {
                            "volatility_expected": vol_expected,
                            "reason": str(vol_reason),
                        },
                        "ai_prediction": {
                            "score": float(ai_total_score),
                            "direction": str(ai_direction),
                            "veto": decision.get("veto"),
                            "lot_multiplier": float(
                                decision.get("lot_multiplier", 1.0)
                            ),
                            "forecast": float(
                                ai_predict_data.get("forecast", last_price)
                                if isinstance(ai_predict_data, dict)
                                else last_price
                            ),
                        },
                        "account": account,
                        "daily_realized": float(daily_realized),
                        "latency_ms": float(latency_ms),
                        "risk_status": {
                            "time_ok": time_allowed,
                            "loss_ok": risk_ok,
                            "allow_autonomous": risk.allow_autonomous,
                            "profit_day": float(total_daily_profit),
                            "atr": float(current_atr),
                            "limits": session_limits,  # [HFT v3] Trading Tunnels
                            "performance": risk.get_performance_metrics(),
                            # [DISPLAY FIX] Converte uncertainty_norm (0-1) para pontos reais (ATR-scaled)
                            # uncertainty_norm=0.10 * ATR=100pts → exibe "10.0 pts" no painel
                            # Nenhuma lógica de decisão é alterada — apenas conversão visual
                            "uncertainty_range": float(
                                ai_predict_data.get("uncertainty_norm", 0.0) * max(float(current_atr), 1.0)
                                if isinstance(ai_predict_data, dict)
                                else 0.0
                            ),
                            "lower_bound": float(
                                ai_predict_data.get("lower_bound_norm", last_price)
                                if isinstance(ai_predict_data, dict)
                                else last_price
                            ),
                            "upper_bound": float(
                                ai_predict_data.get("upper_bound_norm", last_price)
                                if isinstance(ai_predict_data, dict)
                                else last_price
                            ),
                            "weighted_ofi": float(wen_ofi_val),
                            "synthetic_index": float(synthetic_idx),
                            "bluechips": bluechips
                            if isinstance(bluechips, dict)
                            else {},
                            "psr": float(current_psr),
                            "regime": int(regime),
                            "sniper": {
                                "running": sniper_bot.running,
                                "consecutive_wins": sniper_bot.consecutive_wins,
                                "trade_count": sniper_bot.trade_count,
                                "last_trade_time": str(sniper_bot.last_trade_time)
                                if sniper_bot.last_trade_time
                                else None,
                            },
                        },
                        "dry_run": risk.dry_run,
                        "timestamp": (
                            datetime.now(timezone.utc) - timedelta(hours=3)
                        ).timestamp(),
                        "logs": trade_logs,
                    }

                    # [DINAMISMO] Alertas de Latência
                    if latency_ms > 500:
                        add_operational_log(
                            f"ALERTA DE ALTA LATÊNCIA: {latency_ms:.1f}ms", "warning"
                        )

                    # [DINAMISMO] Alertas de Exaustão (ATR Alto)
                    if current_atr > risk.atr_volatility_trigger:
                        if loop_count % 30 == 0:
                            add_operational_log(
                                f"EXAUSTÃO DE VOLATILIDADE: Apertando o rigor (ATR: {current_atr:.1f})",
                                "warning",
                            )

                    # [DINAMISMO] Pulso de Mercado (Heartbeat)
                    if loop_count % 60 == 0:
                        add_operational_log(
                            f"PULSO DE MERCADO: IA ativa (Score: {ai_total_score:.1f}% | OBI: {obi:.2f}).",
                            "info",
                        )

                    latest_market_packet = packet
                    disconnected_ws = []
                    for ws in list(active_websockets):
                        try:
                            await ws.send_json(packet)
                        except Exception:
                            disconnected_ws.append(ws)
                    for ws in disconnected_ws:
                        if ws in active_websockets:
                            active_websockets.remove(ws)

                except Exception as packet_e:
                    logging.error(f"Erro ao processar/enviar pacote WS: {packet_e}")

                persistence.save_state("last_obi", float(obi))

                persistence.save_state("latency_ms", float(latency_ms))

                # 6. Housekeeping (10s)

                if time_module.time() - last_cleanup_time > 10:
                    last_cleanup_time = time_module.time()

                    try:
                        base_asset = (
                            "WDO" if "WDO" in symbol or "DOL" in symbol else "WIN"
                        )

                        new_symbol = bridge.get_current_symbol(base_asset)

                        if (
                            new_symbol
                            and new_symbol != symbol
                            and "$" not in new_symbol
                        ):
                            logging.warning(f"🔄 ROLLOVER: {symbol} -> {new_symbol}")

                            symbol = new_symbol

                            await panic_close_all()

                            continue

                    except Exception:
                        pass

                    orders = await asyncio.to_thread(
                        bridge.mt5.orders_get, symbol=symbol
                    )

                    if orders:
                        now_ts = time_module.time()

                        for order in orders:
                            if (now_ts - order.time_setup) > 60:
                                # [FIX #MP-F] Usa bridge.cancel_order para capturar race condition
                                # mt5.order_send direto pulava verificacao de fill no momento do cancel
                                cancel_ok = await asyncio.to_thread(
                                    bridge.cancel_order, order.ticket
                                )
                                if not cancel_ok:
                                    # Verifica se foi preenchida no instante do housekeeping
                                    final_st = await asyncio.to_thread(
                                        bridge.check_order_status, order.ticket
                                    )
                                    if final_st == "FILLED":
                                        # [FIX #HK-LOCK] Fill inesperado no housekeeping:
                                        # ativa lock para evitar nova entrada imediata sobre posição recém-aberta
                                        _order_lock_until = time_module.time() + ORDER_LOCK_SEC
                                        _global_order_lock_until = time_module.time() + GLOBAL_ORDER_LOCK_SEC  # [FIX #DUAL-BOT-LOCK]
                                        logging.info(
                                            f"[HOUSEKEEPING] Ordem {order.ticket} preenchida no TTL! Lock local+global ({ORDER_LOCK_SEC:.0f}s/{GLOBAL_ORDER_LOCK_SEC:.0f}s) ativado. Registrando."
                                        )
                                        persistence.save_trade(
                                            symbol, "limit_housekeeping", order.price_open,
                                            order.volume_current, "AUTO_LIMIT_HOUSEKEEPING_RACE",
                                        )
                                    else:
                                        logging.warning(
                                            f"[HOUSEKEEPING] Falha ao cancelar ordem obsoleta {order.ticket}"
                                        )
                                else:
                                    logging.info(
                                        f"[HOUSEKEEPING] Ordem obsoleta {order.ticket} cancelada (>{60}s sem fill)."
                                    )

                # [ANTIVIBE-CODING] Log de Mudança de Regime (Garantia de Sincronia)
                if "last_regime" not in locals():
                    last_regime = regime
                elif regime != last_regime:
                    labels = {0: "LATERAL", 1: "TENDÊNCIA", 2: "VOLÁTIL"}
                    logging.info(
                        f"🔄 [REGIME CHANGE] {labels.get(last_regime, '??')} -> {labels.get(regime, '??')} (Vol: {volatility:.1f} | OBI: {obi:.2f})"
                    )
                    last_regime = regime

                await asyncio.sleep(0.05)

            except asyncio.CancelledError:
                raise

            except Exception as e:
                logging.error(f"Erro no loop principal: {sanitize_log(e)}")

                await asyncio.sleep(1)

    except Exception as e:
        logging.critical(f"Erro fatal Loop Autônomo: {sanitize_log(e)}")


# [ANTIVIBE-CODING] - Novo Endpoint Exclusivo para Clientes WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    logging.info(
        f"🟢 Cliente WebSocket Conectado no Painel. [Total: {len(active_websockets)}]"
    )
    add_operational_log(
        f"Painel conectado via WebSocket (Total: {len(active_websockets)})", "info"
    )
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except Exception:
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logging.info(
            f"🔴 Cliente WebSocket Desconectado do Painel. [Total: {len(active_websockets)}]"
        )


@app.post("/config/autonomous")
async def toggle_autonomous(enabled: bool):
    risk.allow_autonomous = enabled
    status = "ATIVO" if enabled else "INATIVO"
    logging.info(f"Modo Autônomo: {status}")
    add_operational_log(
        f"Modo Autônomo alterado para: {status}", "warning" if enabled else "info"
    )
    return {"status": "success", "autonomous": enabled}


@app.get("/config/filters")
async def get_filters():
    return {
        "status": "success",
        "news": risk.enable_news_filter,
        "calendar": risk.enable_calendar_filter,
        "macro": risk.enable_macro_filter,
    }


@app.post("/config/filters/news")
async def toggle_news_filter(enabled: bool):
    risk.enable_news_filter = enabled
    if hasattr(sniper_bot, "risk") and sniper_bot.risk:
        sniper_bot.risk.enable_news_filter = enabled
    status = "ATIVADO" if enabled else "DESATIVADO"
    logging.info(f"Filtro de Notícias NLP: {status} manualmente.")
    add_operational_log(f"Filtro de Notícias NLP {status} pelo usuário", "info")
    return {"status": "success", "news": enabled}


@app.post("/config/filters/calendar")
async def toggle_calendar_filter(enabled: bool):
    risk.enable_calendar_filter = enabled
    if hasattr(sniper_bot, "risk") and sniper_bot.risk:
        sniper_bot.risk.enable_calendar_filter = enabled
    status = "ATIVADO" if enabled else "DESATIVADO"
    logging.info(f"Filtro de Calendário: {status} manualmente.")
    add_operational_log(f"Filtro de Calendário Econômico {status} pelo usuário", "info")
    return {"status": "success", "calendar": enabled}


@app.post("/config/filters/macro")
async def toggle_macro_filter(enabled: bool):
    risk.enable_macro_filter = enabled
    if hasattr(sniper_bot, "risk") and sniper_bot.risk:
        sniper_bot.risk.enable_macro_filter = enabled
    status = "ATIVADO" if enabled else "DESATIVADO"
    logging.info(f"Filtro Macro (S&P 500): {status} manualmente.")
    add_operational_log(f"Filtro Macro Global {status} pelo usuário", "info")
    return {"status": "success", "macro": enabled}


@app.post("/config/sniper/start")
async def start_sniper():

    global bot_task

    if sniper_bot.running:
        return {"status": "error", "message": "O robô já está em execução"}

    bot_task = asyncio.create_task(sniper_bot.run())

    return {"status": "success"}


@app.post("/config/sniper/stop")
async def stop_sniper():

    sniper_bot.stop()

    return {"status": "success"}


@app.get("/performance")
async def get_performance():

    try:
        perf = risk.get_performance_metrics()

        return {"status": "success", "data": perf}

    except Exception as e:
        return {"status": "error", "data": {}, "detail": repr(e)}


@app.post("/order")
async def place_order(req: OrderRequest):

    start_order = time_module.perf_counter()

    side = req.side.lower()

    volume = float(req.volume)

    if side in ["close_all", "panic"]:
        await panic_close_all()

        return {"status": "success", "message": "PANICO_ACIONADO"}

    if not bridge.connected:
        return {"status": "error", "message": "MT5 não conectado"}

    if not risk.is_time_allowed():
        return {"status": "error", "message": "Horário não permitido"}

    # [OTIMIZAÇíO HFT] Envolvendo todas as chamadas MT5 em threads para evitar lentidão no event loop

    account_info = await asyncio.to_thread(bridge.mt5.account_info)

    # [FIX #28] check_daily_loss retorna (bool, msg) — desempacotar antes de avaliar
    _loss_ok, _loss_msg = risk.check_daily_loss(account_info.profit if account_info else 0)
    if not _loss_ok:
        return {"status": "error", "message": f"Limite de perda diária atingido: {_loss_msg}"}

    symbol = await asyncio.to_thread(bridge.get_current_symbol, "WIN")

    # [FIX #24] Execução manual usa mercado imediato (DEAL + IOC), não pendente (PENDING + LIMIT)
    order_type = (
        bridge.mt5.ORDER_TYPE_BUY
        if side == "buy"
        else bridge.mt5.ORDER_TYPE_SELL
    )

    tick = await asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol)

    if tick is None:
        return {"status": "error", "message": "Falha ao obter preço (Tick Nulo)"}

    price = tick.ask if side == "buy" else tick.bid

    # Validação e Parâmetros (Pode ser intensivo em CPU ou acessar MT5 internamente)

    valid, reason = await asyncio.to_thread(
        bridge.validate_order_compliance, symbol, price
    )

    if not valid:
        return {"status": "error", "message": reason}

    params = await asyncio.to_thread(
        risk.get_order_params, symbol, order_type, price, int(volume)
    )

    params["symbol"] = symbol

    # [FIX #24] Sobrescreve action/type/filling para execução imediata no mercado
    params["action"] = bridge.mt5.TRADE_ACTION_DEAL
    params["type"] = order_type
    params["type_filling"] = bridge.mt5.ORDER_FILLING_IOC  # IOC obrigatório para WIN/WDO na B3

    # Envio Real da Ordem

    result = await asyncio.to_thread(bridge.mt5.order_send, params)

    latency = (time_module.perf_counter() - start_order) * 1000

    # [FIX #25] Guard contra result None (timeout/desconexão do MT5)
    if result is None:
        logging.error(f"⚡ PIPELINE_ORDEM: MT5 retornou None. Lado={side}, Latência={latency:.2f}ms")
        return {"status": "error", "message": "MT5 retornou None (timeout ou desconexão)"}

    logging.info(
        f"⚡ PIPELINE_ORDEM: Lado={side}, Vol={volume}, Resultado={result.retcode}, Latência={latency:.2f}ms"
    )

    if result.retcode != bridge.mt5.TRADE_RETCODE_DONE:
        return {
            "status": "error",
            "message": f"Erro MT5: {sanitize_log(result.comment)}",
        }

    await asyncio.to_thread(persistence.save_trade, symbol, side, price, volume)

    return {"status": "success", "order_id": result.order}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
