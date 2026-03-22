import asyncio
import logging
from datetime import datetime, timedelta
import sys
import os
import pandas as pd
import MetaTrader5 as mt5

# Adiciona o diretório raiz
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.data_collector_historical import HistoricalDataCollector
from backend.train_patchtst import train_sota
from backend.backtest_pro import BacktestPro

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def collect_data_for_dates(start_date, end_date):
    logging.info(f"=== COLETANDO DADOS MT5 DE {start_date.date()} ATÉ {end_date.date()} ===")
    collector = HistoricalDataCollector()
    if not collector.connect():
        logging.error("Falha ao inicializar MT5")
        return False

    symbols = ["WIN$", "WDO$", "VALE3", "PETR4", "ITUB4"]
    for symbol in symbols:
        logging.info(f"Coletando para {symbol}...")
        df_c = collector.get_historical_candles(symbol, mt5.TIMEFRAME_M1, start_date, end_date)
        df_t = None
        if symbol in ["WIN$", "WDO$"]:
            df_t = collector.get_historical_ticks(symbol, start_date, end_date)
        
        collector.process_and_save(symbol, df_c, df_t)
    
    mt5.shutdown()
    logging.info("Coleta finalizada.")
    return True

async def run_analysis():
    logging.info("=== INICIANDO RETREINAMENTO DE ALTA PERFORMANCE (19/03 E 20/03) ===")
    
    # 1. Coletar dados
    start_date = datetime(2026, 3, 19)
    end_date = datetime(2026, 3, 21) # Até o início do dia 21 para incluir o final do dia 20
    
    # Executa coleta
    collect_data_for_dates(start_date, end_date)
    
    # 2. Retreinar o modelo de alta performance
    logging.info("=== INICIANDO RETREINAMENTO COM DADOS ATUALIZADOS ===")
    # Retreina apenas 3 épocas para uma calibragem rápida e perfeita (fine-tuning)
    train_sota(epochs=3, batch_size=128, lr=0.00005)
    
    # 3. Executar o Backtest
    logging.info("=== INICIANDO BACKTEST PARA AVALIAÇÃO DE POTENCIAL DE GANHO ===")
    
    symbol = "WIN$"
    capital = 3000.0

    if not mt5.initialize():
        logging.error("Falha MT5 no Backtest")
        return

    # Usando timezone local para compatibilidade
    tester = BacktestPro(
        symbol=symbol,
        n_candles=3000, 
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=True,
    )

    # Parametros otimizados mantendo restrições de ouro
    # Não alterar os ajustes, configurações e calibragem anteriores se forem mais lucrativos
    
    logging.info("Carregando histórico do terminal MT5 para simulação...")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_date, end_date)
    
    if rates is None or len(rates) == 0:
        logging.error("Nenhum dado retornado para backtest.")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    tester.data = df

    logging.info(f"Dados carregados para Backtest: {len(df)} candles.")

    # Executar Simulacao
    await tester.run()

    # Relatorio
    trades = tester.trades
    shadow = tester.shadow_signals

    print("\n" + "="*60)
    print("DIAGNÓSTICO E POTENCIAL DE GANHO - SOTA PRO - 19/03 A 20/03")
    print("="*60)
    print(f"Capital Inicial:  R$ {capital:.2f}")
    print(f"Saldo Final:      R$ {tester.balance:.2f}")
    print(f"Lucro/Prejuízo:   R$ {tester.balance - capital:.2f}")
    print(f"Total de Trades:  {len(trades)}")

    if len(trades) > 0:
        win_rate = (len([t for t in trades if t["pnl_fin"] > 0]) / len(trades)) * 100
        print(f"Assertividade Geral: {win_rate:.2f}%")

        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]

        buy_pnl = sum([t["pnl_fin"] for t in buy_trades])
        sell_pnl = sum([t["pnl_fin"] for t in sell_trades])

        buy_wr = (len([t for t in buy_trades if t["pnl_fin"] > 0]) / len(buy_trades) * 100) if buy_trades else 0
        sell_wr = (len([t for t in sell_trades if t["pnl_fin"] > 0]) / len(sell_trades) * 100) if sell_trades else 0

        print("\n[ ANÁLISE POR DIREÇÃO (POTENCIAL COMPRADA vs VENDIDA) ]")
        print(f"🔵 COMPRAS (BUY):  {len(buy_trades)} trades | PnL: R$ {buy_pnl:.2f} | Assertividade: {buy_wr:.2f}%")
        print(f"🔴 VENDAS (SELL):  {len(sell_trades)} trades | PnL: R$ {sell_pnl:.2f} | Assertividade: {sell_wr:.2f}%")
        
        # Losses / Prejuízos
        loss_trades = [t for t in trades if t["pnl_fin"] < 0]
        max_loss = min([t["pnl_fin"] for t in trades]) if loss_trades else 0
        total_loss = sum([t["pnl_fin"] for t in loss_trades])
        print("\n[ ANÁLISE DE PREJUÍZOS ]")
        print(f"Trades com Perda: {len(loss_trades)}")
        print(f"Prejuízo Total Bruto: R$ {total_loss:.2f}")
        print(f"Pior Drawdown em um trade: R$ {max_loss:.2f}")

    print("\n[ ANÁLISE DE PERDAS DE OPORTUNIDADES (SHADOW SIGNALS) ]")
    print(f"Sinais V22 Potenciais Detectados: {shadow.get('v22_candidates', 0)}")
    print(f"Oportunidades Bloqueadas (Vetos): {shadow.get('total_missed', 0)}")
    print(f"- Negados pela IA (Baixa Convicção): {shadow.get('filtered_by_ai', 0)}")
    print(f"- Negados pelo Fluxo OBI:            {shadow.get('filtered_by_flux', 0)}")
    
    # Sugestões de melhorias para elevar assertividade
    print("\n[ PONTOS DE MELHORIA E CALIBRAGEM PERFEITA ]")
    
    if (tester.balance - capital) > 0:
         print("✅ O sistema já está lucrativo. MANTENHA as configurações golden sem alterações drásticas.")
    
    if shadow.get("filtered_by_flux", 0) > len(trades):
         print("💡 As oportunidades de ouro podem estar sendo bloqueadas pelo fluxo (OBI).")
         print("   Ajuste Suave: Considere reduzir ligeiramente 'flux_imbalance_threshold' para capturar mais volatilidade de início de movimento.")
    
    if len(trades) > 0:
        if buy_wr < 50:
            print("💡 COMPRAS estão com baixa assertividade. O mercado esteve em forte tendência de baixa ou falso rompimento.")
            print("   Melhoria: Elevar 'rsi_buy_level' ou aumentar limite de Fluxo Comprador na entrada.")
        if sell_wr < 50:
             print("💡 VENDAS estão com baixa assertividade. O mercado esteve consolidado em suportes ou com squeeze ascendente.")
             print("   Melhoria: Diminuir 'rsi_sell_level' ou reforçar confirmação do ADX > 25.")
    
    print("\n" + "="*60)
    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(run_analysis())
