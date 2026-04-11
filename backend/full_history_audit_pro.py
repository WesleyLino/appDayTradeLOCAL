import asyncio
import logging
from datetime import datetime, date
import sys
import os
import pandas as pd
import json

# Adiciona o caminho do backend para que possamos importar os componentes do bot
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro

async def run_full_history_audit():
    # Configuração de logging personalizada para não poluir o terminal
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    symbol = "WIN$"
    capital_inicial = 500.0
    timeframe = "M1"
    
    # Lista de datas solicitadas pelo usuário (incluindo as de Fevereiro e Março)
    target_dates_str = [
        "19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026",
        "02/03/2026", "03/03/2026", "04/03/2026", "05/03/2026", "06/03/2026", "09/03/2026", "10/03/2026",
        "11/03/2026", "12/03/2026", "13/03/2026", "16/03/2026", "19/03/2026", "20/03/2026", "23/03/2026",
        "24/03/2026", "25/03/2026", "26/03/2026", "30/03/2026"
    ]
    
    dates_to_test = []
    for d in target_dates_str:
        try:
            dates_to_test.append(datetime.strptime(d, "%d/%m/%Y").date())
        except ValueError:
            logging.error(f"Data inválida ignorada: {d}")

    logging.info(f"🚀 INICIANDO AUDITORIA HISTÓRICA COMPLETA ({len(dates_to_test)} dias)...")
    
    # Carrega dados do MT5 — solicitamos volume histórico amplo para cobrir todo o range
    tester_data = BacktestPro(symbol=symbol, n_candles=35000, timeframe=timeframe)
    full_data = await tester_data.load_data()
    
    if full_data is None or full_data.empty:
        logging.error("❌ Falha crítica: Sem conexão com MT5 ou dados vazios.")
        return

    # Nome do arquivo de relatório final
    report_file = "c:/Users/Wesley Lino/Documents/ProjetosApp/appDayTradeLOCAL/backend/full_history_audit_results.md"
    
    report_md = "# 📊 Auditoria Histórica de Alta Performance (Potencial SOTA)\n\n"
    report_md += "**Período:** 19/02/2026 a 30/03/2026\n"
    report_md += f"**Capital Inicial:** R$ {capital_inicial:.2f}\n"
    report_md += f"**Ativo:** {symbol} | **Timeframe:** {timeframe}\n\n"
    
    table_header = "| Data | PnL | Trades | Win Rate | Veto IA | Veto Fluxo | Perda Máx |\n"
    table_header += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"
    
    summary_rows = ""
    detailed_content = "## 📜 Detalhamento Individual por Pregão\n\n"
    
    total_pnl = 0
    total_trades_all = 0
    total_wins_all = 0
    
    # Processa cada dia do loop individualmente
    for target_date in dates_to_test:
        date_str = target_date.strftime("%d/%m/%Y")
        logging.info(f"🔍 Analisando {date_str}...")
        
        # Filtra o dia exato
        day_mask = full_data.index.date == target_date
        if not any(day_mask):
            logging.warning(f"⚠️ {date_str}: Dados não encontrados no histórico carregado.")
            summary_rows += f"| {date_str} | **Sem Dados** | - | - | - | - | - |\n"
            continue
            
        # Pega do histórico um buffer de 2000 candles até o final deste dia para médias/IA funcionarem bem
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(2000).copy()

        tester = BacktestPro(
            symbol=symbol,
            n_candles=2000,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=1,
            dynamic_lot=True,
            use_ai_core=True
        )
        tester.data = sliced_data
        tester.opt_params["audit_mode"] = True  # Ativa contagem de vetos sem alterar lucro
        
        await tester.run()
        
        # Consolida resultados do pregão específico
        day_trades = [t for t in tester.trades if t["entry_time"].date() == target_date]
        day_pnl = sum(t["pnl_fin"] for t in day_trades)
        day_wins = len([t for t in day_trades if t["pnl_fin"] > 0])
        day_count = len(day_trades)
        day_wr = (day_wins / day_count * 100) if day_count > 0 else 0
        
        # Otimização: coletar vetos shadow para entender o potencial bloqueado
        shadow = tester.shadow_signals
        missed_ia = shadow.get("buy_vetos_ai", 0) + shadow.get("sell_vetos_ai", 0)
        missed_flux = shadow.get("filtered_by_flux", 0)
        max_drawdown = min([t["pnl_fin"] for t in day_trades]) if day_trades else 0
        
        total_pnl += day_pnl
        total_trades_all += day_count
        total_wins_all += day_wins
        
        # Preenche a linha da tabela
        summary_rows += f"| {date_str} | **R$ {day_pnl:.2f}** | {day_count} | {day_wr:.1f}% | {missed_ia} | {missed_flux} | R$ {max_drawdown:.2f} |\n"
        
        # Detalhamento textual para inspeção
        detailed_content += f"### 📅 Pregão: {date_str}\n"
        detailed_content += f"- **PnL**: R$ {day_pnl:.2f} | **Win Rate**: {day_wr:.1f}% ({day_wins}/{day_count})\n"
        detailed_content += f"- **Oportunidades Vetadas pela IA**: {missed_ia}\n"
        detailed_content += f"- **Oportunidades Vetadas pelo Fluxo**: {missed_flux}\n"
        detailed_content += f"- **Maior Stop-Loss Único**: R$ {max_drawdown:.2f}\n\n"

    # Consolida estatísticas globais da auditoria
    final_wr = (total_wins_all / total_trades_all * 100) if total_trades_all > 0 else 0
    final_summary = "## 🏆 Performance Consolidada da Amostra\n\n"
    final_summary += f"- **PnL Acumulado Total:** R$ {total_pnl:.2f}\n"
    final_summary += f"- **Total de Trades Realizados:** {total_trades_all}\n"
    final_summary += f"- **Win Rate Médio Absoluto:** {final_wr:.1f}%\n"
    final_summary += f"- **Saldo Final Estimado (Banca 500):** R$ {500 + total_pnl:.2f}\n\n"
    
    # Escreve o arquivo final completo
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md + final_summary + "### 📊 Resumo Executivo (Tabela)\n\n" + table_header + summary_rows + "\n" + detailed_content)
        
    logging.info(f"✅ Auditoria concluída com sucesso. Relatório salvo em: {report_file}")

if __name__ == "__main__":
    asyncio.run(run_full_history_audit())
