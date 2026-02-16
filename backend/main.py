from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from .mt5_bridge import MT5Bridge
from backend.risk_manager import RiskManager
from backend.ai_core import AICore, InferenceEngine
from backend.persistence import PersistenceManager
from backend.rl_agent import PPOAgent # HFT v2.0
from backend.microstructure import MicrostructureAnalyzer # HFT v2.0
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
    # State: [ATR, OBI, Sentiment, PatchTST_Score, Volatility]
    rl_agent = PPOAgent(input_dim=5, n_actions=3) 
    micro_analyzer = MicrostructureAnalyzer() # Inicializa Microestrutura
    logging.info("RL Agent (PPO) inicializado em Shadow Mode.")
    logging.info("Microestrutura (CVD) inicializada.")

    # Loop Principal
    last_cleanup_time = 0
    
    try:
        while True:
            if bridge.connected:
                start_time = time_module.perf_counter()
                
                # 0. Obter Símbolo (Async Wrapper)
                symbol = await asyncio.to_thread(bridge.get_current_symbol, "WIN")
                
                if symbol:
                    # 1. Obter Dados de Mercado em Paralelo (Async)
                    # Executamos as chamadas pesadas de I/O do MT5 em threads separadas
                    data_60, book, tns, account_info = await asyncio.gather(
                        asyncio.to_thread(bridge.get_market_data, symbol, n_candles=60),
                        asyncio.to_thread(bridge.get_order_book, symbol),
                        asyncio.to_thread(bridge.get_time_and_sales, symbol, n_ticks=100),
                        asyncio.to_thread(bridge.mt5.account_info)
                    )
                    
                    account = account_info._asdict() if account_info else {}
                    
                    latency_ms = (time_module.perf_counter() - start_time) * 1000
                    if latency_ms > 50:
                        logging.warning(f"HIGH LATENCY ALERT: {latency_ms:.2f}ms")
                    
                    # 1.1 Calcular ATR (Average True Range - Provisório Local)
                    current_atr = 0.0
                    avg_atr = 0.0
                    if data_60 is not None and len(data_60) >= 28:
                        high_low = data_60['high'] - data_60['low']
                        current_atr = high_low.rolling(window=14).mean().iloc[-1]
                        avg_atr = high_low.mean()
                    
                    # 2. Processar Lógica de IA e Risco
                    await ai.update_sentiment()
                    obi = ai.detect_spoofing(book, tns)
                    ai_confidence = await inference.predict(data_60)
                    
                    # Validação de Condição de Mercado (Estágio 2)
                    volatility = data_60['close'].std() if data_60 is not None else 0
                    regime = ai.detect_regime(volatility, obi)
                    macro_change = await asyncio.to_thread(bridge.get_macro_data) # HFT v2.0 Macro Monitor
                    
                    # HFT v2.0: Meta-Learner - Preparar features extras
                    from datetime import datetime
                    current_hour = datetime.now().hour
                    
                    # Score Final (0-100) e Direção (Com Regime Adaptativo + Meta-Learner)
                    decision = ai.calculate_decision(
                        obi, 
                        ai.latest_sentiment_score, 
                        ai_confidence, 
                        regime,
                        atr=current_atr,
                        volatility=volatility,
                        hour=current_hour
                    )
                    ai_total_score = decision["score"]
                    ai_direction = decision["direction"]

                    # --- HFT v2.0: CVD Turbo ---
                    # Coleta Ticks e Calcula CVD
                    ticks_df = await asyncio.to_thread(bridge.get_bulk_ticks, symbol, n=1000)
                    cvd_val = micro_analyzer.calculate_cvd(ticks_df)
                    
                    # Ajuste Fino do Score (Turbo)
                    # WIN: > 500 contratos é relevante
                    # WDO: > 50 contratos é relevante
                    cvd_threshold = 50.0 if "WDO" in symbol or "DOL" in symbol else 500.0
                    
                    if cvd_val > cvd_threshold and ai_direction == "BUY":
                        ai_total_score = min(100.0, ai_total_score + 5.0)
                        logging.info(f"CVD TRIGGER (+5.0): Fluxo Comprador Forte ({cvd_val:.0f})")
                    elif cvd_val < -cvd_threshold and ai_direction == "SELL":
                        ai_total_score = min(100.0, ai_total_score + 5.0)
                        logging.info(f"CVD TRIGGER (+5.0): Fluxo Vendedor Forte ({cvd_val:.0f})")
                    # ---------------------------

                    # --- FASE 3: HARD VETO (Anti-Alucinação) ---
                    # Bloqueia trades quando IA e mercado real divergem
                    veto_active = False
                    veto_reason = ""
                    
                    # Regra 1: IA otimista, mas Fluxo Real é Venda Pesada
                    if ai_direction == "BUY" and cvd_val < -cvd_threshold:
                        veto_active = True
                        veto_reason = f"DIVERGÊNCIA: IA sugere COMPRA, mas CVD mostra Venda Agressiva ({cvd_val:.0f})"
                    
                    # Regra 2: IA pessimista, mas Fluxo Real é Compra Pesada
                    elif ai_direction == "SELL" and cvd_val > cvd_threshold:
                        veto_active = True
                        veto_reason = f"DIVERGÊNCIA: IA sugere VENDA, mas CVD mostra Compra Agressiva ({cvd_val:.0f})"
                    
                    # Aplicar Veto
                    if veto_active:
                        logging.warning(f"🛑 SINAL IA BLOQUEADO: {veto_reason}")
                        ai_total_score = 50.0  # Reset para neutro
                        ai_direction = "NEUTRAL"
                    # -------------------------------------------

                    market_condition = risk.validate_market_condition(symbol, regime, current_atr, avg_atr)
                    market_ok = market_condition["allowed"]
                    
                    # --- RL SHAWDOW MODE (HFT v2.0) ---
                    # Coleta estado atual para o agente
                    try:
                        rl_state = [current_atr, obi, ai.latest_sentiment_score, ai_confidence, volatility]
                        action, _ = rl_agent.select_action(rl_state)
                        # Apenas loga, não executa (Shadow)
                        rl_action_str = ["HOLD", "BUY", "SELL"][action]
                        # logging.info(f"[RL SHADOW] Action: {rl_action_str} | State: {rl_state}") 
                    except Exception as e:
                        logging.error(f"Erro RL Shadow: {e}")
                    # ----------------------------------

                    if risk.should_force_close():
                         # Executar Panic em Thread separada para não bloquear
                        await asyncio.to_thread(panic_close_all)
                        logging.warning("Execução compulsória 17:50 acionada.")

                    if risk.allow_autonomous and ai_total_score >= 85 and risk_ok and market_ok and time_allowed:
                        if ai_direction in ["BUY", "SELL"]:
                            side = "buy" if ai_direction == "BUY" else "sell"
                            
                            # HFT v2.0: Filtro Macro (S&P500)
                            macro_ok, macro_msg = risk.check_macro_filter(side, macro_change)
                            if not macro_ok:
                                logging.warning(f"AUTÔNOMO BLOQUEADO: {macro_msg}")
                                continue

                            logging.info(f"AUTÔNOMO: Disparando {side.upper()} via Score {ai_total_score:.1f}")
                            
                            # HFT v2.0: Gestão de Ordens Híbrida
                            if ai_total_score > 90:
                                order_type = bridge.mt5.ORDER_TYPE_BUY if side == "buy" else bridge.mt5.ORDER_TYPE_SELL
                                logging.info(f"ALTA CONVICÇÃO (Score {ai_total_score:.1f}): Executando MARKET ORDER")
                            else:
                                order_type = bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else bridge.mt5.ORDER_TYPE_SELL_LIMIT
                                logging.info(f"ENTRADA PADRÃO (Score {ai_total_score:.1f}): Executando LIMIT ORDER")
                            
                            # Obter Tick Info (Async)
                            tick_info = await asyncio.to_thread(bridge.mt5.symbol_info_tick, symbol)
                            current_price = tick_info.ask if side == "buy" else tick_info.bid
                            
                            # Validação Compliance Pre-Trade (Async)
                            valid_comp, reason_comp = await asyncio.to_thread(bridge.validate_order_compliance, symbol, current_price)
                            
                            if not valid_comp:
                                 logging.warning(f"AUTÔNOMO BLOQUEADO: Compliance - {reason_comp}")
                            else:
                                params = risk.get_order_params(symbol, order_type, current_price, 1) # Default 1 contrato
                                params["symbol"] = symbol
                                params["comment"] = "AUTO-EXEC SCORE >= 85"
                                
                                # Enviar Ordem (Async)
                                result = await asyncio.to_thread(bridge.mt5.order_send, params)
                                
                                if result.retcode == bridge.mt5.TRADE_RETCODE_DONE:
                                    persistence.save_trade(symbol, side, current_price, 1, "AUTO_DONE")
                                    persistence.save_state("last_auto_trade", f"{side} at {current_price}")
                                else:
                                    logging.error(f"Erro no disparo automático: {result.comment}")
                    elif risk.allow_autonomous and ai_total_score >= 85:
                         # Logar motivo do bloqueio se score for alto mas risco impedir
                         if not market_ok:
                             logging.info(f"SINAL DE ALTA CONFIANÇA BLOQUEADO POR RISCO: {market_condition['reason']}")
                         elif not risk_ok:
                             logging.info(f"SINAL DE ALTA CONFIANÇA BLOQUEADO POR PERDA DIÁRIA: {risk_msg}")

                    # 4. Dados de Compliance (Limites) - Async Wrapper
                    info = await asyncio.to_thread(bridge.mt5.symbol_info, symbol)
                    session_limits = {
                        "lower": info.session_price_limit_min if info else 0,
                        "upper": info.session_price_limit_max if info else 0,
                        "ref": info.session_price_ref if info else 0
                    }

                    # 5. Enviar Pacote ao Frontend
                    
                    # 5. Enviar Pacote ao Frontend (Manter Contrato Original)
                    packet = {
                        "symbol": symbol,
                        "price": data_60.iloc[-1]['close'] if data_60 is not None and not data_60.empty else 0,
                        "obi": obi,
                        "book": book, 
                        "sentiment": ai.latest_sentiment_score,
                        "ai_confidence": ai_confidence,
                        "regime": regime,
                        "latency_ms": latency_ms,
                        "risk_status": {
                            "time_ok": time_allowed,
                            "loss_ok": risk_ok and risk.check_daily_loss(daily_profit, risk.max_daily_loss)[0],
                            "profit_day": daily_profit,
                            "atr": current_atr,
                            "ai_score": ai_total_score,
                            "ai_direction": ai_direction,
                            "limits": session_limits
                        },
                        "account": account,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    await websocket.send_json(packet)
                    
                    persistence.save_state("last_obi", obi)
                    persistence.save_state("latency_ms", latency_ms)

            # 6. Limpeza de Ordens Pendentes (Hanging Orders)
            if time_module.time() - last_cleanup_time > 10: 
                last_cleanup_time = time_module.time()
                orders = await asyncio.to_thread(bridge.mt5.orders_get, symbol=symbol)
                if orders:
                    now_ts = time_module.time()
                    for order in orders:
                        if (now_ts - order.time_setup) > 60: # 60 segundos de tolerância
                             # Apenas cancelar Limit/Stop, não ordens a mercado (que não ficam pendentes assim)
                            req = {
                                "action": bridge.mt5.TRADE_ACTION_REMOVE,
                                "order": order.ticket,
                                "symbol": symbol,
                            }
                            await asyncio.to_thread(bridge.mt5.order_send, req)
                            logging.info(f"Cleanup: Cancelando ordem pendente {order.ticket}")

            # Loop control (100ms)
            await asyncio.sleep(0.01)
            
    except WebSocketDisconnect:
        logging.info("WebSocket desconectado.")
    except Exception as e:
        logging.error(f"Erro no loop principal: {e}")
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
