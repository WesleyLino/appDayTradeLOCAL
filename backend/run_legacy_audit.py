import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.backtest_pro import BacktestPro

async def run_detailed_audit():
    logging.basicConfig(level=logging.ERROR)
    
    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"
    
    target_dates_str = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026"]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]
    
    logging.info("🚀 INICIANDO AUDITORIA SNIPER CLASSIC (LEGADO)")
    
    base_tester = BacktestPro(symbol=symbol, n_candles=25000, timeframe=timeframe)
    full_data = await base_tester.load_data()
    
    if full_data is None or full_data.empty: return

    resumo_tabela = "### 📈 Potencial de Reversão Técnica (Sniper Classic)\n"
    resumo_tabela += "| Data | PnL | Trades | Win Rate | Nota |\n"
    resumo_tabela += "| :--- | :--- | :---: | :---: | :--- |\n"

    total_pnl = 0

    for target_date in dates_to_test:
        date_str = target_date.strftime('%d/%m/%Y')
        mask_until = full_data.index.date <= target_date
        sliced_data = full_data[mask_until].tail(2500).copy()
        
        if not any(sliced_data.index.date == target_date): continue
            
        tester = BacktestPro(
            symbol=symbol,
            n_candles=2500,
            timeframe=timeframe,
            initial_balance=capital_inicial,
            base_lot=1,
            use_ai_core=False # MODO LEGADO
        )
        
        # Parâmetros Legados Relaxados para ver Potencial
        tester.opt_params['rsi_buy_thresh'] = 40
        tester.opt_params['rsi_sell_thresh'] = 60
        tester.opt_params['confidence_threshold'] = 0.0
        tester.opt_params['start_time'] = "09:05"
        tester.opt_params['end_time'] = "17:45"
        
        tester.data = sliced_data
        await tester.run()
        
        trades_day = [t for t in tester.trades if t['entry_time'].date() == target_date]
        day_pnl = sum(t['pnl_fin'] for t in trades_day)
        total_pnl += day_pnl
        wins = len([t for t in trades_day if t['pnl_fin'] > 0])
        wr = (wins/len(trades_day)*100) if trades_day else 0
        
        resumo_tabela += f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades_day)} | {wr:.1f}% | {'Positivo' if day_pnl > 0 else 'Defensivo'} |\n"

    with open("backend/relatorio_potencial_tecnico.md", "w", encoding="utf-8") as f:
        f.write(f"# Auditoria de Potencial Técnico (Legado)\n{resumo_tabela}\n\n**Total Acumulado**: R$ {total_pnl:.2f}")
    
    print(f"✅ Auditoria Técnica Concluída. PnL: R$ {total_pnl:.2f}")

if __name__ == "__main__":
    asyncio.run(run_detailed_audit())
