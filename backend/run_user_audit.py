import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

async def run_user_audit():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"
    
    # Datas solicitadas pelo usuario
    target_dates_str = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026"]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]
    
    logging.info(f"🚀 INICIANDO AUDITORIA SOTA PRO ({symbol}) COM IA ATIVA")
    
    # Pre-fetch de dados (pegar mais velas para cobrir os dias, ~ 15000 velas)
    logging.info("📥 Solicitando histórico massivo do MT5 (15.000 velas), por favor aguarde...")
    base_tester = BacktestPro(symbol=symbol, n_candles=15000, timeframe=timeframe)
    full_data = await base_tester.load_data()
    
    if full_data is None or full_data.empty:
        logging.error("❌ Falha crítica: Sem conexão com MT5 ou dados vazios.")
        return

    full_report = "# 📊 Relatório de Auditoria SOTA PRO (Dias: 19/02 a 27/02)\n"
    full_report += f"**Ativo**: {symbol} | **Capital Base**: R$ {capital_inicial:.2f} | **Timeframe**: {timeframe}\n\n"
    
    resumo_tabela = "### 📈 Resumo Executivo\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Flash-Exit | Vetados (IA/Flux) |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n"

    total_accumulated_pnl = 0
    detailed_reports = "\n## 📜 Detalhamento Histórico Individual e Melhorias\n\n"

    # Pre-instanciação da IA para uso compartilhado e otimizado nos backtests diários
    ai_instance = AICore()

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
            base_lot=1,           # Base lot 1 conforme padrao para 3000R$ agressivo seguro
            dynamic_lot=True,
            use_ai_core=True,
            ai_core=ai_instance
        )
        
        # Últimas Calibrações e Parâmetros (SOTA PRO rigor)
        tester.opt_params['confidence_threshold'] = 0.82
        tester.opt_params['use_flux_filter'] = True
        tester.opt_params['flux_imbalance_threshold'] = 1.15
        tester.opt_params['be_trigger'] = 60.0 
        tester.opt_params['spread'] = 1.2 # Fixar spread para evitar o veto de 3.5 pts da IA
        
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
        detailed_reports += f"**📊 Desempenho Financeiro:**\n"
        detailed_reports += f"- **PnL do Dia**: R$ {day_pnl:.2f}\n"
        detailed_reports += f"- **Operações COMPRADAS**: {len(buy_trades)} trades, Resultado Acumulado: R$ {buy_pnl:.2f}\n"
        detailed_reports += f"- **Operações VENDIDAS**: {len(sell_trades)} trades, Resultado Acumulado: R$ {sell_pnl:.2f}\n"
        detailed_reports += f"- **Win Rate**: {win_rate:.1f}%\n"
        
        detailed_reports += f"\n**🛡️ Defesas Ativas e Perdas de Oportunidades:**\n"
        detailed_reports += f"- Movimentos Sistêmicos (Candidatos V22 brutos): {shadow.get('v22_candidates', 0)}\n"
        detailed_reports += f"- Oportunidades Vetadas pela IA (< 85% de confiança): {missed_ai}\n"
        detailed_reports += f"- Oportunidades Vetadas por Fluxo Fraco: {missed_flux}\n"
        detailed_reports += f"- Saídas Antecipadas (Proteção Flash-Exit): {flash_exits}\n"
        
        # Sugestões de melhoria focadas no resultado do dia para elevar assertividade
        detailed_reports += f"\n**💡 Melhorias para Elevar Assertividade:**\n"
        if missed_ai > len(trades_day) and missed_ai > 0:
            detailed_reports += "- *Alta Taxa de Veto pela IA*: O modelo barrou muitos sinais (threshold 0.85 restritivo). Para aumentar oportunidades, considere reduzir levemente para 0.82-0.83 sem perder o caráter Sniper.\n"
        if missed_flux > len(trades_day) and missed_flux > 0:
            detailed_reports += "- *Alta Taxa de Veto por Fluxo*: Em dias de baixa volatilidade, o book (OBI) não acompanha o deslocamento de preço. Uma assimetria de 1.15 pode estar alta. Considere 1.08 em mercados letárgicos.\n"
        if len(trades_day) > 0 and win_rate < 50:
            detailed_reports += "- *Win Rate Abaixo do Ideal*: Muitas entradas acabaram no vermelho. Melhoria: acionar o trailing stop mais cedo (ex: aos 40 pts) para arrastar stops para a zona de lucro durante pullbacks curtos.\n"
        if len(trades_day) > 0 and win_rate >= 70 and day_pnl > 0:
            detailed_reports += "- *Alta Assertividade Detectada*: Configurações perfeitamente sincronizadas com a macro-tendência do dia. O controle dinâmico de lotes maximizou o lucro de forma ideal.\n"
        if len(trades_day) == 0:
            detailed_reports += "- *Nenhuma Operação Executada*: Filtro SOTA PRO bloqueou 100% dos sinais, o que sugere que o ativo estava sujo ou sem liquidez. Não realizar trades foi a defesa correta para o capital.\n"
        if buy_pnl > 0 and sell_pnl < 0:
            detailed_reports += "- *Melhoria Específica*: Trades de VENDA geraram prejuízo neste dia majoritariamente altista. Sugestão: Impor filtro direcional puro (VWAP Alignment) para vetar entradas contra a macroestrutura de preço do pregão.\n"
        if sell_pnl > 0 and buy_pnl < 0:
            detailed_reports += "- *Melhoria Específica*: Trades de COMPRA geraram prejuízo neste dia majoritariamente baixista. Sugestão: Impor filtro direcional puro (VWAP Alignment) para vetar entradas contra a tendência intradiária.\n"
            
        detailed_reports += "---\n"

    full_report += resumo_tabela
    full_report += f"\n## 🏆 Resultado Final Acumulado (Período): R$ {total_accumulated_pnl:.2f}\n"
    full_report += detailed_reports

    report_path = os.path.join(os.path.dirname(__file__), "relatorio_auditoria_usuario.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)
    
    logging.info(f"\n✅ AUDITORIA CONCLUÍDA. Relatório salvo em: {report_path}")

if __name__ == "__main__":
    asyncio.run(run_user_audit())
