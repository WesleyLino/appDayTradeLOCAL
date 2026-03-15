import asyncio
import json
import os
import sys
import logging
import pandas as pd

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_daily_breakdown():
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
    initial_capital_per_day = 3000.0
    params["dynamic_lot"] = False
    params["use_trailing_stop"] = True
    params["force_lots"] = 3

    print("\n" + "=" * 85)
    print("🕵️ ANÁLISE DE CONSISTÊNCIA: 30 DIAS INDIVIDUAIS (MT5)")
    print(f"Ativo: WIN$ | Capital Base: R$ {initial_capital_per_day:.2f} | Lotes: 3.0")
    print("=" * 85 + "\n")

    # 2. Carregar dados em massa (aprox 45 dias para garantir 30 úteis)
    # 390 candles/dia * 45 ≈ 17,550
    temp_bt = BacktestPro(symbol="WIN$", n_candles=18000, timeframe="M1")
    print("⏳ Coletando dados históricos do MT5...")
    full_df = await temp_bt.load_data()

    if full_df is None or full_df.empty:
        print("❌ Erro: Falha ao carregar dados do MT5.")
        return

    # 3. Separar por dias
    full_df["date"] = full_df.index.date
    unique_days = sorted(full_df["date"].unique())

    # Pegar os últimos 30 dias de negociação
    target_days = unique_days[-30:]

    results = []

    print(
        f"{'DATA':<12} | {'LUCRO':<10} | {'TRADES':<6} | {'WR':<6} | {'DD':<8} | {'STATUS'}"
    )
    print("-" * 85)

    for i, day in enumerate(target_days):
        # Para cada dia, pegamos o dia atual + 60 candles anteriores para estabilizar indicadores
        day_data = full_df[full_df["date"] == day]

        # Localizar o índice inicial do dia
        day_start_idx = full_df.index.get_loc(day_data.index[0])

        # Adicionar padding (se houver histórico suficiente)
        start_idx_with_padding = max(0, day_start_idx - 100)
        end_idx = full_df.index.get_loc(day_data.index[-1]) + 1

        data_chunk = full_df.iloc[start_idx_with_padding:end_idx].copy()

        # Rodar backtest para este dia específico
        bt = BacktestPro(
            symbol="WIN$",
            n_candles=len(data_chunk),
            timeframe="M1",
            initial_balance=initial_capital_per_day,
            **params,
        )

        # Injetar os dados e forçar o lote
        bt.df = data_chunk
        bt.opt_params["force_lots"] = 3

        # Monkey-patch para usar o DF injetado em vez de baixar do MT5 novamente
        # Usamos uma função que ignora o self e retorna o dataframe que capturamos
        async def mock_load_data_internal():
            return data_chunk

        bt.load_data = mock_load_data_internal

        report = await bt.run()

        if report is None:
            print(
                f"{day.strftime('%d/%m/%Y'):<12} | {'ERRO':>10} | {'-':>6} | {'-':>5} | {'-':>6} | ⚠️ FALHA"
            )
            continue

        # No report, filtramos apenas trades que ocorreram no dia alvo (ignorando padding)
        trades_today = [
            t
            for t in report.get("trades", [])
            if pd.to_datetime(t["entry_time"]).date() == day
        ]
        day_pnl = sum(t["pnl_fin"] for t in trades_today)
        day_count = len(trades_today)
        day_wr = (
            (len([t for t in trades_today if t["pnl_fin"] > 0]) / day_count) * 100
            if day_count > 0
            else 0
        )

        status = (
            "✅ GANHO" if day_pnl > 0 else ("🛑 LOSS" if day_pnl < 0 else "⚪ NEUTRO")
        )

        results.append(
            {
                "date": day,
                "pnl": day_pnl,
                "trades": day_count,
                "win_rate": day_wr,
                "drawdown": report.get("max_drawdown", 0),
            }
        )

        print(
            f"{day.strftime('%d/%m/%Y'):<12} | R$ {day_pnl:>7.2f} | {day_count:>6} | {day_wr:>5.1f}% | {report.get('max_drawdown', 0):>6.2f}% | {status}"
        )

    # 4. Resumo Consolidado
    total_net = sum(r["pnl"] for r in results)
    best_day = max(results, key=lambda x: x["pnl"])
    worst_day = min(results, key=lambda x: x["pnl"])
    avg_day = total_net / 30
    profitable_days = len([r for r in results if r["pnl"] > 0])

    print("-" * 85)
    print("📊 RESUMO 30 DIAS INDIVIDUAIS")
    print(f"LUCRO TOTAL ACUMULADO:...... R$ {total_net:.2f}")
    print(f"MÉDIA POR DIA:.............. R$ {avg_day:.2f}")
    print(
        f"DIAS POSITIVOS:............. {profitable_days} / 30 ({(profitable_days / 30) * 100:.1f}%)"
    )
    print(
        f"MELHOR DIA:................. {best_day['date'].strftime('%d/%m/%Y')} (R$ {best_day['pnl']:.2f})"
    )
    print(
        f"PIOR DIA:................... {worst_day['date'].strftime('%d/%m/%Y')} (R$ {worst_day['pnl']:.2f})"
    )
    print("=" * 85 + "\n")


if __name__ == "__main__":
    asyncio.run(run_daily_breakdown())
