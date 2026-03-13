import asyncio
import logging
import pandas as pd
import os
import sys
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# Garantir que o diretório raiz está no path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.backtest_pro import BacktestPro

async def run_multi_day_audit():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    symbol = "WIN$"
    capital_inicial = 500.0  # Conforme solicitado pelo usuário nos testes de 11/03
    timeframe = mt5.TIMEFRAME_M1
    
    # Datas solicitadas pelo usuário em ordem cronológica sugerida
    target_dates = [
        "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27",
        "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06", "2026-03-09", "2026-03-10", "2026-03-11"
    ]
    
    if not mt5.initialize():
        logging.error("❌ Erro ao inicializar MetaTrader 5")
        return

    logging.info("🚀 INICIANDO AUDITORIA MASSIVA SOTA v24.2 - 15 DIAS INDIVIDUAIS")
    logging.info("====================================================================")

    results = []
    total_pnl = 0

    for date_str in target_dates:
        logging.info(f"\n📅 PROCESSANDO DIA: {date_str}...")
        
        # Carregar dados do dia (com 200 velas de warmup/lookback)
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # [v24.2] Pegar dados desde o dia anterior para aquecer EMA/ATR
        start_lookback = target_dt - timedelta(days=3) # Garante fim de semana/feriado
        end_dt = target_dt.replace(hour=18, minute=0, second=0)
        
        # [v24.2] Copy rates com margem de segurança para indicadores
        rates = mt5.copy_rates_range(symbol, timeframe, start_lookback, end_dt)
        if rates is None or len(rates) < 100:
            logging.warning(f"⚠️ Sem dados suficientes para {date_str}. Pulando...")
            continue
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        # Instanciar BacktestPro (Rigor SOTA v24.2)
        bt = BacktestPro(symbol=symbol, n_candles=len(df), initial_balance=capital_inicial)
        bt.data = df
        
        # [PT-BR] Calibragem de Auditoria SOTA v24.2
        bt.opt_params['confidence_buy_threshold'] = 58.0
        bt.opt_params['confidence_sell_threshold'] = 42.0
        bt.opt_params['tp_dist'] = 500.0
        bt.opt_params['tp_multiplier'] = 8.0 # Ativação do Target Institucional MAX
        bt.opt_params['sl_multiplier'] = 3.0
        bt.opt_params['vwap_dist_threshold'] = 800.0
        
        await bt.run()
        
        # Métricas do dia
        trades_count = len(bt.trades)
        pnl = bt.balance - bt.initial_balance
        win_rate = (len([t for t in bt.trades if t['pnl_fin'] > 0]) / trades_count * 100) if trades_count > 0 else 0
        
        logging.info(f"✅ FINALIZADO: PnL: R$ {pnl:.2f} | Trades: {trades_count} | Win Rate: {win_rate:.1f}%")
        
        results.append({
            "data": date_str,
            "pnl": pnl,
            "trades": trades_count,
            "win_rate": win_rate
        })
        total_pnl += pnl

    mt5.shutdown()

    # Gerar Relatório Final
    logging.info("\n====================================================================")
    logging.info("🏆 AUDITORIA CONCLUÍDA")
    logging.info(f"Saldo Total Acumulado: R$ {total_pnl:.2f}")
    logging.info("====================================================================")
    
    report_md = "# 🛡️ Relatório de Auditoria Massiva - SOTA v24.2\n\n"
    report_md += "| Data | PnL Liquidado | Trades | Win Rate |\n"
    report_md += "| :--- | :--- | :--- | :--- |\n"
    for r in results:
        report_md += f"| {r['data']} | R$ {r['pnl']:.2f} | {r['trades']} | {r['win_rate']:.1f}% |\n"
    
    report_md += f"\n**🎯 PnL TOTAL ACUMULADO: R$ {total_pnl:.2f}**\n"
    
    with open("backend/audit_multi_day_v24_2_results.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    
    print("\n[OK] Relatório salvo em: backend/audit_multi_day_v24_2_results.md")

if __name__ == "__main__":
    asyncio.run(run_multi_day_audit())
