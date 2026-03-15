import asyncio
import websockets
import json


async def test_ws():
    uri = "ws://localhost:8000/ws"
    print(f"Tentando conectar em {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Conectado! Aguardando primeiro pacote...")
            for _ in range(3):
                message = await websocket.recv()
                data = json.loads(message)
                print(
                    f"Pacote recebido: Símbolo={data.get('symbol')} | Preço={data.get('price')}"
                )
            print("Teste concluído com sucesso.")
    except Exception as e:
        print(f"Erro na conexão: {e}")


if __name__ == "__main__":
    asyncio.run(test_ws())
