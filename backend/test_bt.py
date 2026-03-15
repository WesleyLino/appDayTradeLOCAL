import asyncio
import sys
import os
import io

# Força UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def test():
    print("Iniciando teste minimalista...")
    bt = BacktestPro(symbol="WIN$", n_candles=200)
    success = await bt.load_data()
    if success:
        print(f"Dados carregados: {len(bt.data)} velas.")
        try:
            res = await bt.run()
            if res:
                print(f"Backtest concluído. Trades: {len(res['trades'])}")
            else:
                print("❌ Falha: Backtest retornou None.")
        except Exception as e:
            import traceback

            print(f"Erro no Backtest: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())
