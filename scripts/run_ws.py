import asyncio
import websockets
import json


async def test_ws():
    uri = "ws://localhost:8001/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to {uri}")
            # Wait for a message
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(message)
            print(f"Received data: {data.keys()}")

            # Check for heartbeat or market_data
            if "status" in data or "market_data" in data or "ai_decision" in data:
                print("WebSocket test PASSED: Received valid data.")
            else:
                print("WebSocket test WARNING: Received unknown data format.")
    except Exception as e:
        print(f"WebSocket test FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(test_ws())
