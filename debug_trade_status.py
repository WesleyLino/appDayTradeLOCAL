import MetaTrader5 as mt5
import sys

def check_trade_allowed():
    if not mt5.initialize():
        print(f"FAILED to initialize: {mt5.last_error()}")
        return

    print("✅ Connected to MT5")
    
    # Check terminal stats
    terminal_info = mt5.terminal_info()
    if terminal_info:
        print(f"Algo Trading Enabled: {terminal_info.trade_allowed}")
        print(f"Connected to Server: {terminal_info.connected}")
    
    # Check account stats
    account_info = mt5.account_info()
    if account_info:
        print(f"Account Trade Allowed: {account_info.trade_allowed}")
        print(f"Account Expert Enabled: {account_info.trade_expert}")
        print(f"Balance: {account_info.balance}")
    
    # Check Symbol stats
    symbol = "WIN$"
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        # Tentar buscar o ativo da série atual se WIN$ falhar
        symbol = "WINJ26" # Exemplo, mas o bridge busca automaticamente
        symbol_info = mt5.symbol_info(symbol)
        
    if symbol_info:
        print(f"\n--- Symbol Info: {symbol} ---")
        print(f"Visible: {symbol_info.visible}")
        print(f"Trade Mode: {symbol_info.trade_mode} (0=No, 1=CloseOnly, 2=Full)")
        print(f"Trade Execution: {symbol_info.trade_exemode}")
        
        # Check if trade is allowed for this symbol
        if symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
            print("❌ TRADING IS DISABLED FOR THIS SYMBOL BY SERVER.")
        elif symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_CLOSEONLY:
            print("⚠️ TRADING IS CLOSE-ONLY FOR THIS SYMBOL.")
        else:
            print("✅ TRADING IS FULLY ENABLEED FOR THIS SYMBOL.")
    else:
        print(f"❌ Symbol {symbol} not found in Market Watch.")

    mt5.shutdown()

if __name__ == "__main__":
    check_trade_allowed()
