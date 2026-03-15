import asyncio
import json
import os
import sys
import logging
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_sota_v22_5_2_audit():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Carregar v22_locked_params.json (Golden Params)
    params_path = "backend/v22_locked_params.json"
    with open(params_path, "r") as f:
        config = json.load(f)

    # Extração robusta dos parâmetros
    strategy_params = config.get("strategy_params", {})
    initial_capital = 3000.0
    symbol = "WIN$"
    timeframe = "M1"

    # Dias solicitados
    target_dates_str = ["06/03/2026", "09/03/2026", "10/03/2026"]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]

    logging.info(f"🚀 INICIANDO AUDITORIA SOTA V22.5.2 - DIAS: {target_dates_str}")

    # Carregar dados (usando n_candles suficiente para cobrir os dias recentes)
    bt_loader = BacktestPro(symbol=symbol, n_candles=5000, timeframe=timeframe)
    full_data = await bt_loader.load_data()

    if full_data is None or full_data.empty:
        logging.error("❌ Falha crítica: Sem conexão com MT5 ou dados vazios.")
        return

    full_report = "# 📊 Relatório de Auditoria SOTA V22.5.2: 06/03, 09/03 e 10/03\n"
    full_report += (
        f"**Ativo**: {symbol} | **Capital Inicial**: R$ {initial_capital:.2f}\n\n"
    )

    resumo_tabela = "### 📈 Resumo de Performance\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra (PnL) | Venda (PnL) | Win Rate | Oport. Perdidas (IA/Flux) |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"

    total_pnl = 0
    detailed_info = "\n## 🔍 Análise Detalhada e Shadow Mode\n\n"

    for target_date in dates_to_test:
        date_str = target_date.strftime("%d/%m/%Y")
        logging.info(f"📅 Processando: {date_str}...")

        # Filtra dados do dia específico
        day_data = full_data[full_data.index.date == target_date].copy()
        if day_data.empty:
            logging.warning(f"⚠️ Sem dados para {date_str}")
            resumo_tabela += f"| {date_str} | **Sem Dados** | - | - | - | - | - |\n"
            continue

        tester = BacktestPro(
            symbol=symbol,
            n_candles=len(day_data),
            timeframe=timeframe,
            initial_balance=initial_capital,
            **strategy_params,
        )
        tester.data = day_data

        # Executa simulação
        await tester.run()

        day_trades = tester.trades
        buy_trades = [t for t in day_trades if t["side"] == "buy"]
        sell_trades = [t for t in day_trades if t["side"] == "sell"]

        day_pnl = sum(t["pnl_fin"] for t in day_trades)
        buy_pnl = sum(t["pnl_fin"] for t in buy_trades)
        sell_pnl = sum(t["pnl_fin"] for t in sell_trades)
        total_pnl += day_pnl

        wins = len([t for t in day_trades if t["pnl_fin"] > 0])
        wr = (wins / len(day_trades) * 100) if day_trades else 0

        shadow = tester.shadow_signals
        missed_ai = shadow.get("filtered_by_ai", 0)
        missed_flux = shadow.get("filtered_by_flux", 0)

        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(day_trades)} | {len(buy_trades)} (R$ {buy_pnl:.2f}) | {len(sell_trades)} (R$ {sell_pnl:.2f}) | {wr:.1f}% | {missed_ai} / {missed_flux} |\n"

        detailed_info += f"### 📅 Pregão: {date_str}\n"
        detailed_info += f"- **Resultado**: R$ {day_pnl:.2f} (Compras: R$ {buy_pnl:.2f} | Vendas: R$ {sell_pnl:.2f})\n"
        detailed_info += f"- **Trades Totais**: {len(day_trades)} ({len(buy_trades)}C / {len(sell_trades)}V)\n"
        detailed_info += "- **Shadow Mode (Vetos)**:\n"
        detailed_info += f"  - Filtros de IA (SOTA): {missed_ai} oportunidades vetadas por baixa confiança.\n"
        detailed_info += f"  - Filtros de Fluxo: {missed_flux} oportunidades vetadas por falta de agressão.\n"

        # Insights baseados no dia
        if day_pnl < 0:
            detailed_info += "- **Alerta de Perda**: O dia resultou em prejuízo. Verificar se o drawdown máximo foi respeitado e se houve falha no Trailing Stop.\n"
        if missed_ai > 5:
            detailed_info += f"- **Oportunidades Perdidas**: A IA vetou {missed_ai} entradas. Analisar se o relaxamento da V22.5.2 (RSI 38/62) teria capturado esses movimentos.\n"

        detailed_info += "---\n"

    full_report += resumo_tabela
    full_report += f"\n## 🏆 Resultado Acumulado (3 dias): R$ {total_pnl:.2f}\n"
    full_report += detailed_info

    # Sugestões de melhoria geral
    full_report += "\n## 🚀 Sugestões para Elevar a Assertividade\n"
    full_report += "1. **Calibragem de Fluxo**: Se as oportunidades perdidas por fluxo forem altas em dias de tendência, considerar reduzir o `flux_imbalance_threshold` para 1.02.\n"
    full_report += "2. **Regime Macro**: Ativar o `Trend Bias` para travar operações contra a tendência primária do dia (Baseado no H1).\n"
    full_report += "3. **Ajuste de Lote**: Em dias de alta performance (WR > 70%), aumentar o multiplicador de lote dinâmico para maximizar o ganho exponencial.\n"

    output_path = "backend/audit_sota_v22_5_2_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    logging.info(f"\n✅ AUDITORIA CONCLUÍDA! Resultado em: {output_path}")


if __name__ == "__main__":
    asyncio.run(run_sota_v22_5_2_audit())
