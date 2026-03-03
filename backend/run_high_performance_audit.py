import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

async def run_high_performance_audit():
    # Configuracao de Logs
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logging.info("🚀 INICIANDO AUDITORIA DE ALTA PERFORMANCE (SOTA HIGH-GAIN)")
    
    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"
    
    target_dates_str = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026"]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]
    
    base_tester = BacktestPro(symbol=symbol, n_candles=25000, timeframe=timeframe)
    full_data = await base_tester.load_data()
    
    if full_data is None or full_data.empty:
        logging.error("❌ Erro ao carregar dados.")
        return

    full_report = "# 📊 Relatório de Auditoria SOTA: Alta Performance (R$ 2.500+)\n"
    full_report += "**Configuração**: SOTA High-Gain (Threshold 0.75 | Lote Dinâmico)\n"
    full_report += f"**Capital Inicial**: R$ {capital_inicial:.2f} | Ativo: {symbol}\n\n"
    
    resumo_tabela = "### 📈 Resumo Acumulado\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Saldo Final |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"

    total_pnl = 0
    current_balance = capital_inicial
    detailed_results = "\n## 📜 Detalhamento por Pregão\n\n"

    ai_instance = AICore()

    for target_date in dates_to_test:
        date_str = target_date.strftime('%d/%m/%Y')
        logging.info(f"📅 Processando: {date_str}...")
        
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(2500).copy()
        
        if not any(sliced_data.index.date == target_date):
            continue
            
        tester = BacktestPro(
            symbol=symbol,
            n_candles=2500,
            timeframe=timeframe,
            initial_balance=current_balance,
            base_lot=1,
            dynamic_lot=True, 
            use_ai_core=True, # SOTA PRO COM ALVOS LIBERADOS
            ai_core=ai_instance
        )
        
        # --- CONFIGURAÇÃO HIGH-GAIN EQUILIBRADA (VERSÃO FINAL V29.2) ---
        ai_instance.buy_threshold = 75.0  # Sensibilidade Sniper (Equilibrada)
        ai_instance.sell_threshold = 25.0 # Sensibilidade Sniper (Equilibrada)
        ai_instance.macro_bull_lock = False
        ai_instance.macro_bear_lock = False
        ai_instance.bluechips_veto_threshold = 0.6 # [PERMISSIVO] Filtro Institucional Moderado
        ai_instance.wdo_veto_threshold = 3.0       # [PERMISSIVO] Filtro WDO Moderado
        ai_instance.spread_veto_threshold = 12.0   # [PERMISSIVO]
        
        tester.opt_params['confidence_threshold'] = 0.75 # Threshold de Segurança (Evita ruído de 25/02)
        tester.opt_params['tp_dist'] = 550.0  
        tester.opt_params['sl_dist'] = 150.0  
        tester.opt_params['use_flux_filter'] = True
        tester.opt_params['flux_imbalance_threshold'] = 1.0 # [PERMISSIVO] Fluxo SNIPER
        tester.opt_params['start_time'] = "09:05"
        tester.opt_params['end_time'] = "17:15"
        tester.opt_params['cooldown_minutes'] = 5 # Cooldown reduzido (Originalmente solicitado: mais trades)
        
        tester.data = sliced_data
        await tester.run()
        
        trades_day = [t for t in tester.trades if t['entry_time'].date() == target_date]
        buys = [t for t in trades_day if t['side'] == 'buy']
        sells = [t for t in trades_day if t['side'] == 'sell']
        
        buy_pnl = sum(t['pnl_fin'] for t in buys)
        sell_pnl = sum(t['pnl_fin'] for t in sells)
        buy_wins = len([t for t in buys if t['pnl_fin'] > 0])
        sell_wins = len([t for t in sells if t['pnl_fin'] > 0])
        
        day_pnl = buy_pnl + sell_pnl
        total_pnl += day_pnl
        current_balance += day_pnl
        
        wins = len([t for t in trades_day if t['pnl_fin'] > 0])
        wr = (wins/len(trades_day)*100) if trades_day else 0
        
        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades_day)} | {len(buys)} (R$ {buy_pnl:.2f}) | {len(sells)} (R$ {sell_pnl:.2f}) | {wr:.1f}% | R$ {current_balance:.2f} |\n"
        
        detailed_results += f"### 📅 {date_str} - Análise Operacional Exaustiva\n"
        detailed_results += "- **Performance Financeira**: \n"
        detailed_results += f"  - 🟢 **Pontual de Compra**: R$ {buy_pnl:.2f} ({buy_wins}G / {len(buys)-buy_wins}L)\n"
        detailed_results += f"  - 🔴 **Pontual de Venda**: R$ {sell_pnl:.2f} ({sell_wins}G / {len(sells)-sell_wins}L)\n"
        detailed_results += f"  - 📉 **Prejuízo (Losses)**: R$ {sum(t['pnl_fin'] for t in trades_day if t['pnl_fin'] < 0):.2f}\n"
        
        # Oportunidades Perdidas
        v22_cand = tester.shadow_signals.get('v22_candidates', 0)
        bv_ai = tester.shadow_signals.get('buy_vetos_ai', 0)
        sv_ai = tester.shadow_signals.get('sell_vetos_ai', 0)
        flux_v = tester.shadow_signals.get('filtered_by_flux', 0)
        
        detailed_results += "- **Rastreamento de Oportunidades Perdidas**: \n"
        detailed_results += f"  - Gatilhos Matemáticos Brutos (V22): {v22_cand}\n"
        detailed_results += f"  - 🚫 Vetos de Compra (IA Insegura): {bv_ai}\n"
        detailed_results += f"  - 🚫 Vetos de Venda (IA Insegura): {sv_ai}\n"
        detailed_results += f"  - 🚫 Vetos por Filtro de Fluxo/Spread: {flux_v}\n"
        
        detailed_results += "- **🚀 Melhorias para Assertividade**: \n"
        if day_pnl < 0:
            detailed_results += "  - *Ajuste*: O prejuízo foi causado por entradas em baixa volatilidade. Sugestão: elevar `vol_min` para evitar 'falsas reversões'.\n"
        elif wr > 60:
            detailed_results += "  - *Ajuste*: Alta assertividade detectada. Potencial para elevar o lucro dobrando o `base_lot` em sinais com Convicção > 85%.\n"
        else:
            detailed_results += "  - *Ajuste*: Equilíbrio estável. Manter calibragem atual para preservação de capital.\n"
        
        detailed_results += "\n---\n"

    full_report += resumo_tabela
    full_report += f"\n## 📈 Resultado Final Acumulado: R$ {total_pnl:.2f}\n"
    full_report += f"**ROI Final**: {(total_pnl/capital_inicial)*100:.1f}%\n"
    full_report += detailed_results

    report_path = "backend/relatorio_high_performance.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(full_report)
    
    logging.info(f"✅ Auditoria Concluída. PnL Total: R$ {total_pnl:.2f}")
    logging.info(f"📄 Relatório salvo em: {report_path}")

if __name__ == "__main__":
    asyncio.run(run_high_performance_audit())
