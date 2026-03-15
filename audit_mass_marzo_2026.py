import asyncio
import pandas as pd
import json
import os
from datetime import timedelta
from backend.backtest_pro import BacktestPro


async def run_mass_audit():
    print("======= AUDITORIA DE PERFORMANCE EM MASSA - MARÇO 2026 (V22.1) =======")
    print("OBRIGAÇÃO: Idioma Português do Brasil")

    # Configurações de Auditoria
    initial_capital = 3000.0
    symbol = "WIN$"
    data_file = "data/sota_training/training_WIN$_MASTER.csv"

    # Carregar parâmetros V22.1 (P0)
    params_path = "backend/v22_locked_params.json"
    with open(params_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    strategy_params = config["strategy_params"]
    strategy_params["initial_balance"] = initial_capital

    # Lista de dias solicitados
    dias_auditoria = [
        "2026-02-19",
        "2026-02-20",
        "2026-02-23",
        "2026-02-24",
        "2026-02-25",
        "2026-02-26",
        "2026-02-27",
        "2026-03-02",
        "2026-03-03",
        "2026-03-04",
        "2026-03-05",
        "2026-03-06",
    ]

    print(f"📥 Lendo dados mestre: {data_file}")
    df_master = pd.read_csv(data_file)
    df_master["time"] = pd.to_datetime(df_master["time"])

    results = []

    for dia in dias_auditoria:
        print(f"\n--- Processando Dia: {dia} ---")

        # Filtro com Warm-up (pega 100 velas antes das 09:00 do dia anterior se necessário)
        # Para simplificar no backtest M1, pegamos a partir das 08:00 do próprio dia se houver
        # ou apenas garantimos que a simulação comece a rodar indicadores antes do horário de trade

        t_start_day = pd.to_datetime(f"{dia} 09:00:00")
        t_end_day = pd.to_datetime(f"{dia} 18:00:00")

        # Pegamos dados desde as 07:00 para garantir warm-up de RSI/BB/EMA
        day_df = df_master[
            (df_master["time"] >= (t_start_day - timedelta(hours=2)))
            & (df_master["time"] <= t_end_day)
        ].copy()

        if day_df.empty:
            print(f"⚠️ Aviso: Nenhum dado para o dia {dia}. Pulando...")
            continue

        temp_csv = f"data/sota_training/audit_temp_{dia}.csv"
        day_df.to_csv(temp_csv, index=False)

        # Instanciar BacktestPro
        bt = BacktestPro(symbol=symbol, data_file=temp_csv, **strategy_params)

        await bt.run()

        # Consolidação de Métricas do Dia
        trades = bt.trades
        lucro_bruto = sum([t["pnl_fin"] for t in trades if t["pnl_fin"] > 0])
        prejuizo_bruto = sum([t["pnl_fin"] for t in trades if t["pnl_fin"] < 0])
        lucro_liquido = bt.balance - initial_capital

        buys = [t for t in trades if t["side"].lower() == "buy"]
        sells = [t for t in trades if t["side"].lower() == "sell"]

        win_buys = len([t for t in buys if t["pnl_fin"] > 0])
        win_sells = len([t for t in sells if t["pnl_fin"] > 0])

        # Perdas de oportunidade (Vetos da IA)
        shadow = bt.shadow_signals
        oportunidades_perdidas = shadow.get("total_missed", 0)

        results.append(
            {
                "Data": dia,
                "Trades": len(trades),
                "Compras": f"{len(buys)} ({win_buys}W)",
                "Vendas": f"{len(sells)} ({win_sells}W)",
                "Lucro_liq": lucro_liquido,
                "Prejuizo": prejuizo_bruto,
                "Perdas_Op": oportunidades_perdidas,
                "Saldo": bt.balance,
            }
        )

        # Print parcial para acompanhar
        print(f"✅ Resultado {dia}: R$ {lucro_liquido:.2f} | Trades: {len(trades)}")

        if os.path.exists(temp_csv):
            os.remove(temp_csv)

    # Tabela Final de Resultados
    audit_df = pd.DataFrame(results)
    print("\n\n" + "=" * 80)
    print("RELATÓRIO FINAL DE AUDITORIA (V22.1 - CAPITAL R$ 3000)")
    print("=" * 80)
    print(audit_df.to_string(index=False))

    total_profit = audit_df["Lucro_liq"].sum()
    print("\n" + "=" * 80)
    print(f"LUCRO LÍQUIDO TOTAL: R$ {total_profit:.2f}")
    print(f"SALDO FINAL ESTIMADO: R$ {initial_capital + total_profit:.2f}")
    print("=" * 80)

    # Salvar resultados em JSON para o relatório
    output_json = "audit_results_v22_1.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"💾 Relatório persistido em: {output_json}")


if __name__ == "__main__":
    asyncio.run(run_mass_audit())
