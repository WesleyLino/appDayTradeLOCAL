import asyncio
import logging
from datetime import datetime, timedelta
import sys
import os
import pandas as pd
import MetaTrader5 as mt5

# Adiciona o diretório raiz
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.backtest_pro import BacktestPro

logging.basicConfig(level=logging.ERROR) # Apenas erros para limpar o output

async def run_analysis():
    start_date = datetime(2026, 3, 19)
    end_date = datetime(2026, 3, 21)
    
    symbol = "WIN$"
    capital = 500.0

    if not mt5.initialize():
        print("Falha MT5")
        return

    tester = BacktestPro(
        symbol=symbol,
        n_candles=3000, 
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=False, # fixo para 500 reais
        use_ai_core=True,
    )

    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        print("Nenhum dado.")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    tester.data = df

    await tester.run()

    trades = tester.trades
    shadow = tester.shadow_signals

    with open("result_mar19_20.txt", "w", encoding="utf-8") as f:
        f.write("\n" + "="*60 + "\n")
        f.write("DIAGNÓSTICO E POTENCIAL DE GANHO - SOTA PRO - 19/03 A 20/03\n")
        f.write("="*60 + "\n")
        f.write(f"Capital Inicial:  R$ {capital:.2f}\n")
        f.write(f"Saldo Final:      R$ {tester.balance:.2f}\n")
        f.write(f"Lucro/Prejuízo:   R$ {tester.balance - capital:.2f}\n")
        f.write(f"Total de Trades:  {len(trades)}\n")

        if len(trades) > 0:
            win_rate = (len([t for t in trades if t["pnl_fin"] > 0]) / len(trades)) * 100
            f.write(f"Assertividade Geral: {win_rate:.2f}%\n")

            buy_trades = [t for t in trades if t["side"] == "buy"]
            sell_trades = [t for t in trades if t["side"] == "sell"]

            buy_pnl = sum([t["pnl_fin"] for t in buy_trades])
            sell_pnl = sum([t["pnl_fin"] for t in sell_trades])

            buy_wr = (len([t for t in buy_trades if t["pnl_fin"] > 0]) / len(buy_trades) * 100) if buy_trades else 0
            sell_wr = (len([t for t in sell_trades if t["pnl_fin"] > 0]) / len(sell_trades) * 100) if sell_trades else 0

            f.write("\n[ ANÁLISE POR DIREÇÃO (POTENCIAL COMPRADA vs VENDIDA) ]\n")
            f.write(f"🔵 COMPRAS (BUY):  {len(buy_trades)} trades | PnL: R$ {buy_pnl:.2f} | Assertividade: {buy_wr:.2f}%\n")
            f.write(f"🔴 VENDAS (SELL):  {len(sell_trades)} trades | PnL: R$ {sell_pnl:.2f} | Assertividade: {sell_wr:.2f}%\n")
            
            loss_trades = [t for t in trades if t["pnl_fin"] < 0]
            max_loss = min([t["pnl_fin"] for t in trades]) if loss_trades else 0
            total_loss = sum([t["pnl_fin"] for t in loss_trades])
            f.write(f"\n[ ANÁLISE DE PREJUÍZOS ]\n")
            f.write(f"Trades com Perda: {len(loss_trades)}\n")
            f.write(f"Prejuízo Total Bruto: R$ {total_loss:.2f}\n")
            f.write(f"Pior Drawdown em um trade: R$ {max_loss:.2f}\n")

        f.write(f"\n[ HISTÓRICO DE TRADES ]\n")
        for t in trades:
            f.write(f"{t['entry_time']} -> {t['side']} | PnL: R$ {t['pnl_fin']:.2f} | Reason: {t['reason']} | Lotes: {t['lots']}\n")

        f.write("\n[ ANÁLISE DE PERDAS DE OPORTUNIDADES (SHADOW SIGNALS) ]\n")
        f.write(f"Sinais V22 Potenciais Detectados: {shadow.get('v22_candidates', 0)}\n")
        f.write(f"Oportunidades Bloqueadas (Vetos): {shadow.get('total_missed', 0)}\n")
        f.write(f"- Negados pela IA (Baixa Convicção): {shadow.get('filtered_by_ai', 0)}\n")
        f.write(f"- Negados pelo Fluxo OBI:            {shadow.get('filtered_by_flux', 0)}\n")
        
        f.write("\n[ PONTOS DE MELHORIA E CALIBRAGEM PERFEITA ]\n")
        
        if (tester.balance - capital) > 0:
            f.write("✅ O sistema já está lucrativo. MANTENHA as configurações golden sem alterações drásticas.\n")
        
        if shadow.get("filtered_by_flux", 0) > len(trades) and shadow.get("filtered_by_flux", 0) > 0:
            f.write("💡 As oportunidades de ouro podem estar sendo bloqueadas pelo fluxo (OBI).\n")
            f.write("   Ajuste Suave: Considere reduzir ligeiramente 'flux_imbalance_threshold' para capturar mais volatilidade de início de movimento.\n")
        
        if len(trades) > 0:
            if buy_wr < 50 and len(buy_trades) > 0:
                f.write("💡 COMPRAS estão com baixa assertividade. O mercado esteve em forte tendência de baixa ou falso rompimento.\n")
                f.write("   Melhoria: Elevar 'rsi_buy_level' ou aumentar limite de Fluxo Comprador na entrada.\n")
            if sell_wr < 50 and len(sell_trades) > 0:
                f.write("💡 VENDAS estão com baixa assertividade. O mercado esteve consolidado em suportes ou squeeze ascendente.\n")
                f.write("   Melhoria: Diminuir 'rsi_sell_level' ou reforçar confirmação do ADX > 25.\n")
        
        f.write("\n" + "="*60 + "\n")

    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(run_analysis())
