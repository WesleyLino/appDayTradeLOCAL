import asyncio
import logging
from datetime import datetime
import sys
import os
import json

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


async def run_audit():
    # Configuração de logging em Português
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    dates_to_test = [
        datetime(2026, 2, 27).date(),
        datetime(2026, 2, 26).date(),
        datetime(2026, 2, 25).date(),
        datetime(2026, 2, 24).date(),
        datetime(2026, 2, 23).date(),
        datetime(2026, 2, 20).date(),
        datetime(2026, 2, 19).date(),
    ]

    symbol = "WIN$"
    capital = 3000.0

    logging.info(
        f"🚀 INICIANDO AUDITORIA FEVEREIRO 2026 - QUANTUMTRADE SOTA ({symbol})"
    )

    # Carregando Golden Params V22
    params_path = os.path.join(os.path.dirname(__file__), "v22_locked_params.json")
    locked_params = {}
    if os.path.exists(params_path):
        with open(params_path, "r") as f:
            config = json.load(f)
            locked_params = config.get("strategy_params", {})
            logging.info("🛡️ Golden Params V22 carregados para o backtest.")

    # Pre-fetch de 15.000 velas para garantir lookback suficiente
    logging.info("📥 Solicitando velas históricas do MT5...")
    base_tester = BacktestPro(symbol=symbol, n_candles=15000, timeframe="M1")
    full_data = await base_tester.load_data()

    if full_data is None or full_data.empty:
        logging.error("❌ Falha ao carregar dados históricos do MT5.")
        return

    full_report = "# 📊 Relatório de Auditoria Fevereiro 2026 (QuantumTrade SOTA)\n"
    full_report += f"**Ativo**: {symbol} | **Capital Inicial**: R$ {capital:.2f} | **Timeframe**: M1\n\n"
    full_report += "> **Obrigação**: Idioma Português do Brasil - Auditoria de Potencial de Ganho e Defesa.\n\n"

    total_pnl = 0

    for target_date in dates_to_test:
        logging.info(f"\n📅 AUDITORIA: {target_date.strftime('%d/%m/%Y')}")

        # Filtro de dados para o dia alvo com lookback
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(2000).copy()

        day_events = sliced_data[sliced_data.index.date == target_date]
        if len(day_events) == 0:
            logging.warning(
                f"⚠️ Sem dados para o dia {target_date.strftime('%d/%m/%Y')}."
            )
            continue

        tester = BacktestPro(
            symbol=symbol,
            n_candles=2000,
            timeframe="M1",
            initial_balance=capital,
            **locked_params,
        )

        tester.data = sliced_data

        # Executar Simulação
        await tester.run()

        # Estatísticas do Dia
        trades_day = [t for t in tester.trades if t["entry_time"].date() == target_date]

        buy_trades = [t for t in trades_day if t["side"] == "buy"]
        sell_trades = [t for t in trades_day if t["side"] == "sell"]

        buy_pnl = sum(t["pnl_fin"] for t in buy_trades)
        sell_pnl = sum(t["pnl_fin"] for t in sell_trades)
        day_pnl = buy_pnl + sell_pnl
        total_pnl += day_pnl

        buy_wins = len([t for t in buy_trades if t["pnl_fin"] > 0])
        sell_wins = len([t for t in sell_trades if t["pnl_fin"] > 0])
        total_wins = len([t for t in trades_day if t["pnl_fin"] > 0])

        shadow = tester.shadow_signals

        # Gerando MD
        day_report = f"## 📅 Data: {target_date.strftime('%d/%m/%Y')}\n\n"
        day_report += "### 💰 Performance\n"
        day_report += f"- **PnL do Dia**: R$ {day_pnl:.2f}\n"
        day_report += f"- **Win Rate**: {(total_wins / len(trades_day) * 100) if trades_day else 0:.1f}%\n"
        day_report += f"- **Total Trades**: {len(trades_day)}\n\n"

        day_report += "**Por Direção:**\n"
        day_report += f"- **🟩 COMPRADAS**: {len(buy_trades)} | PnL: R$ {buy_pnl:.2f} | Win Rate: {(buy_wins / len(buy_trades) * 100) if buy_trades else 0:.1f}%\n"
        day_report += f"- **🟥 VENDIDAS**: {len(sell_trades)} | PnL: R$ {sell_pnl:.2f} | Win Rate: {(sell_wins / len(sell_trades) * 100) if sell_trades else 0:.1f}%\n\n"

        day_report += "### 📉 Oportunidades & Vetos\n"
        day_report += (
            f"- **Vetos por Incerteza (IA)**: {shadow.get('filtered_by_ai', 0)}\n"
        )
        day_report += (
            f"- **Vetos por Fluxo/Volume**: {shadow.get('filtered_by_flux', 0)}\n"
        )
        day_report += f"- **Vetos por Tendência Diária [H]**: {shadow.get('filtered_by_bias', 0)}\n\n"

        # Análise simples de melhoria
        melhorias = []
        if day_pnl < 0:
            if shadow.get("filtered_by_ai", 0) > 5:
                melhorias.append(
                    "- **IA Conservadora**: Muitos sinais vetados em dia de perda. Considerar recalibração de incerteza."
                )
            if shadow.get("filtered_by_bias", 0) > 3:
                melhorias.append(
                    "- **Veto de Tendência [H]**: Protegeu de entradas contra a tendência, mas pode ter bloqueado correções lucrativas."
                )
        else:
            melhorias.append(
                "- **Calibragem Gold V22**: Mantida estabilidade e proteção de capital."
            )

        day_report += "### 🛠️ Sugestões de Melhoria\n"
        day_report += (
            "\n".join(melhorias)
            if melhorias
            else "- Sem sugestões críticas para este cenário."
        )
        day_report += "\n\n---\n"

        full_report += day_report
        logging.info(f"✔️ Concluído: PnL R$ {day_pnl:.2f}")

    full_report += f"\n# 📊 RESULTADO CONSOLIDADO: R$ {total_pnl:.2f}\n"

    report_path = os.path.join(os.path.dirname(__file__), "audit_feb_2026_results.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    logging.info(f"\n✅ Relatório salvo em: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_audit())
