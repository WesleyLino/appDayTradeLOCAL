import asyncio
import json
import os
import sys
import logging
import pandas as pd

# Adiciona o diretório raiz ao path para encontrar o backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_v11_audit():
    # Configuração de Logs - Apenas Erros para manter output limpo
    logging.basicConfig(
        level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # 1. Carregar parâmetros base
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

    # Configurações V11.0 solicitadas: R$ 3000 capital, MT5 M1, WIN
    params["use_ai_core"] = True
    params["dynamic_lot"] = False
    params["use_trailing_stop"] = True
    # Nota: V11.0 usa lotes assimétricos (3/1) definidos no código, mas se force_lots estiver setado ele fixa.
    # Vou remover force_lots para permitir a assimetria Maestro Overdrive.
    params.pop("force_lots", None)

    initial_capital_per_day = 3000.0

    print("\n" + "=" * 95)
    print("🕵️ AUDITORIA SOTA V11.0 (MAESTRO OVERDRIVE): ÚLTIMOS 30 DIAS INDIVIDUAIS")
    print(
        f"Ativo: WIN$ | Capital por Pregão: R$ {initial_capital_per_day:.2f} | Local: MT5 Histórico"
    )
    print("=" * 95 + "\n")

    # 2. Carregar dados em massa (aprox 45 dias para garantir 30 úteis)
    temp_bt = BacktestPro(symbol="WIN$", n_candles=18000, timeframe="M1")
    print("⏳ Coletando dados históricos do MT5 (18000 candles)...")
    full_df = await temp_bt.load_data()

    if full_df is None or full_df.empty:
        print("❌ Erro: Falha ao carregar dados do MT5.")
        return

    # 3. Separar por dias
    full_df["date"] = full_df.index.date
    unique_days = sorted(full_df["date"].unique())
    target_days = unique_days[
        -31:-1
    ]  # Pegamos os 30 dias anteriores ao último (para evitar dados incompletos de hoje)

    results = []

    header = f"{'DATA':<12} | {'PNL BUY':<10} | {'PNL SELL':<10} | {'TOTAL':<10} | {'TRADES':<6} | {'WR':<5} | {'MISSED'}"
    print(header)
    print("-" * 95)

    for day in target_days:
        # Pega o dia atual + padding para indicadores
        day_data = full_df[full_df["date"] == day]
        if day_data.empty:
            continue

        day_start_idx = full_df.index.get_loc(day_data.index[0])
        start_idx_with_padding = max(
            0, day_start_idx - 150
        )  # Mais padding para VWAP e ATR
        end_idx = full_df.index.get_loc(day_data.index[-1]) + 1

        data_chunk = full_df.iloc[start_idx_with_padding:end_idx].copy()

        bt = BacktestPro(
            symbol="WIN$",
            n_candles=len(data_chunk),
            timeframe="M1",
            initial_balance=initial_capital_per_day,
            **params,
        )

        # Injetar dados
        bt.df = data_chunk

        async def mock_load_data():
            return data_chunk

        bt.load_data = mock_load_data

        report = await bt.run()

        if report is None:
            continue

        # Filtra trades do dia
        trades_today = [
            t
            for t in report.get("trades", [])
            if pd.to_datetime(t["entry_time"]).date() == day
        ]

        pnl_buy = sum(t["pnl_fin"] for t in trades_today if t["side"] == "buy")
        pnl_sell = sum(t["pnl_fin"] for t in trades_today if t["side"] == "sell")
        total_pnl = sum(t["pnl_fin"] for t in trades_today)
        day_count = len(trades_today)
        day_wr = (
            (len([t for t in trades_today if t["pnl_fin"] > 0]) / day_count) * 100
            if day_count > 0
            else 0
        )

        # Oportunidades perdidas (Shadow Signals)
        # Nota: Shadow signals são acumulados no objeto bt, pegamos o delta se houver
        missed_data = report.get("shadow_signals", {})
        missed = missed_data.get("total_missed", 0)
        filtered_ai = missed_data.get("filtered_by_ai", 0)
        filtered_flux = missed_data.get("filtered_by_flux", 0)
        filtered_sent = missed_data.get("filtered_by_sentiment", 0)

        results.append(
            {
                "date": day,
                "pnl_buy": pnl_buy,
                "pnl_sell": pnl_sell,
                "total_pnl": total_pnl,
                "trades": day_count,
                "win_rate": day_wr,
                "missed": missed,
                "filtered_ai": filtered_ai,
                "filtered_flux": filtered_flux,
                "filtered_sent": filtered_sent,
            }
        )

        print(
            f"{day.strftime('%d/%m/%Y'):<12} | R$ {pnl_buy:>7.2f} | R$ {pnl_sell:>7.2f} | R$ {total_pnl:>7.2f} | {day_count:>6} | {day_wr:>4.0f}% | {missed:>6}"
        )

    # 4. Resumo Final
    print("-" * 95)
    total_net = sum(r["total_pnl"] for r in results)
    total_buy = sum(r["pnl_buy"] for r in results)
    total_sell = sum(r["pnl_sell"] for r in results)
    total_trades = sum(r["trades"] for r in results)
    avg_day = total_net / len(results) if results else 0
    total_missed = sum(r["missed"] for r in results)

    print(f"ACUMULADO 30 DIAS: R$ {total_net:.2f}")
    print(f"PNL COMPRAS:      R$ {total_buy:.2f}")
    print(f"PNL VENDAS:       R$ {total_sell:.2f}")
    print(f"TOTAL TRADES:     {total_trades}")
    print(f"SINAIS BARRADOS:  {total_missed} (Oportunidades de refino)")
    print("=" * 95 + "\n")

    # Exportar para JSON para o agente ler e gerar o MD
    output_path = "backend/audit_v11_raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        # Converter dates para str
        for r in results:
            r["date"] = str(r["date"])
        json.dump(results, f, indent=4)


if __name__ == "__main__":
    asyncio.run(run_v11_audit())
