import asyncio
import json
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_7day_baseline_test():
    print("📈 Iniciando Audit MT5 de 7 Dias: 1 Contrato / Cap R$ 1000")
    print("🚀 Foco: Verificação de performance recente com a estratégia SOTA.")

    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    # Parâmetros solicitados pelo usuário
    params["start_time"] = "10:00"
    params["end_time"] = "15:00"  # Mantendo a janela Pro expandida
    params["aggressive_mode"] = (
        True  # Para habilitar o rsi_threshold maior e daily_loss de 60%
    )

    # 4000 candles M1 ~= 7 dias operacionais completos
    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=4000,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        dynamic_lot=False,  # FORÇADO A 1 CONTRATO
        **params,
    )

    await backtester.run()

    print("\n=== RESUMO 7 DIAS (1 LOTE) ===")
    print(f"Saldo Final: R$ {backtester.balance:.2f}")
    if len(backtester.trades) > 0:
        profit_total = backtester.balance - 1000.0
        print(f"Lucro Líquido: R$ {profit_total:.2f}")
        print(f"Drawdown Máximo: {backtester.max_drawdown * 100:.2f}%")
        print(f"Total de Trades: {len(backtester.trades)}")

        win_trades = [t for t in backtester.trades if t["pnl_fin"] > 0]
        wr = (len(win_trades) / len(backtester.trades)) * 100
        print(f"Win Rate: {wr:.1f}%")
        print(f"Oportunidades Ignoradas (Prob 70-85%): {backtester.missed_signals}")
    else:
        print("Nenhum trade realizado no período.")

    print("\n=== LISTAGEM DE TRADES (Últimos 10) ===")
    for t in backtester.trades[-10:]:
        print(
            f"Data: {t['exit_time'].date()} | {t['exit_time'].time()} | Side: {t['side']} | Pts: {t['pnl_points']:.1f} | R$: {t['pnl_fin']:.2f} | Motivo: {t['reason']}"
        )

    print("\n✅ Auditoria de 7 Dias Concluída.")


if __name__ == "__main__":
    asyncio.run(run_7day_baseline_test())
