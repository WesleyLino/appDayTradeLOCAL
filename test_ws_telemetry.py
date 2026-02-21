import asyncio
import websockets
import json
import traceback

async def debug_telemetry():
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Conectado! Aguardando estabilizacao do modelo (pular primeiros 5 pacotes)...")
            count = 0
            while count < 10:
                message = await websocket.recv()
                data = json.loads(message)
                count += 1
                
                if count > 5:
                    print(f"\n--- PACOTE {count} ---")
                    print(f"Confidence: {data.get('ai_confidence')}")
                    print(f"Risk Status: {json.dumps(data.get('risk_status', {}), indent=2)}")
                    print(f"AI Prediction: {json.dumps(data.get('ai_prediction', {}), indent=2)}")
                
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(debug_telemetry())
