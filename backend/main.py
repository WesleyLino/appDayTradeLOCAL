from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from .mt5_bridge import MT5Bridge
from backend.risk_manager import RiskManager
from backend.ai_core import AICore, InferenceEngine
from backend.persistence import PersistenceManager
from backend.rl_agent import PPOAgent # HFT v2.0
from backend.microstructure_analyzer import MicrostructureAnalyzer # HFT v2.0
import numpy as np
from .data_collector import DataCollector
import time as time_module
import logging
import keyboard
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

bridge = MT5Bridge()
risk = RiskManager()
ai = AICore()
persistence = PersistenceManager()
import os
collector = DataCollector("WIN$")
weights_path = os.path.join(os.path.dirname(__file__), "patchtst_weights.pth")
inference = InferenceEngine(weights_path)

@app.on_event("startup")
async def startup_event():
    bridge.connect()
    # Atalho Global de Pânico: Ctrl+Q para zerar tudo
    
    # Verificar recursos críticos
    missing_resources = inference.check_resources()
    if missing_resources:
        logging.critical(f"RECURSOS FALTANDO: {', '.join(missing_resources)}")
        # Poderíamos travar o startup, mas melhor avisar e rodar em modo degradado
    
    # Injeção de Dependência (opcional, já que passamos no loop, mas boa prática)
    ai.inference_engine = inference
    
    keyboard.add_hotkey('ctrl+q', lambda: panic_close_all())
    logging.info("Kill Switch ativo: Pressione Ctrl+Q para ZERAR TUDO.")

def panic_close_all():
    """Zera todas as posições abertas imediatamente."""
    logging.warning("!!! BOTÃO DE PÂNICO ACIONADO !!!")
    if bridge.connected:
        mt5 = bridge.mt5
        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                # B3 Netting: Enviar ordem oposta para zerar
                order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": order_type,
                    "price": price,
                    "deviation": 10,
                    "magic": 123456,
                    "comment": "PANIC CLOSE",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_FOK,
                }
                result = mt5.order_send(request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logging.error(f"Falha ao zerar posição {pos.ticket}: {result.comment}")
        
        persistence.save_state("panic_status", "CLOSED_ALL")

@app.on_event("shutdown")
async def shutdown_event():
    bridge.disconnect()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logging.info("Frontend conectado via WebSocket.")
    
    # Inicialização do Agente RL (Shadow Mode)
    # State: [ATR, OBI, Sentiment, PatchTST_Score, Volatility, CVD, Synthetic_Index]
    rl_agent = PPOAgent(input_dim=7, n_actions=3) 
    micro_analyzer = MicrostructureAnalyzer() # Inicializa Microestrutura
    logging.info("RL Agent (PPO) inicializado em Shadow Mode.")
    logging.info("Microestrutura (CVD) inicializada.")

    # Loop Principal
    last_cleanup_time = 0
    last_trailing_check = 0
    last_heartbeat = time_module.time()
    
    # Variáveis de Estado Persistentes no Loop
    symbol = "WIN$" # Inicial
    returns_history = []
    prev_total_profit = 0.0
    current_day = datetime.now().day
    
    try:
        while True:
            # --- 0. CHECK CONEXÃO MT5 ---
            if not bridge.check_connection():
                if time_module.time() - last_heartbeat > 30.0:
                    logging.error("Conexão MT5 perdida ou Terminal instável. Pausando execução...")
                await asyncio.sleep(5) 
                last_heartbeat = time_module.time()
                continue

            try: # [HFT v2.1] Iteration-level error handling
                # 0. Obter Símbolo (Async Wrapper)
                current_symbol = await asyncio.to_thread(bridge.get_current_symbol, "WIN")
                if current_symbol:
                    symbol = current_symbol

                # Se ainda não temos símbolo válido, espera e tenta de novo
                if not symbol or "$" in symbol:
                    await asyncio.sleep(1)
                    continue

                # 1. Obter Dados de Mercado em Paralelo (Async)
                    # Executamos as chamadas pesadas de I/O do MT5 em threads separadas
                    # Adicionamos get_daily_realized_profit para cálculo exato de PnL
                    data_60, book, tns, account_info, daily_realized = await asyncio.gather(
                        asyncio.to_thread(bridge.get_market_data, symbol, n_candles=60),
                        asyncio.to_thread(bridge.get_order_book, symbol),
                        asyncio.to_thread(bridge.get_time_and_sales, symbol, n_ticks=100),
                        asyncio.to_thread(bridge.mt5.account_info),
                        asyncio.to_thread(bridge.get_daily_realized_profit)
                    )
                    
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
                    if data_60 is None or data_60.empty:
                        logging.warning(f"WAIT: Dados Históricos indisponíveis para {symbol}. Ignorando iteração.")
                        await asyncio.sleep(1)
                        continue
                    
                    # --- ALPHA-X: PSR & RELIABILITY ---
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
                    await ai.update_sentiment()
                    obi = ai.detect_spoofing(book, tns)
                    ai_predict_data = await inference.predict(data_60)
                    ai_confidence = ai_predict_data.get("score", 0.5) if isinstance(ai_predict_data, dict) else ai_predict_data
                    
                    # Validação de Condição de Mercado (Estágio 2)
                    volatility = data_60['close'].std() if data_60 is not None else 0
                    regime = ai.detect_regime(volatility, obi)
                    macro_change = await asyncio.to_thread(bridge.get_macro_data) 
                    
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
                    
                    # --- HFT v2.0: CVD Turbo ---
                    ticks_df = await asyncio.to_thread(bridge.get_bulk_ticks, symbol, n=1000)
                    cvd_val = micro_analyzer.calculate_cvd(ticks_df)
                    
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

                    # 5.3 Defesa de Ajuste (Settlement Trap)
                    settlement_price = await asyncio.to_thread(bridge.get_settlement_price, symbol)
                    
                    # Obter preço atual do TICK para precisão (não candle anterior)
                    tick_info = await asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol)
                    last_price = tick_info.last if tick_info else (data_60.iloc[-1]['close'] if data_60 is not None else 0)
                    
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

                    # 5b.2 Gap Trap Protection
                    try:
                        # Reutilizar dailys se possível ou buscar leve
                        daily_rates = await asyncio.to_thread(bridge.mt5.copy_rates_from_pos, symbol, bridge.mt5.TIMEFRAME_D1, 0, 2)
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
                    
                    # Blue Chips Soft Veto & Influence
                    bluechips = await asyncio.to_thread(bridge.get_bluechips_data)
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
                            logging.error(f"Erro no Trailing Stop: {e}")

                    if risk.should_force_close():
                        await asyncio.to_thread(panic_close_all)
                        logging.warning("Check Force Close: 17:50 atingido.")

                    # --- LÓGICA DE DECISÃO DE TRADE ---
                    if risk.allow_autonomous and ai_total_score >= 75 and risk_ok and market_ok and time_allowed:
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
                                else:
                                    order_type = bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else bridge.mt5.ORDER_TYPE_SELL_LIMIT
                                    logging.info("🛡️ PASSIVE ENTRY: LIMIT ORDER")
                                
                                # Obter Tick Fresco para a ordem
                                tick_info = await asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol)
                                current_order_price = tick_info.ask if side == "buy" else tick_info.bid
                                
                                valid_comp, reason_comp = await asyncio.to_thread(bridge.validate_order_compliance, symbol, current_order_price)
                                
                                if not valid_comp:
                                     logging.warning(f"BLOCK Compliance: {reason_comp}")
                                else:
                                    # [SOTA] Volatility Sizing
                                    # Calcula lotes baseados na volatilidade atual
                                    point_value = 10.0 if "WDO" in symbol or "DOL" in symbol else 0.20
                                    sota_lots = risk.calculate_volatility_sizing(account['balance'], current_atr, point_value)
                                    # Arredondar para inteiro (MT5 stocks) ou step mínimo (futuros é 1)
                                    final_lots = max(1, int(sota_lots))
                                    
                                    logging.info(f"[SOTA] Volatility Sizing: {final_lots} lotes (ATR: {current_atr:.1f})")

                                    params = risk.get_order_params(symbol, order_type, current_order_price, final_lots)
                                    params["symbol"] = symbol
                                    params["comment"] = "AUTO-RESILIENTE SCORE >= 75"
                                    
                                    # Execução Resiliente (Trata Requotes)
                                    result = await asyncio.to_thread(bridge.place_resilient_order, params)
                                    
                                    if result and result.retcode == bridge.mt5.TRADE_RETCODE_DONE:
                                        persistence.save_trade(symbol, side, current_order_price, final_lots, "AUTO_DONE")
                                        persistence.save_state("last_auto_trade", f"{side} at {current_order_price}")
                                        # Log de Slippage: Preço Executado vs Preço Solicitado
                                        slippage = abs(result.price - current_order_price)
                                        logging.info(f"TRADE SUCCESS: Slippage {slippage:.1f} pts")
                                    else:
                                        msg = result.comment if result else "Timeout/None"
                                        logging.error(f"Falha Crítica na Execução: {msg}")
                    
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
                        "lower": info.session_price_limit_min if info else 0,
                        "upper": info.session_price_limit_max if info else 0,
                        "ref": info.session_price_ref if info else 0
                    }

                    # 5. Enviar Pacote ao Frontend
                    packet = {
                        "symbol": symbol,
                        "price": last_price,
                        "obi": obi,
                        "book": book, 
                        "sentiment": ai.latest_sentiment_score,
                        "ai_confidence": ai_confidence,
                        "synthetic_index": synthetic_idx,
                        "regime": regime,
                        "latency_ms": latency_ms,
                        "risk_status": {
                            "time_ok": time_allowed,
                            "loss_ok": risk_ok,
                            "profit_day": total_daily_profit,
                            "atr": current_atr,
                            "ai_score": ai_total_score,
                            "ai_direction": ai_direction,
                            "limits": session_limits
                        },
                        "sota": {
                           "forecast": ai_predict_data.get("forecast", last_price) if isinstance(ai_predict_data, dict) else last_price,
                           "confidence": ai_confidence,
                           "uncertainty_range": ai_predict_data.get("uncertainty", 0.0) if isinstance(ai_predict_data, dict) else 0.0,
                           "weighted_ofi": wen_ofi_val,
                           "regime": regime
                        },
                        "account": account,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    await websocket.send_json(packet)
                    
                    persistence.save_state("last_obi", obi)
                    persistence.save_state("latency_ms", latency_ms)

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
                logging.error(f"Erro (recuperável) no loop principal: {e}")
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
    side = req.side.lower()
    volume = req.volume
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
