import pandas as pd
from backend.backtest_pro import BacktestPro
import logging
import json

logging.basicConfig(level=logging.INFO)

import asyncio


def run_sniper_backtest():
    async def main():
        # Carrega dados do dia 10/03
        try:
            data = pd.read_csv(
                "data/audit_m1_20260310.csv", index_col=0, parse_dates=True
            )
        except:
            print("Arquivo de dados 10/03 não encontrado.")
            return

        # Garante que os parâmetros v24.5 Sniper sejam carregados
        with open("backend/v24_locked_params.json", "r") as f:
            params = json.load(f)

        # Inicializa BacktestPro
        bt = BacktestPro(symbol="WIN$", data=data, initial_balance=3000.0, **params)

        # Executa (AWAIT OBRIGATÓRIO)
        results = await bt.run()

        print("\n" + "=" * 50)
        print("RESULTADO SNIPER v24.5 - DIA 10/03/2026")
        print("=" * 50)
        print(f"Saldo Final: R$ {results['final_balance']:.2f}")
        print(f"Total PnL:   R$ {results['total_pnl']:.2f}")
        print(f"Win Rate:    {results['win_rate']:.1f}%")
        print(f"Trades:      {len(results['trades'])}")
        print("=" * 50)

    asyncio.run(main())


if __name__ == "__main__":
    run_sniper_backtest()
