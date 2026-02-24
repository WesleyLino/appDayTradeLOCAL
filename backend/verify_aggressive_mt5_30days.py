import asyncio
import json
import os
import sys
from datetime import datetime
import MetaTrader5 as mt5

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_aggressive_mt5_test():
    print("📈 INICIANDO TESTE AGRESSIVO (30 DIAS) - DADOS REAIS MT5")
    print("🚀 Configuração: 1 Contrato / Cap R$ 1000 / Limite Diário 60% / Sem Limite de Trades")
    
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # 12,000 candles M1 ~= 30-35 dias operacionais
    # Forçamos a coleta do MT5 não passando data_file
    backtester = BacktestPro(
        symbol="WIN$", 
        n_candles=12000,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        dynamic_lot=False, # Como pedido: considerar 1 contrato fixo
        **params
    )
    
    await backtester.run()
    
    print("\n==================================================")
    print("RELATORIO AGRESSIVO (DADOS MT5)")
    print("==================================================")
    print("Saldo Inicial: R$ 1000.00")
    print(f"Saldo Final:   R$ {backtester.balance:.2f}")
    print(f"Lucro Líquido: R$ {backtester.balance - 1000.0:.2f}")
    print(f"Total Trades:  {len(backtester.trades)}")
    
    wins = [t for t in backtester.trades if t['pnl_fin'] > 0]
    wr = (len(wins) / len(backtester.trades) * 100) if backtester.trades else 0
    
    print(f"Win Rate:      {wr:.1f}%")
    print(f"Max Drawdown:  {backtester.max_drawdown*100:.2f}%")
    print("==================================================\n")

    print("=== LISTAGEM DE TRADES (30 DIAS) ===")
    for t in backtester.trades:
        print(f"Data: {t['exit_time'].date()} | Side: {t['side']} | Pts: {t['pnl_points']:.1f} | R$: {t['pnl_fin']:.2f} | Motivo: {t['reason']}")
    
    print("\n✅ Teste MT5 Concluído.")

if __name__ == "__main__":
    asyncio.run(run_aggressive_mt5_test())
