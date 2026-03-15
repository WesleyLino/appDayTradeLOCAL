import asyncio
import websockets
import json
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import time

# Configurações do Teste (Porta 8001 para auditoria)
WS_URI = "ws://localhost:8001/ws"
ORIGIN = "http://localhost:3000"


async def rigorous_sync_test():
    print("--- INICIANDO TESTE DE SINCRONIZAÇÃO RIGOROSA (AUDITORIA PORTA 8001) ---")

    if not mt5.initialize():
        print("Erro ao inicializar MT5 local.")
        return

    print(f"MT5 Inicializado. Tentando conectar no WebSocket: {WS_URI}")

    try:
        # v16.0 usa additional_headers
        async with websockets.connect(
            WS_URI, additional_headers={"Origin": ORIGIN}
        ) as websocket:
            print("Conectado ao WebSocket de Auditoria.")
            print("-" * 100)
            print(
                f"{'SÍMBOLO':<8} | {'HORÁRIO MT5':<15} | {'HORÁRIO APP (BR)':<18} | {'MT5':<8} | {'APP':<8} | {'DELAY'}"
            )
            print("-" * 100)

            for i in range(15):
                try:
                    # Espera pelo pacote do backend
                    # Aumentando timeout para garantir que o ciclo lento não cause falso negativo
                    message = await asyncio.wait_for(websocket.recv(), timeout=35.0)
                    now_ts = time.time()
                    app_data = json.loads(message)

                    symbol = app_data.get("symbol", "N/A")
                    app_price = app_data.get("price")
                    app_ts = app_data.get("timestamp")
                    app_time = (
                        datetime.fromtimestamp(app_ts).strftime("%H:%M:%S.%f")[:-3]
                        if app_ts
                        else "N/A"
                    )

                    # Obter tick real do MT5 para o símbolo que o backend está enviando
                    mt5_tick = mt5.symbol_info_tick(symbol)
                    if mt5_tick:
                        mt5_price = mt5_tick.last
                        mt5_time_raw = datetime.fromtimestamp(
                            mt5_tick.time
                        ) - timedelta(hours=3)
                        mt5_time_str = mt5_time_raw.strftime("%H:%M:%S.%f")[:-3]

                        latency = (now_ts - app_ts) * 1000 if app_ts else 0
                        match = abs(float(app_price) - float(mt5_price)) < 1.0
                        color = "\033[92m" if match else "\033[91m"
                        reset = "\033[0m"

                        print(
                            f"{symbol:<8} | {mt5_time_str:<15} | {app_time:<18} | {mt5_price:<8.1f} | {color}{app_price:<8.1f}{reset} | {latency:.1f}ms"
                        )
                    else:
                        print(
                            f"{symbol:<8} | {'N/A':<15} | {app_time:<18} | {'N/A':<8} | {app_price:<8.1f} | Sincronia de Tick pendente..."
                        )

                except asyncio.TimeoutError:
                    print("[!] Timeout: O backend não enviou dados em 35s.")
                except Exception as e:
                    print(f"Erro no loop: {e}")
                    continue

                await asyncio.sleep(0.1)

    except Exception as e:
        print(f"Erro Fatal no Teste: {e}")
    finally:
        mt5.shutdown()
        print("-" * 100)
        print("Auditoria concluída.")


if __name__ == "__main__":
    asyncio.run(rigorous_sync_test())
