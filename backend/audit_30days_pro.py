import asyncio
import logging
import sys
import os

# Garantir que o diretório raiz está no path para importar backtest_pro
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


async def run_30day_audit_massiva():
    # Configuração de logging 100% em Português
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"

    logging.info(
        f"🚀 INICIANDO AUDITORIA MASSIVA DE 30 DIAS SOTA V10.0 MAESTRO III ({symbol})"
    )

    # Pre-fetch de 25.000 velas M1 para cobrir ~30 dias úteis (~50 dias corridos)
    logging.info(
        "📥 Solicitando histórico massivo do MT5 (25.000 velas), por favor aguarde..."
    )
    base_tester = BacktestPro(symbol=symbol, n_candles=25000, timeframe=timeframe)
    full_data = await base_tester.load_data()

    if full_data is None or full_data.empty:
        logging.error("❌ Falha crítica: Sem conexão com MT5 ou dados vazios.")
        return

    # Extrair os últimos 30 dias únicos de pregão presentes nos dados
    all_dates = sorted(list(set(full_data.index.date)))
    # Pegar os últimos 30 dias (se houver)
    dates_to_test = all_dates[-30:] if len(all_dates) >= 30 else all_dates

    logging.info(
        f"📊 Identificados {len(dates_to_test)} dias de pregão para auditoria."
    )

    full_report = (
        "# 📊 Relatório Geral de Auditoria: 30 Dias SOTA V10.0 (Maestro III)\n"
    )
    full_report += f"**Ativo**: {symbol} | **Capital Base**: R$ {capital_inicial:.2f} | **Timeframe**: {timeframe}\n\n"
    full_report += "> **Status**: Auditoria Massiva Individualizada por Pregão.\n\n"

    # Tabela de Resumo Executivo
    resumo_tabela = "### 📈 Resumo Executivo (Top 30 Dias)\n\n"
    resumo_tabela += (
        "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Flash-Exit |\n"
    )
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"

    total_accumulated_pnl = 0
    detailed_reports = "\n## 📜 Detalhamento Histórico Individual\n\n"

    for target_date in dates_to_test:
        date_str = target_date.strftime("%d/%m/%Y")
        logging.info(f"📅 Processando: {date_str}...")

        # Slicing de dados: Pega 1500 velas até o final do dia alvo (lookback seguro)
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(1500).copy()

        # Filtro para verificar se há trades no dia específico
        day_mask = sliced_data.index.date == target_date
        if not any(day_mask):
            logging.warning(f"⚠️ Dia {date_str} sem negociação.")
            continue

        # Instanciar Backtester com modo SOTA V10.0
        tester = BacktestPro(
            symbol=symbol,
            n_candles=1500,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=2,  # Maestro III usa parciais
            dynamic_lot=True,
            use_ai_core=True,
        )

        # Calibragem Maestro III (High Rigor)
        tester.opt_params["confidence_threshold"] = 0.81
        tester.opt_params["use_flux_filter"] = True
        tester.opt_params["flux_imbalance_threshold"] = 1.05
        tester.opt_params["be_trigger"] = 60.0

        tester.data = sliced_data

        # Rodar Simulação
        await tester.run()

        # Extrair métricas do dia
        trades_day = [t for t in tester.trades if t["entry_time"].date() == target_date]

        buy_trades = [t for t in trades_day if t["side"] == "buy"]
        sell_trades = [t for t in trades_day if t["side"] == "sell"]

        buy_pnl = sum(t["pnl_fin"] for t in buy_trades)
        sell_pnl = sum(t["pnl_fin"] for t in sell_trades)
        day_pnl = buy_pnl + sell_pnl
        total_accumulated_pnl += day_pnl

        buy_wins = len([t for t in buy_trades if t["pnl_fin"] > 0])
        sell_wins = len([t for t in sell_trades if t["pnl_fin"] > 0])
        total_wins = len([t for t in trades_day if t["pnl_fin"] > 0])
        win_rate = (total_wins / len(trades_day) * 100) if trades_day else 0

        shadow = tester.shadow_signals
        flash_exits = len([t for t in trades_day if t["reason"] == "FLASH_EXIT"])

        # Adicionar à tabela de resumo
        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades_day)} | {len(buy_trades)} | {len(sell_trades)} | {win_rate:.1f}% | {flash_exits} |\n"

        # Detalhamento para o final do relatório
        detailed_reports += f"### 📅 Pregão: {date_str}\n"
        detailed_reports += f"- **PnL do Dia**: R$ {day_pnl:.2f}\n"
        detailed_reports += f"- **Operações por Lado**: 🟩 C: {len(buy_trades)} (R$ {buy_pnl:.2f}) | 🟥 V: {len(sell_trades)} (R$ {sell_pnl:.2f})\n"
        detailed_reports += f"- **Defesas Ativas**: Flash-Exit: {flash_exits} | Sinais Vetados (Fluxo/IA): {shadow.get('filtered_by_flux', 0)} / {shadow.get('filtered_by_ai', 0)}\n"
        detailed_reports += "---\n"

    # Consolidar relatório final
    full_report += resumo_tabela
    full_report += (
        f"\n## 🏆 Resultado Final Acumulado: R$ {total_accumulated_pnl:.2f}\n"
    )
    full_report += detailed_reports

    report_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "audit_30days_results.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    logging.info(f"\n✅ AUDITORIA CONCLUÍDA: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_30day_audit_massiva())
