import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_aggressive_mt5_1day_test():
    print("📈 INICIANDO TESTE AGRESSIVO (1 DIA) - DADOS REAIS MT5")
    print(
        "🚀 Configuração: 1 Contrato / Cap R$ 1000 / Limite Diário 60% / Sem Limite de Trades"
    )

    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    # 600 candles M1 ~= 1 dia operacional completo
    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        dynamic_lot=False,
        **params,
    )

    await backtester.run()

    print("\n==================================================")
    print("RELATORIO AGRESSIVO 1 DIA (DADOS MT5)")
    print("==================================================")
    print("Saldo Inicial: R$ 1000.00")
    print(f"Saldo Final:   R$ {backtester.balance:.2f}")
    print(f"Lucro Líquido: R$ {backtester.balance - 1000.0:.2f}")
    print(f"Total Trades:  {len(backtester.trades)}")

    wins = [t for t in backtester.trades if t["pnl_fin"] > 0]
    wr = (len(wins) / len(backtester.trades) * 100) if backtester.trades else 0

    print(f"Win Rate:      {wr:.1f}%")
    print(f"Max Drawdown:  {backtester.max_drawdown * 100:.2f}%")
    print("==================================================\n")

    if backtester.trades:
        print("=== LISTAGEM DE TRADES (HOJE) ===")
        for t in backtester.trades:
            print(
                f"Data: {t['exit_time'].date()} | Horário: {t['exit_time'].time()} | Side: {t['side']} | Pts: {t['pnl_points']:.1f} | R$: {t['pnl_fin']:.2f} | Motivo: {t['reason']}"
            )
    else:
        print("Nenhum trade realizado no período (Sniper Mode Ativo).")

    print("\n✅ Teste 1 Dia MT5 Concluído.")


if __name__ == "__main__":
    asyncio.run(run_aggressive_mt5_1day_test())
