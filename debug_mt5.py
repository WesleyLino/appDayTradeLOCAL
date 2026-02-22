import MetaTrader5 as mt5
from dotenv import load_dotenv

load_dotenv()

print("Initializing MT5...")
if not mt5.initialize():
    print(f"FAILED: {mt5.last_error()}")
else:
    print("SUCCESS: Connected to MT5")
    # print(f"Terminal Info: {mt5.terminal_info()}")
    print(f"Account: {mt5.account_info().login if mt5.account_info() else 'No Account'}")
    mt5.shutdown()
