import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")


async def test_websocket_ofi():
    uri = "ws://localhost:8000/ws"
    logging.info(f"Conectando ao WebSocket do SOTA em {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            logging.info("Conectado! Aguardando quadros de telemetria...")

            # Vamos ler as próximas 5 atualizações
            for i in range(5):
                message = await websocket.recv()
                data = json.loads(message)

                # O payload do backend main.py aparentemente envia direto o objeto
                if "risk_status" in data:
                    weighted_ofi = data["risk_status"].get("weighted_ofi")
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    logging.info(
                        f"[{timestamp}] Métrica OFI Ponderado recebida via WS: {weighted_ofi}"
                    )
                else:
                    logging.warning(
                        f"risk_status ausente. Chaves recebidas: {list(data.keys())}"
                    )

    except Exception as e:
        logging.error(f"Erro no WebSocket: {e}")


if __name__ == "__main__":
    asyncio.run(test_websocket_ofi())
