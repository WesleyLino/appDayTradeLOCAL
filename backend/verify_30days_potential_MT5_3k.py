import asyncio
import json
import os
import sys
import logging

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_30day_potential_analysis():
    # Configuração de Logs
    logging.basicConfig(
        level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "best_params_WIN.json")
        )

    if not os.path.exists(params_path):
        print(f"Erro: Arquivo {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)

    params = config["params"]

    # Configuração R$ 3000
    initial_capital = 3000.0
    params["dynamic_lot"] = False
    params["use_trailing_stop"] = True

    # 12,000 candles M1 ≈ 30 dias úteis de pregão (6.5h/dia * 60min = 390 min/dia)
    # 390 * 30 = 11,700. Usamos 12,000 para margem.
    n_candles = 12000

    print("\n" + "=" * 75)
    print("🕵️ SIMULAÇÃO DE ESTRESSE: 30 DIAS DE POTENCIAL (MT5)")
    print(f"Ativo: WIN$ | Capital: R$ {initial_capital:.2f} | Lotes: 3.0 (Fixo)")
    print(f"Período Estimado: ~30 dias de negociação (~{n_candles} candles M1)")
    print("=" * 75 + "\n")

    # 2. Configurar o Backtester
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=n_candles,
        timeframe="M1",
        initial_balance=initial_capital,
        **params,
    )

    # Forçamos 3 lotes (regra de 1 por k)
    bt.opt_params["force_lots"] = 3

    # 3. Rodar Backtest
    print("⏳ Coletando 12.000 candles do MetaTrader 5...")
    df = await bt.load_data()
    if df is not None:
        start_date = df.index[0].strftime("%d/%m/%Y")
        end_date = df.index[-1].strftime("%d/%m/%Y")
        print(f"📅 Período Real: {start_date} até {end_date}")

        print("⏳ Processando simulação SOTA (Trailing Stop Ativo)...")
        report = await bt.run()

        # 4. Exibir Resultados
        total_pnl = report["total_pnl"]
        pct_return = (total_pnl / initial_capital) * 100

        print("\n" + "=" * 75)
        print("📈 PERFORMANCE FINAL (30 DIAS)")
        print("=" * 75)
        print(f"Saldo Inicial:.............. R$ {initial_capital:.2f}")
        print(f"Saldo Final:................ R$ {bt.balance:.2f}")
        print(f"Lucro Líquido:.............. R$ {total_pnl:.2f} ({pct_return:.1f}%)")
        print(f"Taxa de Acerto:............. {report['win_rate']:.1f}%")
        print(f"Profit Factor:.............. {report['profit_factor']:.2f}")
        print(f"Drawdown Máximo:............ {report['max_drawdown']:.2f}%")
        print(f"Total de Trades:............ {len(report['trades'])}")

        # Média Diária Estimada
        daily_avg = total_pnl / 30
        print(f"Potencial Médio Diário:..... R$ {daily_avg:.2f}")

        # 5. Breakdown de Sinais
        shadow = report.get("shadow_signals", {})
        print("\n" + "=" * 75)
        print("🔍 AUDITORIA DE SINAIS (SHADOW MODE)")
        print("=" * 75)
        print(
            f"Filtro de IA (SOTA):........ {shadow.get('filtered_by_ai', 0)} sinais bloqueados"
        )
        print(
            f"Filtro de Fluxo:............ {shadow.get('filtered_by_flux', 0)} sinais bloqueados"
        )

        # 6. Conclusão de Ouro
        print("\n" + "=" * 75)
        print("🏆 VEREDITO DE POTENCIAL")
        print("=" * 75)
        if total_pnl > 0 and report["max_drawdown"] < 15:
            print("Estratégia ALTAMENTE LUCRATIVA e Estável para R$ 3000.")
            print(
                f"O potencial de {pct_return:.1f}% em 30 dias é excepcional com DD de {report['max_drawdown']:.2f}%."
            )
        else:
            print("Estratégia requer ajustes para o capital de R$ 3000 neste período.")

        print("\n✅ Relatório detalhado disponível nos logs do sistema.")
        print("=" * 75 + "\n")

    else:
        print(
            "❌ Erro: Não foi possível obter dados do MT5. Verifique se o terminal está aberto."
        )


if __name__ == "__main__":
    asyncio.run(run_30day_potential_analysis())
