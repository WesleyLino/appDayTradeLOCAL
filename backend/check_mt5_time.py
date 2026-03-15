
import MetaTrader5 as mt5
from datetime import datetime

if not mt5.initialize():
    print("Erro ao inicializar MT5")
    quit()

terminal_info = mt5.terminal_info()
print(f"Terminal Connected: {terminal_info.connected}")

# Tenta pegar o horário do servidor via tick
tick = mt5.symbol_info_tick("WIN$")
if tick:
    server_time = datetime.fromtimestamp(tick.time)
    local_time = datetime.now()
    print(f"Server Time: {server_time}")
    print(f"Local Time: {local_time}")
    print(f"Difference: {server_time - local_time}")
else:
    print("Não foi possível obter tick para verificar o horário do servidor.")

mt5.shutdown()
