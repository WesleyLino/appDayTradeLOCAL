import asyncio
import logging
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


async def run_multi_day_audit():
    # Configuração de logging em Português
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    dates_to_test = [
        datetime(2026, 2, 27).date(),
        datetime(2026, 2, 25).date(),
        datetime(2026, 2, 24).date(),
        datetime(2026, 2, 23).date(),
        datetime(2026, 2, 20).date(),
        datetime(2026, 2, 19).date(),
    ]

    symbol = "WIN$"
    capital = 3000.0

    logging.info(f"🚀 INICIANDO AUDITORIA MULTI-DIAS SOTA V10.0 MAESTRO III ({symbol})")

    # Pre-fetch de 12.000 velas para garantir lookback suficiente para todos os dias
    logging.info("📥 Solicitando velas históricas do MT5, por favor aguarde...")
    base_tester = BacktestPro(symbol=symbol, n_candles=12000, timeframe="M1")
    full_data = await base_tester.load_data()

    if full_data is None or full_data.empty:
        logging.error(
            "❌ Falha ao carregar dados históricos do MT5. Verifique a conexão e símbolos."
        )
        return

    full_report = "# 📊 Relatório de Auditoria SOTA V10.0 (Maestro III)\n"
    full_report += f"**Ativo**: {symbol} | **Capital Inicial**: R$ {capital:.2f} | **Timeframe**: M1\n\n"
    full_report += "> **Obrigação**: Idioma Português do Brasil - Auditoria de Potencial de Ganho e Defesa.\n\n"

    total_week_pnl = 0

    for target_date in dates_to_test:
        logging.info("\n---------------------------------------------------------")
        logging.info(f"📅 AUDITORIA PARA O DIA: {target_date.strftime('%d/%m/%Y')}")
        logging.info("---------------------------------------------------------")

        # Filtro de dados para o dia alvo com margem de lookback (1500 velas)
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(1500).copy()

        day_events = sliced_data[sliced_data.index.date == target_date]
        if len(day_events) == 0:
            logging.warning(
                f"⚠️ Sem dados registrados para o dia {target_date.strftime('%d/%m/%Y')}."
            )
            full_report += f"## 📅 Data: {target_date.strftime('%d/%m/%Y')}\n*Sem dados no histórico (Provável Feriado ou Final de Semana).*\n\n"
            continue

        tester = BacktestPro(
            symbol=symbol,
            n_candles=1500,
            timeframe="M1",
            initial_balance=capital,
            base_lot=2,  # SOTA V10.0 usa base 2 para parciais
            dynamic_lot=True,
            use_ai_core=True,
        )

        # Parâmetros de Calibragem SOTA V10.0 (High Rigor)
        tester.opt_params["confidence_threshold"] = 0.81
        tester.opt_params["use_flux_filter"] = True
        tester.opt_params["flux_imbalance_threshold"] = 1.05
        tester.opt_params["be_trigger"] = 60.0

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
        total_week_pnl += day_pnl

        buy_wins = len([t for t in buy_trades if t["pnl_fin"] > 0])
        sell_wins = len([t for t in sell_trades if t["pnl_fin"] > 0])
        total_wins = len([t for t in trades_day if t["pnl_fin"] > 0])

        shadow = tester.shadow_signals

        # Contagem de Defesas Ativas
        flash_exits = len([t for t in trades_day if t["reason"] == "FLASH_EXIT"])
        profit_guards = len([t for t in trades_day if t["reason"] == "PROFIT_GUARD"])

        # Análise de Melhorias
        melhorias = []
        if shadow.get("filtered_by_ai", 0) > 15:
            melhorias.append(
                "- **IA Restritiva**: Muitos sinais barrados por incerteza. Considerar leve ajuste no `confidence_threshold` (ex: 0.80)."
            )
        if shadow.get("filtered_by_flux", 0) > 10:
            melhorias.append(
                "- **Fluxo Exigente**: O filtro de agressividade barrou lucros potenciais. O Micro-Flux ajudou, mas pode-se testar `flux_imbalance_threshold` em 1.02."
            )
        if buy_pnl < -150 and sell_pnl > 150:
            melhorias.append(
                "- **Direcionalidade**: Mercado de forte queda. Bloqueio total de Compras ou redução de lotes em ordens contra-tendência aumentaria a curva."
            )

        if not melhorias:
            melhorias.append(
                "- **Calibragem Ótima**: Defesas e filtros agiram em harmonia para proteger o capital."
            )

        # Gerando MD em Português
        day_report = f"## 📅 Data: {target_date.strftime('%d/%m/%Y')}\n\n"
        day_report += "### 💰 Performance Financeira\n"
        day_report += f"- **PnL Total do Dia**: R$ {day_pnl:.2f}\n"
        day_report += f"- **Taxa de Acerto (Win Rate)**: {(total_wins / len(trades_day) * 100) if trades_day else 0:.1f}%\n"
        day_report += f"- **Total de Trades**: {len(trades_day)}\n\n"

        day_report += "**Desempenho por Direção:**\n"
        day_report += f"- **🟩 OPERAÇÕES COMPRADAS**: {len(buy_trades)} | PnL: R$ {buy_pnl:.2f} | Win Rate: {(buy_wins / len(buy_trades) * 100) if buy_trades else 0:.1f}%\n"
        day_report += f"- **🟥 OPERAÇÕES VENDIDAS**: {len(sell_trades)} | PnL: R$ {sell_pnl:.2f} | Win Rate: {(sell_wins / len(sell_trades) * 100) if sell_trades else 0:.1f}%\n\n"

        day_report += "### 🛡️ Defesas SOTA V10.0 Ativadas\n"
        day_report += (
            f"- **Flash-Exit (Saída Emergência)**: {flash_exits} acionamentos\n"
        )
        day_report += (
            f"- **Profit Guard (Trava de Lucro)**: {profit_guards} acionamentos\n\n"
        )

        day_report += "### 📉 Oportunidades Perdidas (Shadow Monitoring)\n"
        day_report += (
            f"- **Vetos por Incerteza (IA)**: {shadow.get('filtered_by_ai', 0)}\n"
        )
        day_report += f"- **Vetos por Baixa Liquidez (Fluxo)**: {shadow.get('filtered_by_flux', 0)}\n"
        day_report += f"- **Vetos por Sentimento Macro**: {shadow.get('filtered_by_sentiment', 0)}\n\n"

        day_report += "### 🛠️ Melhorias Sugeridas\n"
        day_report += "\n".join(melhorias) + "\n\n"
        day_report += "---\n"

        full_report += day_report
        logging.info(f"✔️ Concluído: {len(trades_day)} trades. PnL: R$ {day_pnl:.2f}")

    full_report += f"\n# 📊 RESUMO DA SEMANA: R$ {total_week_pnl:.2f}\n"

    report_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "audit_multiday_results.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    logging.info(f"\n✅ AUDITORIA CONCLUÍDA. Relatório salvo em: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_multi_day_audit())
