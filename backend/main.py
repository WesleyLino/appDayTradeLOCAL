from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from .mt5_bridge import MT5Bridge
from .risk_manager import RiskManager
from .ai_core import AICore, InferenceEngine
from .persistence import PersistenceManager
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
    
    try:
        while True:
            if bridge.connected:
                start_time = time_module.perf_counter()
                symbol = bridge.get_current_symbol("WIN")
                if symbol:
                    # 1. Obter Dados de Mercado (Janela de 60 para IA)
                    data_60 = bridge.get_market_data(symbol, n_candles=60)
                    book = bridge.get_order_book(symbol)
                    tns = bridge.get_time_and_sales(symbol, n_ticks=100)
                    
                    account_info = bridge.mt5.account_info()
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
                    
                    # Score Final (0-100) e Direção
                    decision = ai.calculate_decision(obi, ai.latest_sentiment_score, ai_confidence)
                    ai_total_score = decision["score"]
                    ai_direction = decision["direction"]
                    
                    # 3. Validações de Risco
                    time_allowed = risk.is_time_allowed()
                    daily_profit = account.get('profit', 0)
                    risk_ok, risk_msg = risk.check_daily_loss(daily_profit, risk.max_daily_loss)
                    
                    # Validação de Condição de Mercado (Estágio 2)
                    regime = ai.detect_regime(data_60['close'].std() if data_60 is not None else 0, obi)
                    market_condition = risk.validate_market_condition(symbol, regime, current_atr, avg_atr)
                    market_ok = market_condition["allowed"]

                    if risk.should_force_close():
                        panic_close_all()
                        logging.warning("Execução compulsória 17:50 acionada.")

                    if risk.allow_autonomous and ai_total_score >= 85 and risk_ok and market_ok and time_allowed:
                        if ai_direction in ["BUY", "SELL"]:
                            side = "buy" if ai_direction == "BUY" else "sell"
                            logging.info(f"AUTÔNOMO: Disparando {side.upper()} via Score {ai_total_score:.1f}")
                            
                            order_type = bridge.mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else bridge.mt5.ORDER_TYPE_SELL_LIMIT
                            current_price = bridge.mt5.symbol_info_tick(symbol).ask if side == "buy" else bridge.mt5.symbol_info_tick(symbol).bid
                            
                            # Validação Compliance Pre-Trade
                            valid_comp, reason_comp = bridge.validate_order_compliance(symbol, current_price)
                            if not valid_comp:
                                 logging.warning(f"AUTÔNOMO BLOQUEADO: Compliance - {reason_comp}")
                            else:
                                params = risk.get_order_params(symbol, order_type, current_price, 1) # Default 1 contrato
                                params["symbol"] = symbol
                                params["comment"] = "AUTO-EXEC SCORE >= 85"
                                
                                result = bridge.mt5.order_send(params)
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

                    # 4. Dados de Compliance (Limites)
                    info = bridge.mt5.symbol_info(symbol)
                    session_limits = {
                        "lower": info.session_price_limit_min if info else 0,
                        "upper": info.session_price_limit_max if info else 0,
                        "ref": info.session_price_ref if info else 0
                    }

                    # 5. Enviar Pacote ao Frontend
                    packet = {
                        "symbol": symbol,
                        "price": data_60.iloc[-1]['close'] if data_60 is not None and not data_60.empty else 0,
                        "obi": obi,
                        "book": book, # Enviando Order Book (L2) para Heatmap
                        "sentiment": ai.latest_sentiment_score,
                        "ai_confidence": ai_confidence,
                        "regime": ai.detect_regime(data_60['close'].std() if data_60 is not None else 0, obi),
                        "latency_ms": latency_ms,
                        "risk_status": {
                            "time_ok": time_allowed,
                            "loss_ok": risk_ok and volatility_ok,
                            "profit_day": daily_profit,
                            "atr": current_atr,
                            "ai_score": ai_total_score,
                            "ai_direction": ai_direction,
                            "limits": session_limits
                        },
                        "account": {
                            "balance": account.get('balance', 0),
                            "equity": account.get('equity', 0)
                        },
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    await websocket.send_json(packet)
                    
                    persistence.save_state("last_obi", obi)
                    persistence.save_state("latency_ms", latency_ms)
            
            await asyncio.sleep(0.1) # Loop de 100ms
    except WebSocketDisconnect:
        logging.info("Frontend desconectado.")
    except Exception as e:
        logging.error(f"Erro no loop WebSocket: {e}")

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
