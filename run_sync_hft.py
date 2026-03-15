import asyncio
import websockets
import json
from datetime import datetime, timedelta


async def test_latencia_e_horario():
    uri = "ws://localhost:8000/ws/WIN$N"  # WIN$N ou o símbolo atual
    headers = {"Origin": "http://localhost:3000"}
    try:
        async with websockets.connect(uri, extra_headers=headers) as websocket:
            print("Conectado! Aguardando pacotes...")
            for i in range(10):  # Analisar 10 pacotes
                message = await websocket.recv()
                data = json.loads(message)

                # Cálculo de Latência Interna (Timestamp do servidor vs Agora)
                server_ts = data.get("timestamp", 0)
                agora_ts = (datetime.now() - timedelta(hours=3)).timestamp()
                latencia = (agora_ts - server_ts) * 1000

                # Horário Brasília
                horario_server = datetime.fromtimestamp(server_ts).strftime(
                    "%H:%M:%S.%f"
                )[:-3]

                print(f"Pacote {i + 1}:")
                print(f"  - Preço: {data.get('last_price')}")
                print(f"  - Horário Server (GMT-3): {horario_server}")
                print(f"  - Latência Estimada: {latencia:.2f}ms")

                if "book" in data:
                    print(
                        f"  - Book Levels (Asks): {len(data['book'].get('asks', []))}"
                    )

                await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Erro no teste: {e}")


if __name__ == "__main__":
    asyncio.run(test_latencia_e_horario())
