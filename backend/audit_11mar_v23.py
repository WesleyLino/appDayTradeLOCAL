import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import traceback

# Ajuste de path para importar backend
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro
from backend.mt5_bridge import MT5Bridge

# OBRIGAÇÃO: PT-BR
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Auditoria_11Mar")

async def run_audit():
    try:
        logger.info("🚀 Iniciando Auditoria SOTA v23 - Data: 11/03/2026")
        logger.info("💰 Capital Inicial: R$ 3.000,00")
        
        # 1. Conexão e Coleta
        bridge = MT5Bridge()
        if not bridge.connect():
            logger.error("❌ Erro ao conectar ao MT5. Certifique-se que o terminal está aberto.")
            return

        symbol = "WIN$" # Símbolo contínuo para backtest
        logger.info(f"📥 Coletando dados históricos para {symbol}...")
        
        date_from = datetime(2026, 3, 11, 0, 0)
        date_to = datetime(2026, 3, 11, 23, 59)
        
        import MetaTrader5 as mt5
        # Precisamos coletar um pouco antes para os indicadores (SMA20, etc) não virem NaNs no início do dia
        date_from_pre = date_from - timedelta(hours=2)
        df = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, date_from_pre, date_to)
        
        if df.empty:
            logger.error("❌ Nenhum dado encontrado para o dia 11/03. Verifique o histórico do MT5.")
            return

        logger.info(f"📊 {len(df)} candles coletados (incluindo lookback).")

        # 2. Configuração do Backtest
        bt = BacktestPro(symbol=symbol, initial_balance=3000.0)
        bt.data = df 
        
        # 3. Execução
        logger.info("⚙️ Executando simulação SOTA v23...")
        # bt.run() é assíncrono? Sim, de acordo com o view_file
        report = await bt.run()
        
        if report is None:
            logger.error("❌ O backtest retornou 'None'. Algo falhou internamente no bt.run()")
            return

        # 4. Filtrar resultados para o dia 11/03 apenas (Remover lookback inicial)
        trades_total = report.get('trades', [])
        trades_11mar = [t for t in trades_total if t['entry_time'].date() == datetime(2026, 3, 11).date()]

        # 5. Análise de Oportunidades Perdidas (Shadow Signals)
        shadow = report.get('shadow_signals', {})
        
        print("\n" + "="*80)
        print(f"{'RELATÓRIO DE PERFORMANCE SOTA v23 - 11/03/2026':^80}")
        print("="*80)
        print("Saldo Inicial:   R$ 3.000,00")
        print(f"Saldo Final:     R$ {report['final_balance']:.2f}")
        print(f"Lucro/Prejuízo:  R$ {report['total_pnl']:.2f}")
        print(f"Trades do Dia:   {len(trades_11mar)}")
        print(f"Taxa de Acerto:  {report['win_rate']:.1f}%")
        print(f"Drawdown Máx:    {report['max_drawdown']:.2f}%")
        print("-" * 80)
        
        # Detalhar tipos de operações
        trades_df = pd.DataFrame(trades_11mar)
        if not trades_df.empty:
            buys = trades_df[trades_df['side'] == 'buy']
            sells = trades_df[trades_df['side'] == 'sell']
            print(f"Operações COMPRA:  {len(buys):<3} | PnL Somado: R$ {buys['pnl_fin'].sum():.2f}")
            print(f"Operações VENDA:   {len(sells):<3} | PnL Somado: R$ {sells['pnl_fin'].sum():.2f}")
        else:
            print("Nenhuma operação executada no dia (Filtros Conservadores).")
        
        print("-" * 80)
        print("INDICADORES DE OPORTUNIDADE (Shadow Signals):")
        print(f"- Sinais Candidatos (V22): {shadow.get('v22_candidates', 0)}")
        print(f"- Vetos por Insegurança IA: {shadow.get('filtered_by_ai', 0)}")
        print(f"- Vetos por Fluxo (OBI):    {shadow.get('filtered_by_flux', 0)}")
        
        # Veto reasons
        reasons = shadow.get('vet_reasons', shadow.get('veto_reasons', {}))
        if reasons:
            print(f"- Principais Motivos de Veto: {reasons}")
        
        print("\n" + "="*80)
        print("MELHORIAS SUGERIDAS:")
        if shadow.get('filtered_by_ai', 0) > 5:
            print("1. Relaxar threshold de confiança em 10% para regimes de tendência comprovada.")
        if len(trades_11mar) == 0:
            print("1. Reduzir exigência de 'Bollinger Squeeze' para 1.0 em dias de expansão de volatilidade.")
        print("2. Calibrar Trailing Stop para travar 30% mais rápido em scalpings laterais.")
        print("="*80 + "\n")

        bridge.disconnect()

    except Exception as e:
        logger.error(f"❌ Erro fatal na auditoria: {e}")
        traceback.print_exc()
        if 'bridge' in locals():
            bridge.disconnect()

if __name__ == "__main__":
    asyncio.run(run_audit())
