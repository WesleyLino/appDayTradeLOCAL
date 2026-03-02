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
    
    target_dates_str = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026"]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]
    
    logging.info(f"🚀 INICIANDO AUDITORIA BRUTA SOTA PRO ({symbol})")
    
    base_tester = BacktestPro(symbol=symbol, n_candles=25000, timeframe=timeframe)
    full_data = await base_tester.load_data()
    
    if full_data is None or full_data.empty:
        logging.error("❌ Erro ao carregar dados.")
        return

    full_report = "# 📊 Relatório de Auditoria Detalhada (Potencial de Ganho)\n"
    full_report += f"**Gerado em**: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
    full_report += f"**Capital**: R$ {capital_inicial:.2f} | **Estratégia**: Sniper SOTA v22+ (Bruto)\n\n"
    
    resumo_tabela = "### 📈 Resumo das Operações\n\n"
    resumo_tabela += "| Data | PnL Total | Trades | Compra | Venda | Win Rate | Vetos (IA/Bias) |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n"

    total_pnl = 0
    detailed_results = ""

    ai_instance = AICore()

    for target_date in dates_to_test:
        date_str = target_date.strftime('%d/%m/%Y')
        logging.info(f"📅 Auditando: {date_str}...")
        
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(2000).copy() # Aumentado para garantir indicadores estáveis
        
        if not any(sliced_data.index.date == target_date):
            resumo_tabela += f"| {date_str} | **Sem Dados** | - | - | - | - | - |\n"
            continue
            
        tester = BacktestPro(
            symbol=symbol,
            n_candles=2000,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=1,
            use_ai_core=True,
            ai_core=ai_instance
        )
        
        # --- CONFIGURAÇÃO BRUTA (Ignorar travas para ver potencial) ---
        ai_instance.buy_threshold = 80.0  # Ligeiramente mais sensível que 85
        ai_instance.sell_threshold = 20.0 # Ligeiramente mais sensível que 15
        ai_instance.macro_bull_lock = False
        ai_instance.macro_bear_lock = False
        ai_instance.h1_trend = 0
        ai_instance.uncertainty_threshold_base = 0.50 # Permite mais risco para auditoria de potencial
        
        # Override de parâmetros operacionais do Tester
        tester.opt_params['confidence_threshold'] = 0.0 # NEUTRALIZA BUG DE ESTABILIDADE DA VENDA
        tester.opt_params['use_flux_filter'] = False
        tester.opt_params['cooldown_minutes'] = 3
        tester.opt_params['start_time'] = "09:00"
        
        tester.data = sliced_data
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
        
        shadow = tester.shadow_signals
        vov = shadow.get('filtered_by_ai', 0)
        vob = shadow.get('filtered_by_bias', 0)
        
        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades_day)} | {len(buys)} (R$ {buy_pnl:.2f}) | {len(sells)} (R$ {sell_pnl:.2f}) | {wr:.1f}% | {vov} / {vob} |\n"
        
        detailed_results += f"### 📅 Pregão: {date_str}\n"
        detailed_results += f"- **PnL**: R$ {day_pnl:.2f} (Compras: R$ {buy_pnl:.2f}, Vendas: R$ {sell_pnl:.2f})\n"
        detailed_results += f"- **Trades**: {len(trades_day)} (Win Rate: {wr:.1f}%)\n"
        detailed_results += f"- **Defesas**: IA Vetou {vov} sinais, Tendência Vetou {vob} sinais.\n"
        
        # Auditoria de Misses
        if len(trades_day) == 0 and vov > 0:
            detailed_results += f"- *Nota*: O dia foi filtrado por incerteza ({vov} sinais barrados). Potencial de alta cautela.\n"
        elif day_pnl < 0:
            detailed_results += "- *Melhoria*: Considerar reduzir SL para 100 pts em dias de alta volatilidade.\n"
        detailed_results += "---\n"

    full_report += resumo_tabela
    full_report += f"\n## 📈 Resultado Final Acumulado: R$ {total_pnl:.2f}\n"
    full_report += detailed_results

    with open("backend/relatorio_auditoria_usuario.md", "w", encoding="utf-8") as f:
        f.write(full_report)
    
    logging.info(f"✅ Auditoria Concluída via SOTA-BRUTO. PnL: R$ {total_pnl:.2f}")

if __name__ == "__main__":
    asyncio.run(run_detailed_audit())
