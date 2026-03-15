import asyncio
import os
import sys
import logging

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_stress_backtest():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Datas para teste
    tests = [
        {
            "date": "27/02",
            "file": "data/audit_m1_20260227.csv",
            "name": "Pausa Institucional (27/02)",
        },
    ]

    results = []

    for test in tests:
        print(f"\n{'=' * 60}")
        print(f"INICIANDO TESTE: {test['name']}")
        print(f"{'=' * 60}")

        # Para 12 e 13, se não houver arquivo, o BacktestPro tentará baixar do MT5
        # Mas como estamos em ambiente de backtest, vamos limitar n_candles
        bt = BacktestPro(
            symbol="WIN$", n_candles=3000, data_file=test["file"], use_ai_core=True
        )

        await bt.load_data()
        if bt.data is None:
            print(f"FAILED: Falha ao carregar dados para {test['date']}. Pulando...")
            continue

        # Executar simulação
        # Nota: BacktestPro.run() é o método que executa a simulação completa
        # Vou verificar se o método run existe ou se devo chamar manual
        try:
            # Assumindo que o método run() existe (padrão do BacktestPro)
            summary = await bt.run()
            results.append(
                {
                    "name": test["name"],
                    "pnl": summary.get("net_profit", 0),
                    "trades": summary.get("total_trades", 0),
                    "wr": summary.get("win_rate", 0),
                }
            )
        except Exception as e:
            print(f"FAILED: Erro na execução de {test['name']}: {e}")

    print(f"\n\n{'=' * 60}")
    print("RELATORIO CONSOLIDADO v24.5 - STRESS TEST")
    print(f"{'=' * 60}")
    for res in results:
        print(
            f"{res['name']}: PnL R$ {res['pnl']:.2f} | Trades: {res['trades']} | WR: {res['wr']:.1f}%"
        )


if __name__ == "__main__":
    asyncio.run(run_stress_backtest())
