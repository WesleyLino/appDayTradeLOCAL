
import MetaTrader5 as mt5
import pandas as pd
from backend.mt5_bridge import MT5Bridge
import json

def test_bluechips():
    bridge = MT5Bridge()
    if bridge.connect():
        print("✅ MT5 Connected")
        data = bridge.get_bluechips_data()
        print("Blue Chips Data:", data)
        bridge.disconnect()
    else:
        print("❌ MT5 Connection Failed")

if __name__ == "__main__":
    test_bluechips()
