
import asyncio
import json
import websockets
import time

async def capture_logs():
    uri = "ws://localhost:8000/ws"
    output_file = "backend/ws_capture_test.log"
    print(f"Capturando pacotes de {uri} para {output_file}...")
    
    with open(output_file, "w") as f:
        try:
            async with websockets.connect(uri) as websocket:
                start_time = time.time()
                while time.time() - start_time < 15: # Captura por 15 segundos
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        if "logs" in data:
                            f.write(f"[{time.ctime()}] Logs count: {len(data['logs'])}\n")
                            for log in data["logs"][:2]: # Loga os 2 primeiros (mais recentes)
                                f.write(f"  - {log['time']} | {log['msg']}\n")
                            f.flush()
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        f.write(f"Erro: {e}\n")
                        break
        except Exception as e:
            print(f"Erro na conexão: {e}")

if __name__ == "__main__":
    asyncio.run(capture_logs())
