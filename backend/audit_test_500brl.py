import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
import pytz
import sys
import os
import MetaTrader5 as mt5

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro

async def run_individual_day_audit():
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("\n" + "="*80)
    print(" INICIANDO AUDITORIA BACKTEST: Mini Índice (WIN$) | M1 | Capital: R$ 500,00")
    print("="*80)

    dates_to_test = [
        datetime(2026, 2, 19), datetime(2026, 2, 20), datetime(2026, 2, 23),
        datetime(2026, 2, 24), datetime(2026, 2, 25), datetime(2026, 2, 26),
        datetime(2026, 2, 27), datetime(2026, 3, 2),  datetime(2026, 3, 3),
        datetime(2026, 3, 4),  datetime(2026, 3, 5),  datetime(2026, 3, 6),
        datetime(2026, 3, 9),  datetime(2026, 3, 10), datetime(2026, 3, 11),
        datetime(2026, 3, 12), datetime(2026, 3, 13), datetime(2026, 3, 16),
        datetime(2026, 3, 19), datetime(2026, 3, 20)
    ]

    symbol = "WIN$"
    capital = 500.0

    if not mt5.initialize():
        print(" Falha ao inicializar MT5")
        return

    tz = pytz.timezone("Etc/UTC")
    
    total_geral_pnl = 0.0
    total_geral_trades = 0
    total_geral_wins = 0

    for tgt_date in dates_to_test:
        date_str = tgt_date.strftime("%d/%m/%Y")
        
        # Pull 3-days before for perfect warmup
        utc_from = (tgt_date - timedelta(days=3)).replace(hour=0, minute=0, tzinfo=tz)
        utc_to = tgt_date.replace(hour=20, minute=0, tzinfo=tz)
        
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
        if rates is None or len(rates) == 0:
            print(f" {date_str} - Sem dados disponíveis no MT5.")
            continue
            
        data = pd.DataFrame(rates)
        data["time"] = pd.to_datetime(data["time"], unit="s")
        data.set_index("time", inplace=True)
        
        # Configurar Backtest (Usando os Golden Params, base_lot=1 -> 1 Míni = max R$ losses normais)
        tester = BacktestPro(
            symbol=symbol,
            n_candles=3000,
            timeframe="M1",
            initial_balance=capital,
            base_lot=1
        )
        tester.data = data
        tester.generate_report = lambda: None
        
        # Suprimir logs padrão
        logger = logging.getLogger()
        old_level = logger.level
        logger.setLevel(logging.ERROR)
        
        await tester.run()
        
        logger.setLevel(old_level)
        
        # Filtrar trades que ocorreram no `tgt_date` especificamente
        target_date_obj = tgt_date.date()
        daily_trades = [t for t in tester.trades if pd.to_datetime(t["entry_time"]).date() == target_date_obj]
        
        pnl = sum(t["pnl_fin"] for t in daily_trades)
        
        win_trades = [t for t in daily_trades if t["pnl_fin"] > 0]
        loss_trades = [t for t in daily_trades if t["pnl_fin"] <= 0]
        
        buy_trades = [t for t in daily_trades if t.get("side", "").lower() == "buy"]
        sell_trades = [t for t in daily_trades if t.get("side", "").lower() == "sell"]
        buy_win = len([t for t in buy_trades if t["pnl_fin"] > 0])
        sell_win = len([t for t in sell_trades if t["pnl_fin"] > 0])
        
        num_trades = len(daily_trades)
        wins = len(win_trades)
        win_rate = (wins / num_trades * 100) if num_trades > 0 else 0
        
        print(f"\n DIA: {date_str} | Capital Alocado: R$ 500,00")
        print(f"   ► PnL Líquido (só hoje): R$ {pnl:.2f} ({pnl/capital*100:.2f}%)")
        print(f"   ► Trades Executados (só hoje): {num_trades} (Win Rate: {win_rate:.1f}%)")
        
        if num_trades > 0:
            print(f"      - COMPRAS: {len(buy_trades)} (Vitórias: {buy_win})")
            print(f"      - VENDAS : {len(sell_trades)} (Vitórias: {sell_win})")
            print(f"      - Maiores Prejuízos: {min([t['pnl_fin'] for t in loss_trades]) if loss_trades else 0:.2f}")
            print(f"      - Maiores Ganhos   : {max([t['pnl_fin'] for t in win_trades]) if win_trades else 0:.2f}")
            
        total_geral_pnl += pnl
        total_geral_trades += num_trades
        total_geral_wins += wins

    print("\n" + "="*80)
    print(" RESUMO GERAL DAS OPERAÇÕES (Contabilizado Dia-a-Dia, isoladamente)")
    print("="*80)
    print(f"► Total PnL Líquido Agregado: R$ {total_geral_pnl:.2f}")
    if total_geral_trades > 0:
        print(f"► Total Trades Realizados  : {total_geral_trades}")
        print(f"► Assertividade Média Geral: {(total_geral_wins/total_geral_trades)*100:.1f} (%)")
    else:
        print("► Nenhum trade executado (Verificar configurações e filtros).")
    print("="*80 + "\n")

    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(run_individual_day_audit())
