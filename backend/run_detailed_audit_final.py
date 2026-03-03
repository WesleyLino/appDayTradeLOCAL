import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

async def run_detailed_audit():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"
    
    # Ordem Cronológica para o relatório
    target_dates_str = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026"]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]
    
    logging.info(f"🚀 INICIANDO AUDITORIA DE POTENCIAL EXTRAORDINÁRIO ({symbol})")
    
    base_tester = BacktestPro(symbol=symbol, n_candles=25000, timeframe=timeframe)
    full_data = await base_tester.load_data()
    
    if full_data is None or full_data.empty:
        logging.error("❌ Erro ao carregar dados.")
        return

    full_report = "# 📊 Relatório de Auditoria Detalhada: Potencial de Ganho (19/02 - 27/02)\n"
    full_report += "**Configuração**: Modo de Potencial Bruto (Sniper SOTA Desbloqueado)\n"
    full_report += f"**Capital**: R$ {capital_inicial:.2f} | **Foco**: Potencial de Reversão e Tendência\n\n"
    
    resumo_tabela = "### 📈 Resumo das Operações (Sem Veto Macro)\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Viés IA |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"

    total_pnl = 0
    detailed_results = "\n## 📜 Detalhamento por Pregão\n\n"

    ai_instance = AICore()

    for target_date in dates_to_test:
        date_str = target_date.strftime('%d/%m/%Y')
        logging.info(f"📅 Pregão: {date_str}...")
        
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(2500).copy()
        
        if not any(sliced_data.index.date == target_date):
            continue
            
        tester = BacktestPro(
            symbol=symbol,
            n_candles=2500,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=1,
            use_ai_core=True,
            ai_core=ai_instance
        )
        
        # --- MODO POTENCIAL EXTREMO (Desbloqueio de filtros) ---
        ai_instance.buy_threshold = 55.0  # Captura viés leve de alta
        ai_instance.sell_threshold = 45.0 # Captura viés leve de baixa
        ai_instance.macro_bull_lock = False
        ai_instance.macro_bear_lock = False
        ai_instance.h1_trend = 0
        ai_instance.uncertainty_threshold_base = 1.0 # Ignora incerteza para auditoria de potencial
        
        tester.opt_params['confidence_threshold'] = 0.0
        tester.opt_params['use_flux_filter'] = False
        tester.opt_params['start_time'] = "09:05" # Evita o primeiro candle de abertura
        tester.opt_params['end_time'] = "17:45"
        tester.opt_params['cooldown_minutes'] = 2 # Permite mais trades para ver potencial
        
        await tester.run()
        
        trades_day = [t for t in tester.trades if t['entry_time'].date() == target_date]
        buys = [t for t in trades_day if t['side'] == 'buy']
        sells = [t for t in trades_day if t['side'] == 'sell']
        
        buy_pnl = sum(t['pnl_fin'] for t in buys)
        sell_pnl = sum(t['pnl_fin'] for t in sells)
        day_pnl = buy_pnl + sell_pnl
        total_pnl += day_pnl
        
        wins = len([t for t in trades_day if t['pnl_fin'] > 0])
        wr = (wins/len(trades_day)*100) if trades_day else 0
        
        # Determina o viés predominante do dia baseado nos trades
        vies = "BULL" if buy_pnl > sell_pnl else "BEAR"
        if len(trades_day) == 0: vies = "NEUTRO"
        
        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades_day)} | {len(buys)} (R$ {buy_pnl:.2f}) | {len(sells)} (R$ {sell_pnl:.2f}) | {wr:.1f}% | {vies} |\n"
        
        detailed_results += f"### 📅 {date_str} - Potencial Bruto\n"
        if len(trades_day) > 0:
            detailed_results += f"- **Resultado**: R$ {day_pnl:.2f}\n"
            detailed_results += f"- **Performance**: {len(buys)} Compras (R$ {buy_pnl:.2f}) e {len(sells)} Vendas (R$ {sell_pnl:.2f})\n"
            detailed_results += f"- **Win Rate**: {wr:.1f}%\n"
            detailed_results += f"- **Oportunidades**: O sistema identificou maior potencial na ponta {'COMPRADORA' if buy_pnl > sell_pnl else 'VENDEDORA'}.\n"
        else:
            detailed_results += "- **Nota**: Sem trades disparados pelos gatilhos básicos (RSI/Bandas) mesmo com filtros IA relaxados.\n"
        detailed_results += "---\n"

    full_report += resumo_tabela
    full_report += f"\n## 📈 PnL Acumulado Potencial: R$ {total_pnl:.2f}\n"
    full_report += detailed_results

    with open("backend/relatorio_auditoria_usuario.md", "w", encoding="utf-8") as f:
        f.write(full_report)
    
    logging.info(f"✅ Auditoria Finalizada. PnL: R$ {total_pnl:.2f}")

if __name__ == "__main__":
    asyncio.run(run_detailed_audit())
