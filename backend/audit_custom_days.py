import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.backtest_pro import BacktestPro

async def run_custom_audit():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"
    
    # Datas solicitadas (fevereiro de 2026)
    target_dates_str = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026"]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]
    
    logging.info(f"🚀 INICIANDO AUDITORIA CUSTOMIZADA SOTA V10.0 MAESTRO III ({symbol})")
    
    # Pre-fetch de dados (pegar mais velas para garantir que cobrimos esses dias, 10-15 dias úteis ~ 10000 velas)
    logging.info("📥 Solicitando histórico massivo do MT5 (15.000 velas), por favor aguarde...")
    base_tester = BacktestPro(symbol=symbol, n_candles=15000, timeframe=timeframe)
    full_data = await base_tester.load_data()
    
    if full_data is None or full_data.empty:
        logging.error("❌ Falha crítica: Sem conexão com MT5 ou dados vazios.")
        return

    full_report = "# 📊 Relatório de Auditoria SOTA PRO: Dias Selecionados\n"
    full_report += f"**Ativo**: {symbol} | **Capital Base**: R$ {capital_inicial:.2f} | **Timeframe**: {timeframe}\n\n"
    
    resumo_tabela = "### 📈 Resumo Executivo\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Flash-Exit | Oport. Perdidas (IA/Flux) |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n"

    total_accumulated_pnl = 0
    detailed_reports = "\n## 📜 Detalhamento Histórico Individual e Melhorias\n\n"

    for target_date in dates_to_test:
        date_str = target_date.strftime('%d/%m/%Y')
        logging.info(f"📅 Processando: {date_str}...")
        
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(1500).copy()
        
        day_mask = sliced_data.index.date == target_date
        if not any(day_mask):
            logging.warning(f"⚠️ Dia {date_str} sem negociação ou sem dados no histórico retornado.")
            resumo_tabela += f"| {date_str} | **Sem Dados** | - | - | - | - | - | - |\n"
            continue
            
        tester = BacktestPro(
            symbol=symbol,
            n_candles=1500,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=2,
            dynamic_lot=True,
            use_ai_core=False
        )
        
        # Calibragem Maestro III
        tester.opt_params['confidence_threshold'] = 0.70 # Default to allow base signal
        tester.opt_params['use_flux_filter'] = True
        tester.opt_params['flux_imbalance_threshold'] = 1.05
        tester.opt_params['be_trigger'] = 60.0 

        
        tester.data = sliced_data
        
        # Simulação
        await tester.run()
        
        trades_day = [t for t in tester.trades if t['entry_time'].date() == target_date]
        buy_trades = [t for t in trades_day if t['side'] == 'buy']
        sell_trades = [t for t in trades_day if t['side'] == 'sell']
        
        buy_pnl = sum(t['pnl_fin'] for t in buy_trades)
        sell_pnl = sum(t['pnl_fin'] for t in sell_trades)
        day_pnl = buy_pnl + sell_pnl
        total_accumulated_pnl += day_pnl
        
        total_wins = len([t for t in trades_day if t['pnl_fin'] > 0])
        win_rate = (total_wins/len(trades_day)*100) if trades_day else 0
        
        shadow = tester.shadow_signals
        flash_exits = len([t for t in trades_day if t['reason'] == 'FLASH_EXIT'])
        
        missed_ai = shadow.get('filtered_by_ai', 0)
        missed_flux = shadow.get('filtered_by_flux', 0)
        
        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades_day)} | {len(buy_trades)} (R$ {buy_pnl:.2f}) | {len(sell_trades)} (R$ {sell_pnl:.2f}) | {win_rate:.1f}% | {flash_exits} | {missed_ai} / {missed_flux} |\n"

        detailed_reports += f"### 📅 Pregão: {date_str}\n"
        detailed_reports += "**Desempenho Financeiro:**\n"
        detailed_reports += f"- **PnL do Dia**: R$ {day_pnl:.2f}\n"
        detailed_reports += f"- **Compras**: {len(buy_trades)} trades, Resultado Acumulado: R$ {buy_pnl:.2f}\n"
        detailed_reports += f"- **Vendas**: {len(sell_trades)} trades, Resultado Acumulado: R$ {sell_pnl:.2f}\n"
        detailed_reports += f"- **Win Rate**: {win_rate:.1f}%\n"
        
        detailed_reports += "\n**Defesas Ativas e Sombras (Oportunidades):**\n"
        detailed_reports += f"- Sinais base matemáticos detectados (Candidatos V22): {shadow.get('v22_candidates', 0)}\n"
        detailed_reports += f"- Falta de Confiança IA (Oportunidades vetadas < 81% conf): {missed_ai}\n"
        detailed_reports += f"- Falta de Pressão de Fluxo (Oportunidades vetadas): {missed_flux}\n"
        detailed_reports += f"- Saídas Antecipadas (Flash-Exit): {flash_exits}\n"
        
        # Sugestões de melhoria focadas no resultado do dia
        detailed_reports += "\n**Insights para Melhorar Assertividade neste cenário:**\n"
        if missed_ai > len(trades_day) and missed_ai > 0:
            detailed_reports += "- *Alta Taxa de Veto pela IA*: O modelo considerou muitos sinais como incertos. Avaliar se o `confidence_threshold` (0.81) está muito rígido ou se o mercado apresentou muito ruído atípico (ex: macro data).\n"
        if missed_flux > len(trades_day) and missed_flux > 0:
            detailed_reports += "- *Alta Taxa de Veto por Fluxo*: Sinais gerados matematicamente sem agressão de volume. Em dias letárgicos, o `flux_imbalance_threshold` (1.05) nos defendeu de falsos rompimentos, mas também evitou entradas.\n"
        if len(trades_day) > 0 and win_rate < 50:
            detailed_reports += "- *Win Rate Baixo*: Operações acionadas resultaram numa proporção maior de perdas. Melhorias possíveis: apertar o `be_trigger` (Breakeven) para proteger no zero-a-zero mais cedo, ou adotar um Trailing Stop mais agressivo para realizar lucro antecipado na reversão.\n"
        if len(trades_day) > 0 and win_rate >= 70 and day_pnl > 0:
            detailed_reports += "- *Excelente Assertividade*: Filtros otimizados e aderentes à dinâmica de hoje. Manter o uso do multiplicador de lote dinâmico para usufruir de dias de alta performance (surfando o Anti-Martingale).\n"
        if len(trades_day) == 0:
            detailed_reports += "- *Dia Sem Operações*: Os rigorosos filtros Maestro defenderam o capital completamente em um dia de baixa qualidade para a estratégia ou lateralização suja. Evitou-se o overtrading.\n"
        if buy_pnl > 0 and sell_pnl < 0:
             detailed_reports += "- *Viés de Alta não Capturado*: Houve lucro na ponta COMPRADA e perdas na ponta VENDIDA. Se o dia foi unidirecional de alta, melhorar a sincronia do regime macro da IA (Trend Mode) para vetos de contratendência prematuros.\n"
        if sell_pnl > 0 and buy_pnl < 0:
             detailed_reports += "- *Viés de Baixa não Capturado*: Houve lucro na ponta VENDIDA e perdas na ponta COMPRADA. Estratégia de correção contra fluxo principal ocasionou stop loss.\n"
            
        detailed_reports += "---\n"

    full_report += resumo_tabela
    full_report += f"\n## 🏆 Resultado Final Acumulado (7 dias): R$ {total_accumulated_pnl:.2f}\n"
    full_report += detailed_reports

    report_path = os.path.join(os.path.dirname(__file__), "audit_custom_results.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)
    
    logging.info(f"\n✅ AUDITORIA CONCLUÍDA: {report_path}")

if __name__ == "__main__":
    asyncio.run(run_custom_audit())
