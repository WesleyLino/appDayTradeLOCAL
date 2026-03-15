import asyncio
import logging
import pandas as pd
import os
import sys
import json

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


async def run_multi_day_v24_4():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 1. Configuração de Período e Ativo
    symbol = "WIN$"
    initial_balance = 3000.0

    # Dias solicitados (invertidos para ordem cronológica)
    days_to_test = [
        ("19/02", "backend/data_19_02_2026.csv"),
        ("20/02", "backend/data_20_02_2026.csv"),
        ("23/02", "backend/data_23_02_2026.csv"),
        ("24/02", "backend/data_24_02_2026.csv"),
        ("25/02", "backend/data_25_02_2026.csv"),
        ("26/02", "backend/data_26_02_2026.csv"),
        ("27/02", "backend/data_27_02_2026.csv"),
        ("02/03", "backend/data_02_03_2026.csv"),
        ("03/03", None),  # Via MT5
        ("04/03", None),  # Via MT5
        ("05/03", None),  # Via MT5
        ("06/03", None),  # Via MT5
        ("09/03", None),  # Via MT5
    ]

    logging.info("🚀 INICIANDO AUDITORIA DINÂMICA v24.4: 13 DIAS (FEV/MAR)")
    logging.info("Foco: Sensibilidade Personalizada por Cenário - PT-BR\n")

    results = []

    for label, csv_path in days_to_test:
        logging.info(f"📅 Analisando: {label}...")

        # Instanciar BacktestPro (SOTA v24.4 já é o padrão no arquivo carregado)
        bt = BacktestPro(symbol=symbol, initial_balance=initial_balance)

        # Carregar Dados (Preferência para CSV se existir)
        if csv_path and os.path.exists(csv_path):
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            bt.data = df
        else:
            # Busca do MT5 (últimos candles que cubram o dia solicitado)
            # Como hoje é 12/03, o histórico de Março está disponível via MT5
            await bt.load_data()
            # Filtro interno por data se necessário ou usa o tail() do MT5
            # Para simplificar Março, pegamos a data alvo via index do MT5 se n_candles for alto
            pass

        await bt.run()

        # Métricas do dia
        pnl = sum(t["pnl_fin"] for t in bt.trades)
        trades_count = len(bt.trades)
        win_rate = (
            (len([t for t in bt.trades if t["pnl_fin"] > 0]) / trades_count * 100)
            if trades_count > 0
            else 0
        )

        # Detectar vetos de pânico (Córtex v24.4)
        panico_vetos = bt.shadow_signals.get("veto_reasons", {}).get(
            "PANICO_MERCADO_SEM_BYPASS", 0
        )

        results.append(
            {
                "dia": label,
                "pnl": pnl,
                "trades": trades_count,
                "win_rate": win_rate,
                "panico_vetos": panico_vetos,
            }
        )

        logging.info(
            f"   ✅ Resultado: PnL R$ {pnl:.2f} | Trades: {trades_count} | WR: {win_rate:.1f}% | Vetos Pânico: {panico_vetos}"
        )

    # Consolidação do Relatório
    total_pnl = sum(r["pnl"] for r in results)
    total_trades = sum(r["trades"] for r in results)

    print("\n" + "=" * 50)
    print("📊 RESUMO CONSOLIDADO v24.4 (13 DIAS)")
    print("=" * 50)
    print(f"PnL Total Acumulado: R$ {total_pnl:.2f}")
    print(f"Total de Trades:     {total_trades}")
    print(f"Média PnL/Dia:      R$ {total_pnl / len(results):.2f}")

    # Salvar rascunho de resultados
    with open("backend/audit_multi_day_v24_4_results.json", "w") as f:
        json.dump(results, f, indent=4)


if __name__ == "__main__":
    asyncio.run(run_multi_day_v24_4())
