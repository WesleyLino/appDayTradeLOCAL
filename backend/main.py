from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# --- MONKEY-PATCH PARA CONFLITO ONNX/BEARTYPE ---
try:
    import onnxscript.values as v
    if not hasattr(v, 'ParamSchema'):
        class DummyParamSchema: pass
        v.ParamSchema = DummyParamSchema
except ImportError:
    pass
# -----------------------------------------------
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from .mt5_bridge import MT5Bridge
from backend.risk_manager import RiskManager
from backend.ai_core import AICore, InferenceEngine
from backend.persistence import PersistenceManager
from backend.rl_agent import PPOAgent # HFT v2.0
from backend.microstructure_analyzer import MicrostructureAnalyzer # HFT v2.0
from backend.news_collector import NewsCollector
import pandas as pd
import numpy as np
from .data_collector import DataCollector
import time as time_module
import traceback
# Configuração de Logs Unificada
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend/ws_debug_final.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
from backend.sentiment_analyzer import SentimentAnalyzer
from backend.calendar_manager import CalendarManager
from datetime import datetime, timedelta
from pydantic import BaseModel

class OrderRequest(BaseModel):
    side: str
    volume: float = 1.0

app = FastAPI()

# Permite acesso do frontend Next.js local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Inicialização Global de Componentes (HFT v2.1) ---
bridge = MT5Bridge()
risk = RiskManager()
ai = AICore()
persistence = PersistenceManager()
rl_agent = PPOAgent(input_dim=7, n_actions=3) # Global para evitar lag na conexão
micro_analyzer = MicrostructureAnalyzer()   # Global

import os
weights_path = os.path.join(os.getcwd(), "backend", "patchtst_weights_sota.pth")
if not os.path.exists(weights_path):
    # Tentar caminho alternativo
    weights_path = "backend/patchtst_weights_sota.pth"
if not os.path.exists(weights_path):
    weights_path = os.path.join(os.getcwd(), "backend", "patchtst_weights.pth") # Fallback Legado

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
        print("DEBUG: STARTUP EVENT STARTED", file=sys.stderr)
        # Configurar Logs (já feito no global, mas ok)
        
        # Conexão MT5 (Refatorado para não ser bloqueante)
        print("DEBUG: Connecting bridge...", file=sys.stderr)
        connected = await asyncio.to_thread(bridge.connect)
        if not connected:
            logging.warning("MT5 Bridge não conectado na inicialização. Tentando reconectar...")
            # A reconexão acontece no loop principal, mas podemos logar aqui.
        else:
            try:
                login_info = bridge.mt5.account_info().login
                logging.info(f"[OK] MT5 Bridge conectado: {login_info}")
            except:
                logging.info("[OK] MT5 Bridge conectado.")
        # Atalho Global de Pânico: Ctrl+Q para zerar tudo
        
        # Verificar recursos críticos
        print("DEBUG: Instantiating InferenceEngine...", file=sys.stderr)
        inference = InferenceEngine(weights_path)
        
        print("DEBUG: Checking resources...", file=sys.stderr)
        missing_resources = inference.check_resources()
        if missing_resources:
            logging.critical(f"RECURSOS FALTANDO: {missing_resources}")
            # Poderíamos travar o startup, mas melhor avisar e rodar em modo degradado

        print("DEBUG: Injecting dependency...", file=sys.stderr)
        # Injeção de Dependência (opcional, já que passamos no loop, mas boa prática)
        ai.inference_engine = inference
        
        # keyboard.add_hotkey('ctrl+q', lambda: panic_close_all())
        # logging.info("Kill Switch ativo: Pressione Ctrl+Q para ZERAR TUDO.")
        print("DEBUG: STARTUP FINISHED", file=sys.stderr)
    except Exception:
        print("CRITICAL STARTUP ERROR:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        logging.critical("CRITICAL STARTUP ERROR", exc_info=True)
        # sys.exit(1) # Let uvicorn handle it? No, explicit exit is better if stuck.

def panic_close_all():
    """Zera todas as posições abertas imediatamente."""
    # Evita spam do botão de pânico se já estiver ativado
    current_status = persistence.load_state("panic_status")
    if current_status == "CLOSED_ALL":
        return
        
    logging.warning("!!! BOTÃO DE PÂNICO ACIONADO !!!")
    if bridge.connected:
        mt5 = bridge.mt5
        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                # B3 Netting: Enviar ordem oposta via close_position (Centralizado)
                bridge.close_position(pos.ticket)
        
        persistence.save_state("panic_status", "CLOSED_ALL")

@app.on_event("shutdown")
async def shutdown_event():
    bridge.disconnect()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    conn_id = f"{time_module.time():.4f}"
    logging.info(f"🚀 WebSocket: Handshake concluído. [ID: {conn_id}]")
    
    try:
        # Configurações de Risco/Filtros (Failsafe)
        cvd_threshold = 1000 
        safe_dist = 50.0

        # Loop Principal
        last_cleanup_time = 0
        last_trailing_check = 0
        last_heartbeat = time_module.time()
        
        # Variáveis de Estado Persistentes no Loop
        symbol = "WIN$" # Inicial
        returns_history = []
        prev_total_profit = 0.0
        current_day = datetime.now().day
        
        # [HFT] Inicialização de Variáveis de Ciclo
        loop_count = 0
        data_60 = pd.DataFrame()
        multi_data = pd.DataFrame()
        account_info = None
        wen_ofi_val = 0.0
        vol_reason = ""
        settlement_price = 0.0
        bluechips = pd.DataFrame()
        macro_change = {"score": 0.0, "reason": "No data"}
        daily_rates = None
        current_symbol = "WIN$"
        current_atr = 0.0
        avg_atr = 0.0
        ai_confidence = 0.0
        volatility = 0.0
        regime = 0
        synthetic_idx = 0.0
        prev_total_profit = 0.0
        
        logging.info("Entrando no loop principal do WebSocket...")
        while True:
            start_time = time_module.perf_counter()
            now = datetime.now()
            logging.debug(f"--- HEARTBEAT [{now}] ---")
            current_hour = now.hour
            logging.debug("Step 1: Check Conexao")
            # --- 0. CHECK CONEXÃO MT5 ---
            if not bridge.check_connection():
                logging.warning("MT5 desconectado. Tentando reconectar...")
                if bridge.connect():
                    logging.info("Reconectado ao MT5 com sucesso!")
                else:
                    if time_module.time() - last_heartbeat > 30.0:
                        logging.error("Conexão MT5 perdida ou Terminal instável. Pausando execução...")
                    await asyncio.sleep(5) 
                    last_heartbeat = time_module.time()
                    continue

            try: 
                # --- 1. DETECÇÃO DE SÍMBOLO (Ciclo Médio: 1s) ---
                if loop_count % 5 == 1 or not symbol:
                    logging.debug("Step 3: Obtendo simbolo")
                    new_symbol = await asyncio.to_thread(bridge.get_current_symbol, "WIN")
                    if new_symbol and new_symbol != symbol:
                        logging.info(f"Símbolo detectado: {new_symbol}")
                        symbol = new_symbol
                
                logging.debug(f"Step 4: Simbolo Ativo: {symbol}")

                # Se ainda não temos símbolo válido, espera e tenta de novo
                if not symbol:
                    logging.warning("Nenhum símbolo detectado. Aguardando...")
                    await asyncio.sleep(1)
                    continue

                # 1. Coleta de Dados Estratificada (HFT Optimization)
                # Ciclo Rápido (Sempre): Tick & Book
                # Ciclo Lento (A cada 5 iterações): OHLC Histórico, Multi-Ativo, Conta
                
                if 'loop_count' not in locals(): loop_count = 0
                loop_count += 1
                
                # Coleta Ultra-Rápida (Prioridade 1)
                t0 = time_module.perf_counter()
                tick_info, book, tns = await asyncio.gather(
                    asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol),
                    asyncio.to_thread(bridge.get_order_book, symbol),
                    asyncio.to_thread(bridge.get_time_and_sales, symbol, n_ticks=50)
                )
                dt_gather_fast = (time_module.perf_counter() - t0) * 1000
                logging.debug(f"P1 Gather Time: {dt_gather_fast:.2f}ms")
                
                if tick_info:
                    last_price = tick_info.last
                    last_valid_price = last_price
                else:
                    last_price = last_valid_price
                    logging.warning("Tick Info falhou. Usando ultimo preco valido.")

                # Coleta Lenta (Prioridade 2 - a cada ~200ms-500ms dependendo do sleep)
                if loop_count % 10 == 1 or 'data_60' not in locals():
                    wdo_symbol = await asyncio.to_thread(bridge.get_current_symbol, "WDO")
                    multi_symbols = [symbol, "ITUB4", "PETR4", "VALE3", wdo_symbol or "WDO$"]
                    
                    multi_data, data_60, account_info, daily_realized, bluechips = await asyncio.gather(
                        asyncio.to_thread(bridge.get_synchronized_multi_asset_data, multi_symbols, n_candles=60),
                        asyncio.to_thread(bridge.get_market_data, symbol, n_candles=60),
                        asyncio.to_thread(bridge.mt5.account_info),
                        asyncio.to_thread(bridge.get_daily_realized_profit),
                        asyncio.to_thread(bridge.get_bluechips_data)
                    )
                    
                    # 1.2 Coleta de Dados Macro/Lenta (A cada ~5-10 segundos)
                    if loop_count % 50 == 1:
                        logging.debug("Iniciando coleta Macro (Notícias, Ajuste, Gap Trap)...")
                        headlines = await asyncio.to_thread(news_collector.get_latest_headlines, 5)
                        sentiment_score = await sentiment_engine.analyze_sentiment(headlines)
                        ai.latest_sentiment_score = sentiment_score
                        vol_expected, vol_reason = calendar.is_volatility_expected()
                        settlement_price = await asyncio.to_thread(bridge.get_settlement_price, symbol)
                        macro_change = await asyncio.to_thread(bridge.get_macro_data)
                        daily_rates = await asyncio.to_thread(bridge.mt5.copy_rates_from_pos, symbol, bridge.mt5.TIMEFRAME_D1, 0, 2)
                        logging.debug("Coleta Macro concluída.")
                        
                    logging.debug(f"Coleta Lenta executada (Loop {loop_count})")
                
                # 1.1 Processamento de Conta e Risco (CRÍTICO: Definir variáveis antes do uso)
                if account_info is None:
                    logging.warning(f"WAIT: account_info indisponível para {symbol}. Retrying...")
                    await asyncio.sleep(1)
                    continue
                    
                account = account_info._asdict()
                floating_profit = account_info.profit
                total_daily_profit = daily_realized + floating_profit
                # Validação de Risco Diário
                risk_ok, risk_msg = risk.check_daily_loss(total_daily_profit)
                
                # Validação de Dados de Mercado (Fail-Safe)
                if not isinstance(data_60, pd.DataFrame):
                    logging.warning(f"WAIT: data_60 não é DataFrame ({type(data_60)}). Ignorando iteração.")
                    await asyncio.sleep(1)
                    continue
                    
                if data_60.empty:
                    logging.warning(f"WAIT: Dados Históricos vazios para {symbol}. Ignorando iteração.")
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
                if len(returns_history) > 1000: returns_history.pop(0)
                
                reliability_ok, current_psr = risk.validate_reliability(returns_history)
                # ----------------------------------
                
                # Validação de Horário
                time_allowed = risk.is_time_allowed()
                
                latency_ms = (time_module.perf_counter() - start_time) * 1000
                if latency_ms > 200: # Tolerância maior em Python puro
                    logging.warning(f"HIGH LATENCY: {latency_ms:.2f}ms")
                
                # Heartbeat Log (1 min)
                if time_module.time() - last_heartbeat > 60:
                    logging.info(f"HEARTBEAT: {symbol} | PnL Dia: {total_daily_profit:.2f} | Risco: {'OK' if risk_ok else 'TRAVADO'} | Latency: {latency_ms:.1f}ms")
                    last_heartbeat = time_module.time()

                # 1.2 Calcular ATR (Average True Range)
                current_atr = 0.0
                avg_atr = 0.0
                if data_60 is not None and len(data_60) >= 28:
                    high_low = data_60['high'] - data_60['low']
                    current_atr = high_low.rolling(window=14).mean().iloc[-1]
                    avg_atr = high_low.mean()
                
                # 2. Processar Lógica de IA e Risco
                logging.debug("Iniciando processamento de IA...")
                # Sentimento agora é atualizado no ciclo lento (linha 249)
                obi = ai.detect_spoofing(book, tns)
                cvd_val = micro_analyzer.calculate_cvd(tns) 
                
                # Inferência SOTA Multi-Ativo (usa multi_data sincronizado)
                logging.debug("Executando inferência SOTA...")
                
                # Garantir 60 linhas e 5 canais (SOTA Multi-Ativo exige c_in=5)
                sota_input = multi_data
                if sota_input is None or len(sota_input) < 60:
                    logging.warning(f"SOTA: multi_data incompleto (len={len(sota_input) if sota_input is not None else 0}). Gerando dataframe de contingencia (5 canais).")
                    # Cria um DF de fallback com 60 linhas usando apenas a coluna 'close' de data_60 repetida
                    # Isso garante c_in=5 e len=60 para o ONNX não crashar
                    if data_60 is not None and not data_60.empty and 'close' in data_60.columns:
                        base_col = data_60['close'].values[-60:]
                        if len(base_col) < 60:
                            base_col = np.pad(base_col, (60 - len(base_col), 0), 'edge')
                    else:
                        base_col = np.zeros(60)
                        
                    sota_input = pd.DataFrame({
                        'c1': base_col, 'c2': base_col, 'c3': base_col, 'c4': base_col, 'c5': base_col
                    })
                    
                ai_predict_data = await inference.predict(sota_input)
                ai_confidence = ai_predict_data.get("confidence", 0.0) if isinstance(ai_predict_data, dict) else 0.0
                logging.debug(f"Inferência concluída. Confidence: {ai_confidence}")
                
                # Validação de Condição de Mercado (Estágio 2)
                volatility = data_60['close'].std() if data_60 is not None and not data_60.empty else 0
                regime = ai.detect_regime(volatility, obi)
                # macro_change movido para o ciclo lento
                
                 # Score Final (0-100) e Direção
                decision = ai.calculate_decision(
                    obi, 
                    ai.latest_sentiment_score, 
                    ai_predict_data, # Passamos o dict completo para o veto de incerteza
                    regime,
                    atr=current_atr,
                    volatility=volatility,
                    hour=current_hour
                )
                ai_total_score = decision["score"]
                ai_direction = decision["direction"]

                # --- ALPHA-X: OFI Ponderado (SOTA) ---
                # Substituindo Level 2 simples por Weighted OFI
                wen_ofi_val = micro_analyzer.calculate_wen_ofi(book)
                
                if wen_ofi_val > 500 and ai_direction == "BUY":
                    ai_total_score = min(100.0, ai_total_score + 4.0) # Peso ajustado para SOTA
                elif wen_ofi_val < -500 and ai_direction == "SELL":
                    ai_total_score = min(100.0, ai_total_score + 4.0)

                # --- ALPHA-X: PSR RELIABILITY VETO ---
                if not reliability_ok and len(returns_history) >= 30:
                    logging.warning(f"ALPHA-X HARD VETO: PSR insuficiente ({current_psr:.4f})")
                    ai_total_score = 50.0
                    ai_direction = "NEUTRAL"
                
                # --- HFT v2.0: CVD Turbo (Otimizado: Usar tns do gather P1) ---
                # Reutilizando tns já capturado no início do loop para evitar nova chamada MT5
                cvd_val = micro_analyzer.calculate_cvd(tns)
                
                cvd_threshold = 50.0 if "WDO" in symbol or "DOL" in symbol else 500.0
                
                if cvd_val > cvd_threshold and ai_direction == "BUY":
                    ai_total_score = min(100.0, ai_total_score + 5.0)
                    if ai_total_score > 80: logging.info(f"CVD TRIGGER (+5.0): Fluxo Comprador Forte ({cvd_val:.0f})")
                elif cvd_val < -cvd_threshold and ai_direction == "SELL":
                    ai_total_score = min(100.0, ai_total_score + 5.0)
                    if ai_total_score > 80: logging.info(f"CVD TRIGGER (+5.0): Fluxo Vendedor Forte ({cvd_val:.0f})")
                
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
                    
                    settlement_veto = False
                    settlement_msg = ""
                    # Veto COMPRA: Preço logo abaixo do ajuste (Resistência)
                    if ai_direction == "BUY" and -safe_dist < dist < 0:
                        settlement_veto = True
                        settlement_msg = f"Ajuste funcionando como Resistência (Dist: {dist:.1f})"
                    # Veto VENDA: Preço logo acima do ajuste (Suporte)
                    elif ai_direction == "SELL" and 0 < dist < safe_dist:
                        settlement_veto = True
                        settlement_msg = f"Ajuste funcionando como Suporte (Dist: {dist:.1f})"
                        
                    if settlement_veto:
                        logging.warning(f"HFT DEFENSE: Veto de Ajuste ({settlement_price}). {settlement_msg}")
                        ai_total_score = 50.0
                        ai_direction = "NEUTRAL"
                
                # 5b.1 Pinning (Opções)
                today_dt = datetime.now()
                if today_dt.weekday() == 4 and 15 <= today_dt.day <= 21:
                    if "10:00" <= current_hhmm <= "16:00" and regime == 0:
                        logging.info("PINNING ALERT: Vencimento Opções.")
                        ai_total_score = max(40.0, min(60.0, ai_total_score))

                # 5b.2 Gap Trap Protection - Otimizado: USA CACHE
                try:
                    # Reutilizar daily_rates buscado no ciclo lento
                    if daily_rates is not None and len(daily_rates) == 2:
                        prev_close = daily_rates[0]['close']
                        today_open = daily_rates[1]['open']
                        gap_pct = ((today_open - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                        
                        if gap_pct > 0.5 and cvd_val > 0 and ai_direction == "SELL":
                            logging.warning(f"GAP TRAP VETO: Alta ({gap_pct:.2f}%) + Fluxo Comprador.")
                            ai_total_score = 50.0
                            ai_direction = "NEUTRAL"
                        elif gap_pct < -0.5 and cvd_val < 0 and ai_direction == "BUY":
                            logging.warning(f"GAP TRAP VETO: Baixa ({gap_pct:.2f}%) + Fluxo Vendedor.")
                            ai_total_score = 50.0
                            ai_direction = "NEUTRAL"
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
                synthetic_idx = micro_analyzer.calculate_synthetic_index(bluechips)
                
                # Se Blue Chips estão fortemente contra, reduz o score
                if ai_direction == "BUY" and synthetic_idx < -0.05:
                    penalty = abs(synthetic_idx) * 100 # ex: 0.1% contra -> -10 pontos
                    ai_total_score = max(50.0, ai_total_score - penalty)
                    if synthetic_idx < -0.2: # Hard Veto se queda for > 0.2%
                         veto_active = True
                         veto_reason = f"VETO QUANT EXTREMO: Blue Chips Caindo Forte ({synthetic_idx:.2f}%)"
                elif ai_direction == "SELL" and synthetic_idx > 0.05:
                    penalty = abs(synthetic_idx) * 100
                    ai_total_score = max(50.0, ai_total_score - penalty)
                    if synthetic_idx > 0.2: # Hard Veto se alta for > 0.2%
                         veto_active = True
                         veto_reason = f"VETO QUANT EXTREMO: Blue Chips Subindo Forte ({synthetic_idx:.2f}%)"
                
                if veto_active:
                    logging.warning(f"🛑 {veto_reason}")
                    ai_total_score = 50.0
                    ai_direction = "NEUTRAL"

                market_condition = risk.validate_market_condition(symbol, regime, current_atr, avg_atr)
                market_ok = market_condition["allowed"]
                
                # --- RL SHADOW MODE ---
                try:
                    rl_state = [current_atr, obi, ai.latest_sentiment_score, ai_confidence, volatility, cvd_val, synthetic_idx]
                    action, log_prob = rl_agent.select_action(rl_state)
                    actions_map = {0: "BUY", 1: "SELL", 2: "HOLD"}
                    suggested = actions_map.get(action, "UNKNOWN")
                    if ai_total_score > 70:
                        logging.info(f"🤖 [RL SHADOW] Sugestão: {suggested} | Decisão Atual: {ai_direction}")
                except Exception as rl_e: 
                    logging.debug(f"Erro RL Shadow: {rl_e}")

                # --- TRAILING STOP (1s Check) ---
                if time_module.time() - last_trailing_check > 1.0:
                    last_trailing_check = time_module.time()
                    try:
                        positions = await asyncio.to_thread(bridge.mt5.positions_get, symbol=symbol)
                        if positions:
                            for pos in positions:
                                # --- ALPHA-X: TRIPLE BARRIER (TIME EXIT) ---
                                # Se a posição estiver aberta há mais de 15 minutos e não atingiu SL/TP, fechamos.
                                # Pos.time é em segundos (timestamp)
                                pos_age_min = (time_module.time() - pos.time) / 60
                                if pos_age_min > 15.0:
                                    logging.warning(f"ALPHA-X TIME EXIT: Posição {pos.ticket} aberta há {pos_age_min:.1f} min. Fechando a mercado.")
                                    await asyncio.to_thread(bridge.close_position, pos.ticket)
                                    continue
                                
                                is_wdo = "WDO" in symbol or "DOL" in symbol
                                # Configuração Trailing (Poderia vir do Config/Risk)
                                trigger_pts = 5.0 if is_wdo else 100.0 # Gatilho para iniciar
                                step_pts = 2.0 if is_wdo else 50.0 # Passo do trailing
                                
                                current_price = last_price
                                if pos.type == bridge.mt5.POSITION_TYPE_BUY:
                                    profit_pts = current_price - pos.price_open
                                    if profit_pts >= trigger_pts:
                                        new_sl = current_price - step_pts
                                        # Se novo SL for maior que o atual (subir o stop)
                                        if new_sl > pos.sl:
                                            # Anti-Violinada no SL Dinâmico
                                            new_sl = risk._apply_anti_violinada(symbol, new_sl, "buy")
                                            await asyncio.to_thread(bridge.update_sltp, pos.ticket, new_sl, pos.tp)
                                            logging.info(f"TRAILING STOP (BUY): SL movido para {new_sl}")
                                            
                                elif pos.type == bridge.mt5.POSITION_TYPE_SELL:
                                    profit_pts = pos.price_open - current_price
                                    if profit_pts >= trigger_pts:
                                        new_sl = current_price + step_pts
                                        # Se novo SL for menor que o atual (descer o stop)
                                        if pos.sl == 0 or new_sl < pos.sl:
                                             # Anti-Violinada no SL Dinâmico
                                            new_sl = risk._apply_anti_violinada(symbol, new_sl, "sell")
                                            await asyncio.to_thread(bridge.update_sltp, pos.ticket, new_sl, pos.tp)
                                            logging.info(f"TRAILING STOP (SELL): SL movido para {new_sl}")
                    except Exception as e:
                        logging.error(f"Erro no Trailing/Time Stop: {e}")

                if risk.should_force_close():
                    await asyncio.to_thread(panic_close_all)
                    logging.warning("Check Force Close: 17:50 atingido.")

                # --- LÓGICA DE DECISÃO DE TRADE ---
                if risk.allow_autonomous and ai_total_score >= 85 and risk_ok and market_ok and time_allowed:
                    if ai_direction in ["BUY", "SELL"]:
                        side = "buy" if ai_direction == "BUY" else "sell"
                        
                        macro_ok, macro_msg = risk.check_macro_filter(side, macro_change)
                        if not macro_ok:
                            logging.warning(f"AUTÔNOMO BLOQUEADO: {macro_msg}")
                        else:
                            # EXECUÇÃO AUTORIZADA
                            logging.info(f"AUTÔNOMO: Disparando {side.upper()} via Score {ai_total_score:.1f}")
                            
                            is_sniper = False
                            if ai_total_score > 90:
                                if (side == "buy" and cvd_val >= 300) or (side == "sell" and cvd_val <= -300):
                                    is_sniper = True
                            
                            if is_sniper:
                                order_type = bridge.mt5.ORDER_TYPE_BUY if side == "buy" else bridge.mt5.ORDER_TYPE_SELL
                                logging.info("🎯 SNIPER MODE: MARKET ORDER")
                                
                                # Obter Tick Fresco para a ordem
                                tick_info = await asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol)
                                current_order_price = tick_info.ask if side == "buy" else tick_info.bid
                                
                                # [SOTA] Volatility Sizing
                                point_value = 10.0 if "WDO" in symbol or "DOL" in symbol else 0.20
                                sota_lots = risk.calculate_volatility_sizing(account['balance'], current_atr, point_value)
                                final_lots = max(1, int(sota_lots))
                                
                                params = risk.get_order_params(symbol, order_type, current_order_price, final_lots)
                                params["symbol"] = symbol
                                params["comment"] = "AUTO SNIPER"
                                
                                # Execução Resiliente (Trata Requotes)
                                if risk.dry_run:
                                    logging.warning(f"DRY-RUN: Simulando Ordem SNIPER {side.upper()} de {final_lots} lotes @ {current_order_price}")
                                    # Criação de um mock result válido
                                    class MockResult:
                                        retcode = bridge.mt5.TRADE_RETCODE_DONE
                                        price = current_order_price
                                    result = MockResult()
                                else:
                                    result = await asyncio.to_thread(bridge.place_resilient_order, params)
                                
                                if result and result.retcode == bridge.mt5.TRADE_RETCODE_DONE:
                                    mode_tag = "SIMULATION_SNIPER" if risk.dry_run else "AUTO_SNIPER"
                                    persistence.save_trade(symbol, side, current_order_price, final_lots, mode_tag)
                                    persistence.save_state("last_auto_trade", f"{side} at {current_order_price}")
                                    slippage = abs(result.price - current_order_price)
                                    logging.info(f"TRADE SUCCESS ({mode_tag}): Slippage {slippage:.1f} pts")
                                else:
                                    msg = result.comment if hasattr(result, 'comment') else "Timeout/None"
                                    logging.error(f"Falha Crítica na Execução Sniper: {msg}")

                            else:
                                # --- PASSIVE ENTRY: LIMIT ORDER (HFT SOTA) ---
                                order_type = bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else bridge.mt5.ORDER_TYPE_SELL_LIMIT
                                logging.info("🛡️ PASSIVE ENTRY: LIMIT ORDER (Top Book)")
                                
                                # Pegar Preço Do Topo do Book (Comprar no Bid, Vender no Ask)
                                # Isso garante spread a favor, mas risco de não executar
                                tick_info = await asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol)
                                # IMPORTANTE: Limit Buy é abaixo do preço atual (Bid), Limit Sell é acima (Ask)?
                                # Não! Limit Buy deve ser <= Ask. Se colocarmos no Bid, estamos na fila passiva.
                                # Se colocarmos no Ask, vira Market praticamente.
                                # Estratégia HFT: Colocar no BID (para compra) ou ASK (para venda) e esperar ser agredido.
                                limit_price = tick_info.bid if side == "buy" else tick_info.ask
                                
                                valid_comp, reason_comp = await asyncio.to_thread(bridge.validate_order_compliance, symbol, limit_price)
                                
                                if not valid_comp:
                                     logging.warning(f"BLOCK Compliance: {reason_comp}")
                                else:

                                    # [SOTA] Volatility Sizing
                                    point_value = 10.0 if "WDO" in symbol or "DOL" in symbol else 0.20
                                    sota_lots = risk.calculate_volatility_sizing(account['balance'], current_atr, point_value)
                                    
                                    # Ajuste fino de lotes (step)
                                    vol_step = tick_info.volume_step if hasattr(tick_info, 'volume_step') else 1.0
                                    # Arredondar para o step mais próximo
                                    final_lots = round(sota_lots / vol_step) * vol_step
                                    final_lots = max(vol_step, final_lots)
                                    
                                    logging.info(f"[SOTA] HFT Limit: {final_lots} lotes @ {limit_price}")

                                    # Enviar Ordem Limitada
                                    if risk.dry_run:
                                        logging.warning(f"DRY-RUN: Simulando Ordem LIMIT {side.upper()} de {final_lots} lotes @ {limit_price}")
                                        class MockResultLimit:
                                            retcode = bridge.mt5.TRADE_RETCODE_DONE
                                            order = 999999
                                        result = MockResultLimit()
                                    else:
                                        result = await asyncio.to_thread(
                                            bridge.place_limit_order, 
                                            symbol, order_type, limit_price, final_lots, 
                                            sl=0, tp=0, comment="AUTO HFT LIMIT"
                                        )
                                    
                                    if result and result.retcode == bridge.mt5.TRADE_RETCODE_DONE:
                                        order_ticket = result.order
                                        mode_tag = "SIMULACAO_LIMITE_PENDENTE" if risk.dry_run else "PENDENTE"
                                        logging.info(f"Ordem {mode_tag} Aberta: {order_ticket}. Aguardando 5s...")
                                        
                                        # --- HFT TTL LOOP (5 segundos) ---
                                        filled = False
                                        for _ in range(10): # 10x 0.5s = 5s
                                            await asyncio.sleep(0.5)
                                            status = await asyncio.to_thread(bridge.check_order_status, order_ticket)
                                            
                                            # [UX] Enviar Heartbeat para Frontend não congelar e mostrar status
                                            try:
                                                hb_packet = {
                                                    "symbol": symbol,
                                                    "price": limit_price,
                                                    "obi": obi,
                                                    "sentiment": ai.latest_sentiment_score,
                                                    "risk_status": {
                                                        "ai_score": ai_total_score,
                                                        "order_status": "PENDING_HFT",
                                                        "ticket": order_ticket
                                                    },
                                                    "account": account,
                                                    "timestamp": time_module.time()
                                                }
                                                await websocket.send_json(hb_packet)
                                            except Exception:
                                                pass # Ignorar erros de socket no loop rápido

                                            if status == "FILLED":
                                                filled = True
                                                logging.info(f"HFT FILL: Ordem {order_ticket} executada no spread!")
                                                persistence.save_trade(symbol, side, limit_price, final_lots, "AUTO_LIMIT_FILLED")
                                                break
                                            elif status == "CANCELED":
                                                logging.warning(f"Ordem {order_ticket} cancelada externamente.")
                                                break
                                        
                                        if not filled:
                                            logging.info(f"HFT TTL Expired: Tentando cancelar {order_ticket}...")
                                            cancel_success = await asyncio.to_thread(bridge.cancel_order, order_ticket)
                                            
                                            if not cancel_success:
                                                # RACE CONDITION CHECK:
                                                # Se falhou cancelar, pode ter sido executada no último milissegundo.
                                                logging.warning(f"Falha ao cancelar {order_ticket}. Verificando se foi executada (Race Condition)...")
                                                final_status = await asyncio.to_thread(bridge.check_order_status, order_ticket)
                                                
                                                if final_status == "FILLED":
                                                    logging.info(f"RACE CONDITION WIN: Ordem {order_ticket} foi executada no limite do tempo!")
                                                    persistence.save_trade(symbol, side, limit_price, final_lots, "AUTO_LIMIT_FILLED_RACE")
                                                else:
                                                    logging.error(f"Ordem {order_ticket} presa em estado incerto: {final_status}")
                                            else:
                                                logging.info(f"Ordem {order_ticket} cancelada com sucesso (TTL).")

                                            # Opcional: Aqui poderíamos agredir a mercado (Chase), mas HFT puro evita isso. 
                                            # Vamos abortar para preservar a vantagem estatística.
                                    else:
                                        msg = result.comment if result else "Timeout/None"
                                        logging.error(f"Falha ao enviar Limit Order: {msg}")
                
                # LOG DE BLOQUEIO ALTA CONFIANÇA
                elif risk.allow_autonomous and ai_total_score >= 75:
                     if not market_ok:
                         logging.info(f"SINAL FORTE BLOQUEADO (RISCO MERCADO): {market_condition['reason']}")
                     elif not risk_ok:
                         logging.info(f"SINAL FORTE BLOQUEADO (MONEY MANAGEMENT): {risk_msg}")
                     elif not time_allowed:
                         pass # Horário bloqueado é comum, não poluir log

                # 4. Dados de Compliance (Limites)
                info = await asyncio.to_thread(bridge.mt5.symbol_info, symbol)
                session_limits = {
                    "lower": getattr(info, 'session_price_limit_min', 0.0) if info else 0,
                    "upper": getattr(info, 'session_price_limit_max', 0.0) if info else 0,
                    "ref": getattr(info, 'session_price_ref', 0.0) if info else 0
                }

                # 5. Enviar Pacote ao Frontend (Consolidado)
                try:
                    # Camada Macro (já processada no ciclo lento)
                    packet = {
                        "symbol": str(symbol),
                        "price": float(last_price),
                        "obi": float(obi),
                        "ai_confidence": float(ai_confidence),
                        "book": book, 
                        "sentiment": {
                            "score": float(sentiment_score),
                            "headlines": headlines
                        },
                        "calendar": {
                            "volatility_expected": vol_expected,
                            "reason": str(vol_reason)
                        },
                        "ai_prediction": decision,
                        "account": account,
                        "daily_realized": float(daily_realized),
                        "latency_ms": float(latency_ms),
                        "risk_status": {
                            "time_ok": time_allowed,
                            "loss_ok": risk_ok,
                            "profit_day": float(total_daily_profit),
                            "atr": float(current_atr),
                            "uncertainty_range": float(ai_predict_data.get("uncertainty_norm", 0.0) if isinstance(ai_predict_data, dict) else 0.0),
                            "lower_bound": float(ai_predict_data.get("lower_bound_norm", last_price) if isinstance(ai_predict_data, dict) else last_price),
                            "upper_bound": float(ai_predict_data.get("upper_bound_norm", last_price) if isinstance(ai_predict_data, dict) else last_price),
                            "weighted_ofi": float(wen_ofi_val),
                            "synthetic_index": float(synthetic_idx),
                            "psr": float(current_psr),
                            "regime": int(regime)
                        },
                        "timestamp": (datetime.utcnow() - timedelta(hours=3)).timestamp()
                    }
                    logging.debug("Preparando pacote para envio...")
                    await websocket.send_json(packet)
                    logging.debug("Pacote enviado via WebSocket.")
                except Exception as packet_e:
                    logging.error(f"Erro ao processar/enviar pacote WS: {packet_e}")
                    traceback.print_exc()
                
                persistence.save_state("last_obi", float(obi))
                persistence.save_state("latency_ms", float(latency_ms))

                # 6. Housekeeping (10s)
                if time_module.time() - last_cleanup_time > 10: 
                    last_cleanup_time = time_module.time()
                    
                    try:
                        base_asset = "WDO" if "WDO" in symbol or "DOL" in symbol else "WIN"
                        new_symbol = bridge.get_current_symbol(base_asset)
                        if new_symbol and new_symbol != symbol and "$" not in new_symbol:
                            logging.warning(f"🔄 ROLLOVER: {symbol} -> {new_symbol}")
                            symbol = new_symbol
                            await asyncio.to_thread(panic_close_all) 
                            continue
                    except Exception as e:
                        logging.error(f"Erro Auto-Rollover: {e}")
    
                    orders = await asyncio.to_thread(bridge.mt5.orders_get, symbol=symbol)
                    if orders:
                        now_ts = time_module.time()
                        for order in orders:
                            if (now_ts - order.time_setup) > 60:
                                req = {
                                    "action": bridge.mt5.TRADE_ACTION_REMOVE,
                                    "order": order.ticket,
                                    "symbol": symbol,
                                }
                                await asyncio.to_thread(bridge.mt5.order_send, req)
                                logging.info(f"Cleanup: Cancelando ordem velha {order.ticket}")
    
                # Loop control
                await asyncio.sleep(0.01)
            
            except asyncio.CancelledError:
                raise # Respeitar shutdown
            except Exception as e:
                logging.error(f"Erro (recuperável) no loop principal: {e}", exc_info=True)
                await asyncio.sleep(1) # Backoff para não floodar logs
    except WebSocketDisconnect:
        logging.info("WebSocket desconectado.")
    except Exception as e:
        logging.critical(f"Erro fatal no loop principal: {e}")
        await websocket.close()

@app.post("/config/autonomous")
async def toggle_autonomous(enabled: bool):
    """Ativa ou desativa a execução automática de ordens."""
    risk.allow_autonomous = enabled
    logging.info(f"Modo Autônomo: {'ATIVO' if enabled else 'INATIVO'}")
    return {"status": "success", "autonomous": enabled}

@app.post("/order")
async def place_order(req: OrderRequest):
    """Endpoint para receber ordens do frontend."""
    logging.info(f"Requisição de ordem recebida: {req.dict()}")
    side = req.side.lower()
    volume = float(req.volume) # Garantir float para o bridge.mt5
    # 0. Kill Switch / Panic Mode
    if side in ["close_all", "panic"]:
        logging.warning("Ordem de PÂNICO recebida via API.")
        panic_close_all()
        return {"status": "success", "message": "PANIC_TRIGGERED"}

    if not bridge.connected:
        return {"status": "error", "message": "MT5 não conectado"}

    # 1. Validações de risco
    if not risk.is_time_allowed():
        return {"status": "error", "message": "Horário não permitido"}
        
    account_info = bridge.mt5.account_info()
    if not risk.check_daily_loss(account_info.profit if account_info else 0):
        return {"status": "error", "message": "Limite de perda diária atingido"}

    # 2. Preparar Ordem (B3 usa Netting)
    symbol = bridge.get_current_symbol("WIN")
    order_type = bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else bridge.mt5.ORDER_TYPE_SELL_LIMIT
    price = bridge.mt5.symbol_info_tick(symbol).ask if side == "buy" else bridge.mt5.symbol_info_tick(symbol).bid
    
    # Validação Compliance (Túneis)
    valid, reason = bridge.validate_order_compliance(symbol, price)
    if not valid:
        logging.warning(f"Ordem rejeitada por compliance: {reason}")
        return {"status": "error", "message": reason}

    params = risk.get_order_params(symbol, order_type, price, int(volume))
    params["symbol"] = symbol
    
    # B3 OCO: Adicionar Stop Loss e Take Profit se definido no RiskManager
    # (Em modo Netting, SL/TP são modificações da posição ou via ordens pendentes complexas)
    # Aqui usamos o SL/TP padrão do get_order_params
    
    # 3. Enviar Ordem
    result = bridge.mt5.order_send(params)
    
    if result.retcode != bridge.mt5.TRADE_RETCODE_DONE:
        logging.error(f"Erro ao enviar ordem: {result.comment}")
        return {"status": "error", "message": f"Erro MT5: {result.comment}"}

    persistence.save_trade(symbol, side, price, volume)
    persistence.save_state("last_trade", f"{side} {volume} at {price}")
    return {"status": "success", "order_id": result.order}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
