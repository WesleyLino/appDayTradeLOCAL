import sys
import os
import logging

# Adicionar diretório atual ao path
sys.path.append(os.getcwd())

# Mock MetaTrader5 module since we might not have it installed in this environment or want to test the bridge logic specifically
# However, the user environment supposedly has it. If not, this test will fail on import.
# Assuming proper environment:
try:
    from backend.mt5_bridge import MT5Bridge
    import MetaTrader5 as mt5_module
except ImportError:
    print("MT5 module not found, skipping specific bridge test.")
    sys.exit(0)

def test_bridge_access():
    print("--- Testando Acesso ao Módulo MT5 via Bridge ---")
    bridge = MT5Bridge()
    
    # Check if .mt5 attribute exists and matches the module
    if hasattr(bridge, 'mt5'):
        print(f"✅ bridge.mt5 attribute found: {bridge.mt5}")
        if bridge.mt5 == mt5_module:
            print("✅ bridge.mt5 references the correct module.")
        else:
            print("❌ bridge.mt5 does not match imported module!")
            sys.exit(1)
            
        # Check if we can access constants used in main.py
        try:
            buy_type = bridge.mt5.ORDER_TYPE_BUY
            limit_type = bridge.mt5.ORDER_TYPE_BUY_LIMIT
            print(f"✅ Constants accessed: BUY={buy_type}, BUY_LIMIT={limit_type}")
        except AttributeError as e:
            print(f"❌ Failed to access constants: {e}")
            sys.exit(1)
            
    else:
        print("❌ bridge.mt5 attribute NOT found!")
        sys.exit(1)

if __name__ == "__main__":
    test_bridge_access()
