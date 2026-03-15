import asyncio
import websockets
import json
import urllib.request


async def test_logs():
    uri = "ws://localhost:8000/ws"
    print(f"Tentando conectar em {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Conectado ao WebSocket do Backend!")

            # 1. Aguarda estabilização (mensagens iniciais)
            print("Aguardando stream inicial...")
            await asyncio.sleep(2)

            # 2. Dispara a alteração do Filtro de Notícias
            print("\n>>> DISPARANDO: Toggle Filtro de Notícias (enabled=true)")
            req = urllib.request.Request(
                "http://localhost:8000/config/filters/news?enabled=true", method="POST"
            )
            with urllib.request.urlopen(req) as response:
                res_body = response.read().decode()
                print(f"Resposta API: {res_body}")

            # 3. Monitora os próximos 100 frames de log (maior janela)
            print("\n--- Monitorando Logs em Tempo Real (100 frames) ---")
            found = False
            logged_ids = set()
            for i in range(100):
                try:
                    # Pequeno delay para não sobrecarregar
                    await asyncio.sleep(0.05)
                    msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(msg)
                    if "logs" in data and len(data["logs"]) > 0:
                        # Verifica todos os logs no buffer para garantir que não perdemos nada
                        for entry in data.get("logs", []):
                            entry_id = entry.get("id")
                            if entry_id not in logged_ids:
                                print(
                                    f"[{entry.get('time')}] {entry.get('type')} - {entry.get('msg')}"
                                )
                                logged_ids.add(entry_id)
                                if "Filtro de Notícias" in str(entry.get("msg")):
                                    print(
                                        "\n✨ VALIDAÇÃO SUCESSO: Log detectado no WebSocket!"
                                    )
                                    found = True
                except asyncio.TimeoutError:
                    pass

            if not found:
                print("\n❌ AVISO: Log do Filtro não capturado nos frames lidos.")

    except Exception as e:
        print(f"❌ Erro na execução: {e}")


if __name__ == "__main__":
    asyncio.run(test_logs())
