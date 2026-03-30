import asyncio
import logging
from datetime import datetime
import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro

async def run_audit():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    symbol = "WIN$"
    capital_inicial = 500.0  # As per previous user constraints
    timeframe = "M1"

    target_dates_str = [
        "30/03/2026",
    ]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]

    logging.info(f"🚀 INICIANDO AUDITORIA PARA CALIBRAGEM MÁXIMA E POTENCIAL - SOTA ({symbol}) no dia 30/03")

    # Solicita volume suficiente de dados
    logging.info("📥 Solicitando histórico do MT5, aguarde...")
    tester_data = BacktestPro(symbol=symbol, n_candles=10000, timeframe=timeframe)
    full_data = await tester_data.load_data()

    if full_data is None or full_data.empty:
        logging.error("❌ Falha crítica: Sem conexão com MT5 ou dados vazios.")
        return

    full_report = "# 📊 Relatório de Auditoria de Potencial, Alta Performance e Assertividade (30/03/2026)\n"
    resumo_tabela = "### 📈 Resumo Executivo\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Oport. Vetadas (IA/Flux) |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"

    total_accumulated_pnl = 0
    detailed_reports = "\n## 📜 Detalhamento Histórico Individual e Sombra de Oportunidades\n\n"

    for target_date in dates_to_test:
        date_str = target_date.strftime("%d/%m/%Y")
        logging.info(f"📅 Processando: {date_str}...")

        day_mask = full_data.index.date == target_date
        if not any(day_mask):
            logging.warning(f"⚠️ Dia {date_str} sem negociação ou sem dados no histórico.")
            resumo_tabela += f"| {date_str} | **Sem Dados** | - | - | - | - | - |\n"
            continue
            
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(1500).copy()

        tester = BacktestPro(
            symbol=symbol,
            n_candles=1500,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=1,
            dynamic_lot=True,
            use_ai_core=True,
        )
        tester.data = sliced_data

        # Não alterar pesos base - focar em coletar as estatísticas das shadows ("audit_mode" passivo loggado)
        tester.opt_params["audit_mode"] = True 
        
        await tester.run()

        trades_day = [t for t in tester.trades if t["entry_time"].date() == target_date]
        buy_trades = [t for t in trades_day if t["side"] == "buy"]
        sell_trades = [t for t in trades_day if t["side"] == "sell"]

        buy_pnl = sum(t["pnl_fin"] for t in buy_trades)
        sell_pnl = sum(t["pnl_fin"] for t in sell_trades)
        day_pnl = buy_pnl + sell_pnl
        total_accumulated_pnl += day_pnl

        total_wins = len([t for t in trades_day if t["pnl_fin"] > 0])
        win_rate = (total_wins / len(trades_day) * 100) if trades_day else 0

        shadow = tester.shadow_signals
        missed_ai = shadow.get("buy_vetos_ai", 0) + shadow.get("sell_vetos_ai", 0)
        missed_flux = shadow.get("filtered_by_flux", 0)

        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades_day)} | {len(buy_trades)} (R$ {buy_pnl:.2f}) | {len(sell_trades)} (R$ {sell_pnl:.2f}) | {win_rate:.1f}% | {missed_ai} / {missed_flux} |\n"

        detailed_reports += f"### 📅 Pregão: {date_str}\n"
        detailed_reports += "**Desempenho Financeiro:**\n"
        detailed_reports += f"- **PnL do Dia**: R$ {day_pnl:.2f}\n"
        detailed_reports += f"- **Compras**: {len(buy_trades)} trades | Ganho Líquido: R$ {buy_pnl:.2f} | Vitoriosos: {len([t for t in buy_trades if t['pnl_fin'] > 0])}/{len(buy_trades)}\n"
        detailed_reports += f"- **Vendas**: {len(sell_trades)} trades | Ganho Líquido: R$ {sell_pnl:.2f} | Vitoriosos: {len([t for t in sell_trades if t['pnl_fin'] > 0])}/{len(sell_trades)}\n"
        detailed_reports += f"- **Win Rate Geral**: {win_rate:.1f}%\n"
        
        max_ganho = max([t["pnl_fin"] for t in trades_day]) if trades_day else 0
        max_perda = min([t["pnl_fin"] for t in trades_day]) if trades_day else 0
        detailed_reports += f"- **Prejuízo Máximo / Perda Maior**: R$ {max_perda:.2f}\n"
        detailed_reports += f"- **Potencial Máximo Individual Ganho**: R$ {max_ganho:.2f}\n"

        detailed_reports += "\n**Sombra de Oportunidades (Potencial Oculto):**\n"
        detailed_reports += f"- Sinais Base Matemáticos (Total Setup Identificado): {shadow.get('v22_candidates', 0)}\n"
        detailed_reports += f"- Vetados pela IA (Compra/Venda): {shadow.get('buy_vetos_ai', 0)} / {shadow.get('sell_vetos_ai', 0)}\n"
        detailed_reports += f"- Vetados por Filtro de Fluxo: {missed_flux}\n"
        detailed_reports += f"- Saídas Antecipadas via BreakEven/Veto Macro: {shadow.get('filtered_by_bias', 0)}\n"
        
        detailed_reports += "\n**Melhorias Estruturais sem Alterar Pesos Assertivos (Calibragem Fina):**\n"
        if len(trades_day) > 0 and win_rate < 70:
            detailed_reports += "- Se o W.R está abaixo de 70%, o ponto de melhoria absoluta é refinar o gatilho de *Trailing Stop* ativo (travar gain após R$ 20,00) em vez de ajustar o timing da IA.\n"
        if missed_ai > 15:
            detailed_reports += "- Houve grande bloqueio potencial pela IA. É provável que o AI Core esteve pessimista na consolidação. Avaliar se há falso alerta de bear/bull lock que possa ser mitigado via tolerância H1.\n"
        if missed_flux > 10:
            detailed_reports += "- Sinais excelentes descartados pela letargia do Book. Manter configuração intocada para evitar falsos rompimentos ('Violinos').\n"
        if buy_pnl < 0 or sell_pnl < 0:
            detailed_reports += "- Foi detectado prejuízo direcional na ponta onde PnL < 0. Indicação para ajustar o 'confidence threshold' exclusivamente nesta ponta desfavorável, blindando o lado em contra-tendência forte do dia.\n"
            
        detailed_reports += "---\n"

    full_report += resumo_tabela
    full_report += f"\n## 🏆 Resultado Final Acumulado (Período: 30/03): R$ {total_accumulated_pnl:.2f}\n"
    full_report += detailed_reports

    report_path = os.path.join(os.path.dirname(__file__), "audit_30_mar_results.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    logging.info(f"\n✅ AUDITORIA CONCLUÍDA E GRAVADA: {report_path}")

    # Exibindo o relatorio
    with open(report_path, "r", encoding="utf-8") as f:
        print(f.read())

if __name__ == "__main__":
    asyncio.run(run_audit())
