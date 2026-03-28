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
    capital_inicial = 500.0
    timeframe = "M1"

    target_dates_str = [
        "19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026",
        "02/03/2026", "03/03/2026", "04/03/2026", "05/03/2026", "06/03/2026", "09/03/2026", "10/03/2026",
        "11/03/2026", "12/03/2026", "13/03/2026", "16/03/2026", "19/03/2026", "20/03/2026", "23/03/2026",
        "24/03/2026", "25/03/2026", "26/03/2026"
    ]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]

    logging.info(f"🚀 INICIANDO AUDITORIA POTENCIAL DIÁRIA INDIVIDUALZADA ({symbol}) - Capital R$ {capital_inicial}")

    logging.info("📥 Solicitando histórico massivo do MT5, aguarde...")
    tester_data = BacktestPro(symbol=symbol, n_candles=35000, timeframe=timeframe)
    full_data = await tester_data.load_data()

    if full_data is None or full_data.empty:
        logging.error("❌ Falha crítica: Sem conexão com MT5 ou dados vazios.")
        return

    full_report = f"# 📊 Auditoria de Potencial Individualizada - Capital R$ {capital_inicial:.2f}\n\n"
    resumo_tabela = "### 📈 Resumo Executivo\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Oport. Vetadas (IA/Flux) |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"

    total_accumulated_pnl = 0
    detailed_reports = "\n## 📜 Detalhamento Histórico Individual\n\n"

    for target_date in dates_to_test:
        date_str = target_date.strftime("%d/%m/%Y")
        logging.info(f"📅 Processando: {date_str}...")

        day_mask = full_data.index.date == target_date
        if not any(day_mask):
            logging.warning(f"⚠️ Dia {date_str} sem negociação ou sem dados.")
            resumo_tabela += f"| {date_str} | **Sem Dados** | - | - | - | - | - |\n"
            continue
            
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(1500).copy()

        tester = BacktestPro(
            symbol=symbol,
            n_candles=1500,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=1,  # A lotagem dinamica podera processar multiplicadores acima
            dynamic_lot=True,
            use_ai_core=True,
        )
        tester.data = sliced_data

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
        detailed_reports += f"- **PnL do Dia**: R$ {day_pnl:.2f}\n"
        detailed_reports += f"- **Compras**: {len(buy_trades)} trades | Ganho Líquido: R$ {buy_pnl:.2f} | Vitoriosos: {len([t for t in buy_trades if t['pnl_fin'] > 0])}/{len(buy_trades)}\n"
        detailed_reports += f"- **Vendas**: {len(sell_trades)} trades | Ganho Líquido: R$ {sell_pnl:.2f} | Vitoriosos: {len([t for t in sell_trades if t['pnl_fin'] > 0])}/{len(sell_trades)}\n"
        detailed_reports += f"- **Win Rate**: {win_rate:.1f}%\n"
        
        max_ganho = max([t["pnl_fin"] for t in trades_day]) if trades_day else 0
        max_perda = min([t["pnl_fin"] for t in trades_day]) if trades_day else 0
        detailed_reports += f"- **Prejuízo Máximo / Maior Perda Individual**: R$ {max_perda:.2f}\n"
        detailed_reports += f"- **Potencial Máximo Ganho Individual (Trade Hero)**: R$ {max_ganho:.2f}\n"

        detailed_reports += "\n**Sombra de Oportunidades (Potencial Vetado ou Oculto):**\n"
        detailed_reports += f"- Sinais Base Matemáticos (Setup Identificado): {shadow.get('v22_candidates', 0)}\n"
        detailed_reports += f"- Vetados pela IA (Compra/Venda): {shadow.get('buy_vetos_ai', 0)} / {shadow.get('sell_vetos_ai', 0)}\n"
        detailed_reports += f"- Saídas Antecipadas via Veto de Viés (Macro): {shadow.get('filtered_by_bias', 0)}\n"
        detailed_reports += f"- Vetados por Filtro de Fluxo: {missed_flux}\n"
        
        detailed_reports += "\n**Melhorias para Elevar Assertividade (Pontos Cirúrgicos sem alterar Core):**\n"
        if len(trades_day) > 0 and win_rate < 55:
            detailed_reports += "- Ajustar gatilho de 'Trailing Stop' ativando de forma agressiva nos primeiros sinais de lucro da operação, prevenindo que trades percam todo o ganho latente e protejam os R$ 500 de base.\n"
        if buy_pnl < 0 and sell_pnl > 0:
            detailed_reports += "- Perdas acentuadas nas Operações Compradas. Ações absolutas indicam elevar o nível estrito da confiança (confidence threshold) da IA especificamente para compras neste direcional.\n"
        if sell_pnl < 0 and buy_pnl > 0:
            detailed_reports += "- Perdas acentuadas nas Operações Vendidas. Taticamente elevar o nível de confiança (confidence threshold) da IA especificamente para operações contra as compras fortes.\n"
        if missed_ai > 30:
            detailed_reports += "- Perda de oportunidade extrema pelo IA Core (Super rigidez técnica). Validar afrouxamento isolado do filtro macro nos regimes neutros com alta liquidez.\n"
        if len(trades_day) == 0:
            detailed_reports += "- Defesa perfeita do patrimônio (Overtrading bloqueado) devido ao estresse de mercado identificado como inconclusivo.\n"
            
        detailed_reports += "---\n"

    full_report += resumo_tabela
    full_report += f"\n## 🏆 Resultado Final Acumulado: R$ {total_accumulated_pnl:.2f}\n"
    full_report += detailed_reports

    report_path = os.path.join(os.path.dirname(__file__), "audit_all_individual_days_results.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    logging.info(f"\n✅ AUDITORIA CONCLUÍDA E GRAVADA: {report_path}")

if __name__ == "__main__":
    asyncio.run(run_audit())
