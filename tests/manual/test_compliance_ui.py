
import asyncio
import json
import logging
import random
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Frontend connected to Test Simulator")
    
    try:
        while True:
            # Mock Data mimicking WIN/IND
            ref_price = 120000
            lower_limit = ref_price * 0.90
            upper_limit = ref_price * 1.10
            
            current_price = 120000 + (random.random() - 0.5) * 500
            
            # Simulate approaching limit
            # current_price = upper_limit * 0.99 
            
            packet = {
                "symbol": "WINJ24",
                "price": current_price,
                "obi": 0.5 + (random.random() - 0.5) * 0.2,
                "sentiment": 0.2,
                "ai_confidence": 0.85,
                "regime": 1,
                "latency_ms": 15,
                "risk_status": {
                    "time_ok": True,
                    "loss_ok": True,
                    "profit_day": 150.00,
                    "atr": 150,
                    "ai_score": 88,
                    "limits": {
                        "lower": lower_limit,
                        "upper": upper_limit,
                        "ref": ref_price
                    }
                },
                "account": {
                    "balance": 10000,
                    "equity": 10150
                },
                "timestamp": asyncio.get_event_loop().time()
            }
            
            await websocket.send_json(packet)
            await asyncio.sleep(0.1)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
