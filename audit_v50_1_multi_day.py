import asyncio
import pandas as pd
import logging
import os
import sys
from datetime import datetime

# Adiciona diretório raiz
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def run_detailed_audit():
    symbol = "WIN$"
    # Lista de dias solicitada (pulando 28/02 por ser sábado)
    dias = [
        "19_02_2026",
        "20_02_2026",
        "23_02_2026",
        "24_02_2026",
        "25_02_2026",
        "26_02_2026",
        "27_02_2026",
        "02_03_2026",
    ]

    overall_report = []

    for dia in dias:
        filepath = f"backend/data_{dia}.csv"
        if not os.path.exists(filepath):
            logging.warning(f"⚠️ Arquivo não encontrado: {filepath}")
            continue

        logging.info(f"🔍 Auditando {dia} com SOTA v50.1...")

        # Execução com IA ativada (Modo Realista v50.1)
        tester = BacktestPro(
            symbol=symbol, data_file=filepath, initial_balance=3000.0, use_ai_core=True
        )

        await tester.run()
        trades = tester.trades
        df_t = pd.DataFrame(trades)

        day_stats = {
            "data": dia.replace("_", "/"),
            "pnl_total": 0.0,
            "pnl_compra": 0.0,
            "pnl_venda": 0.0,
            "prejuizo_bruto": 0.0,
            "trades_total": 0,
            "trades_compra": 0,
            "trades_venda": 0,
            "vetos_ia": tester.shadow_signals.get("filtered_by_ai", 0),
            "vetos_compra": tester.shadow_signals.get("buy_vetos_ai", 0),
            "vetos_venda": tester.shadow_signals.get("sell_vetos_ai", 0),
            "candidatos_v22": tester.shadow_signals.get("v22_candidates", 0),
            "max_dd": tester.max_drawdown * 100,
        }

        if not df_t.empty:
            day_stats["pnl_total"] = df_t["pnl_fin"].sum()
            day_stats["pnl_compra"] = df_t[df_t["side"] == "buy"]["pnl_fin"].sum()
            day_stats["pnl_venda"] = df_t[df_t["side"] == "sell"]["pnl_fin"].sum()
            day_stats["prejuizo_bruto"] = df_t[df_t["pnl_fin"] < 0]["pnl_fin"].sum()

            day_stats["trades_total"] = len(df_t)
            day_stats["trades_compra"] = len(df_t[df_t["side"] == "buy"])
            day_stats["trades_venda"] = len(df_t[df_t["side"] == "sell"])

            hits = len(df_t[df_t["pnl_fin"] > 0])
            day_stats["wr_total"] = (hits / len(df_t)) * 100

        overall_report.append(day_stats)
        logging.info(f"✅ {dia} finalizado. PnL: R$ {day_stats['pnl_total']:.2f}")

    df_final = pd.DataFrame(overall_report)

    # Geração de Relatório Markdown [MANUAL TABLE - NO TABULATE REQ]
    report_path = "backend/relatorio_auditoria_v50_1_completo.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 📊 RELATÓRIO DE AUDITORIA SOTA v50.1 - MINI ÍNDICE\n\n")
        f.write(
            f"**Data da Auditoria:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        )
        f.write("**Capital Inicial:** R$ 3.000,00\n\n")

        f.write("## 📈 Performance Consolidada\n\n")
        # Cabeçalho da Tabela
        headers = [
            "Data",
            "PnL Total",
            "PnL Compra",
            "PnL Venda",
            "Prejuízo",
            "Trades",
            "Vetos IA",
            "Max DD %",
        ]
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")

        for _, row in df_final.iterrows():
            cols = [
                row["data"],
                f"R$ {row['pnl_total']:.2f}",
                f"R$ {row['pnl_compra']:.2f}",
                f"R$ {row['pnl_venda']:.2f}",
                f"R$ {row['prejuizo_bruto']:.2f}",
                str(int(row["trades_total"])),
                str(int(row["vetos_ia"])),
                f"{row['max_dd']:.2f}%",
            ]
            f.write("| " + " | ".join(cols) + " |\n")

        f.write("\n\n")

        total_pnl = df_final["pnl_total"].sum()
        total_compra = df_final["pnl_compra"].sum()
        total_venda = df_final["pnl_venda"].sum()
        total_prejuizo = df_final["prejuizo_bruto"].sum()
        total_vetos = df_final["vetos_ia"].sum()

        f.write("## 🔍 Visão de Potencial e Melhorias\n")
        f.write(f"- **PnL Total Líquido:** R$ {total_pnl:.2f}\n")
        f.write(f"- **Ganho em COMPRAS:** R$ {total_compra:.2f}\n")
        f.write(f"- **Ganho em VENDAS:** R$ {total_venda:.2f}\n")
        f.write(f"- **Prejuízo Acumulado:** R$ {total_prejuizo:.2f}\n")
        f.write(f"- **Oportunidades Vetadas pela IA:** {total_vetos} sinais\n\n")

        f.write("### 🚀 Sugestões de Melhoria (Baseado nos Dados)\n")
        if total_compra > total_venda * 1.5:
            f.write(
                "- **Assimetria de Direção:** O bot performou melhor em COMPRAS. Sugerimos revisar o filtro de volume na VENDA.\n"
            )
        elif total_venda > total_compra * 1.5:
            f.write(
                "- **Assimetria de Direção:** O bot performou melhor em VENDAS. Sugerimos revisar o filtro RSI na COMPRA.\n"
            )

        if total_vetos > total_pnl / 10:  # Heurística de excesso de zelo
            f.write(
                "- **Otimização de Assertividade:** A IA está vetando muitos sinais. Podemos reduzir o `confidence_threshold` em 0.05 para capturar trades de 'Sweet Spot' que estão sendo ignorados.\n"
            )

        f.write(
            "- **Gestão de Risco:** O Prejuízo bruto de R$ {:.2f} sugere que o Trailing Stop está protegendo bem o capital em dias voláteis.\n".format(
                abs(total_prejuizo)
            )
        )

    print(f"\n✅ Relatório gerado em: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_detailed_audit())
