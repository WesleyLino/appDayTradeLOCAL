import pandas as pd
import logging
import json
import os
import asyncio
from backend.backtest_pro import BacktestPro

# Configuração de Silêncio para Otimização
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("Optimizer")
logger.setLevel(logging.INFO)


async def run_optimization():
    # 1. Carregar Dataset Master (3 Meses+)
    data_path = "data/sota_training/training_WIN$_MASTER.csv"
    if not os.path.exists(data_path):
        logger.error(f"❌ Dataset não encontrado: {data_path}")
        return

    logger.info(f"📂 Carregando dataset: {data_path}")
    df = pd.read_csv(data_path)
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)

    # 2. Baseline de Parâmetros (v50.1 Calibrado)
    # R$ 3.000,00 de capital inicial para calibração realista
    initial_balance = 3000.0

    baseline_params = {
        "rsi_period": 9,
        "bb_dev": 2.0,
        "vol_spike_mult": 1.5,
        "trailing_trigger": 70.0,
        "trailing_lock": 50.0,
        "trailing_step": 20.0,
        "sl_dist": 180.0,
        "tp_dist": 450.0,
        "confidence_threshold": 0.82,
        "vwap_dist_threshold": 300.0,
        "base_lot": 1,
    }

    # 3. Grade de Otimização de Piramidação
    pyramid_profits = [30.0, 50.0, 70.0]  # Pontos de lucro para adicionar lote
    pyramid_signals = [0.6, 0.75, 0.9]  # Intensidade do fluxo (OFI Proxy 0.0-1.0)
    pyramid_max_vols = [2, 3, 4]  # Limite de contratos (Conta R$ 3k)

    results = []

    total_runs = len(pyramid_profits) * len(pyramid_signals) * len(pyramid_max_vols)
    current_run = 0

    logger.info(f"🚀 Iniciando Grid Search de Piramidação: {total_runs} combinações.")

    for p_profit in pyramid_profits:
        for p_signal in pyramid_signals:
            for p_max in pyramid_max_vols:
                current_run += 1

                # Setup do Backtest
                test_params = baseline_params.copy()
                test_params.update(
                    {
                        "pyramid_profit_threshold": p_profit,
                        "pyramid_signal_threshold": p_signal,
                        "pyramid_max_volume": p_max,
                        "initial_balance": initial_balance,
                    }
                )

                bt = BacktestPro(symbol="WIN$", data=df, **test_params)

                # Executar Backtest
                try:
                    stats = await bt.run()

                    if not stats:
                        logger.warning(f"Run {current_run} sem trades.")
                        continue

                    res = {
                        "pyramid_profit_threshold": p_profit,
                        "pyramid_signal_threshold": p_signal,
                        "pyramid_max_volume": p_max,
                        "pnl": stats["total_pnl"],
                        "max_dd_pct": stats["max_drawdown"],
                        "win_rate": stats["win_rate"],
                        "profit_factor": stats["profit_factor"],
                    }

                    results.append(res)
                    logger.info(
                        f"[{current_run}/{total_runs}] P:{p_profit} S:{p_signal} V:{p_max} | PnL: R${res['pnl']:.2f} | DD: {res['max_dd_pct']:.2f}%"
                    )

                except Exception as e:
                    logger.error(f"Erro no run {current_run}: {e}")

    # 4. Salvar Resultados e Rankings
    results_sorted = sorted(results, key=lambda x: x["pnl"], reverse=True)

    output_file = "pyramid_opt_results_3months.json"
    with open(output_file, "w") as f:
        json.dump(results_sorted, f, indent=4)

    logger.info(f"✅ Otimização Concluída! Melhores parâmetros salvos em {output_file}")

    # Filtrar os TOP 3 que respeitam o Drawdown de 15% (R$ 450,00)
    safety_threshold = 15.0  # %
    champions = [r for r in results_sorted if r["max_dd_pct"] <= safety_threshold]

    if champions:
        logger.info("🏆 CHAMPIONS (Max DD < 15%):")
        for i, c in enumerate(champions[:3]):
            logger.info(
                f"#{i + 1}: Profits={c['pyramid_profit_threshold']} | Signal={c['pyramid_signal_threshold']} | MaxVol={c['pyramid_max_volume']} | PnL={c['pnl']:.2f} | DD={c['max_dd_pct']:.2f}%"
            )
    else:
        logger.warning(
            "⚠️ Nenhuma configuração respeitou o limite de 15% de Drawdown. Sugerindo revisão de risco."
        )


if __name__ == "__main__":
    asyncio.run(run_optimization())
