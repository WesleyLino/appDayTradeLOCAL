import asyncio
import json
import websockets
import time


async def test_dynamic_logs():
    uri = "ws://localhost:8000/ws"
    print(f"Conectando a {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Conectado! Aguardando pacotes de log...")
            # O backend envia pacotes a cada ~50ms no loop principal
            # Vamos monitorar por alguns segundos
            start_time = time.time()
            while time.time() - start_time < 10:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    if "logs" in data and len(data["logs"]) > 0:
                        latest_log = data["logs"][0]
                        print(
                            f"[{latest_log['time']}] {latest_log['msg']} ({latest_log['type']})"
                        )
                    else:
                        print("Pacote recebido, mas sem logs novos.")
                except asyncio.TimeoutError:
                    print("Timeout aguardando mensagem...")
                except Exception as e:
                    print(f"Erro ao receber: {e}")
                    break
    except Exception as e:
        print(
            f"Falha na conexão: {e}. Certifique-se de que o backend está rodando na porta 8000."
        )


if __name__ == "__main__":
    asyncio.run(test_dynamic_logs())
