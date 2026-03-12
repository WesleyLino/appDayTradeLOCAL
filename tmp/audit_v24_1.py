import asyncio
import logging
import sys
import os

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_audit():
    logging.basicConfig(level=logging.INFO)
    
    # Configura o backtester para usar o arquivo de auditoria do dia 10/03
    # NOTA: O arquivo foi identificado como audit_m1_20260310.csv
    bt = BacktestPro(
        symbol="WIN$",
        data_file="data/audit_m1_20260310.csv",
        n_candles=1000,
        trailing_trigger=70.0,
        trailing_lock=50.0,
        be_trigger=60.0,
        be_lock=5.0
    )
    
    print("Iniciando Auditoria v24.1 (Dados: 10/03)...")
    await bt.load_data()
    try:
        results = await bt.run()
    except Exception:
        import traceback
        traceback.print_exc()
        return
    
    print("\nAuditoria Finalizada.")
    print(f"PnL Total: R$ {results['total_pnl']:.2f}")
    print(f"Win Rate: {results['win_rate']:.1f}%")
    print(f"Profit Factor: {results['profit_factor']:.2f}")

if __name__ == "__main__":
    asyncio.run(run_audit())
