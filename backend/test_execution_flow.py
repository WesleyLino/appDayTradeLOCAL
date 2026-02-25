import asyncio
import sys
import os
from unittest.mock import MagicMock

# Ajustar path
sys.path.append(os.getcwd())

from backend.bot_sniper_win import SniperBotWIN

async def main():
    print("--- INICIANDO TESTE SNIPER BOT (DRY RUN) ---")
    
    # Mock da Bridge para não tocar no MT5 real durante o teste
    mock_bridge = MagicMock()
    mock_bridge.mt5.symbol_info_tick.return_value.ask = 120000
    mock_bridge.mt5.symbol_info_tick.return_value.bid = 119995
    mock_bridge.mt5.ORDER_TYPE_BUY_LIMIT = 2
    mock_bridge.mt5.ORDER_TYPE_SELL_LIMIT = 3
    
    # Instanciar bot forçando Dry Run
    bot = SniperBotWIN(bridge=mock_bridge, dry_run=True)
    bot.symbol = "WIN$"
    
    print(f"1. Símbolo: {bot.symbol}")
    print(f"2. Modo Atual (Risk): {'DRY RUN' if bot.risk.dry_run else 'LIVE'}")
    
    # Testar Execução Buy
    print("3. Testando execute_trade('buy')...")
    res_buy = await bot.execute_trade("buy")
    print(f"   Resultado Buy: {res_buy}")
    
    # Testar Execução Sell
    print("4. Testando execute_trade('sell')...")
    res_sell = await bot.execute_trade("sell")
    print(f"   Resultado Sell: {res_sell}")
    
    print("--- TESTE CONCLUÍDO ---")

if __name__ == "__main__":
    asyncio.run(main())
