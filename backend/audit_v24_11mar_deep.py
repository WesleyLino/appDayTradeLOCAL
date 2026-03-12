import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, time, date, timedelta
from backend.backtest_pro import BacktestPro
from backend.mt5_bridge import MT5Bridge

# Configuração OBRIGATÓRIA em PT-BR
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Auditoria_v24_Deep")

async def run_deep_audit_11mar():
    logger.info("💎 [v24 DEEP AUDIT] Iniciando análise de potencial para 11/03/2026")
    
    # Capital Social de R$ 3.000,00
    capital_inicial = 3000.0
    
    # Criar instância do BacktestPro com os parâmetros v24
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=3500, # Aumentado para garantir cobertura
        initial_balance=capital_inicial
    )
    
    # Carregar dados
    logger.info("📡 Coletando dados históricos do MT5 para WIN$...")
    data = await bt.load_data()
    
    if data is None or data.empty:
        logger.error("❌ Erro ao coletar dados. Verifique a conexão com o MT5.")
        return

    # No BacktestPro.load_data, 'time' é o index
    target_date = date(2026, 3, 11)
    
    # Filtrar apenas o dia 11/03
    day_data = data[data.index.date == target_date].copy()
    
    if day_data.empty:
        logger.warning("⚠️ Dados do dia 11/03 não encontrados no buffer principal.")
        return

    logger.info(f"📊 Processando {len(day_data)} candles de M1 para o dia 11/03.")
    
    # Injetar os dados filtrados no objeto de backtest e rodar
    bt.data = day_data
    await bt.run()
    
    trades = bt.trades
    
    # --- ANÁLISE DE RESULTADOS ---
    logger.info("✅ Simulação concluída. Gerando métricas direcionais...")
    
    df_trades = pd.DataFrame(trades)
    
    if df_trades.empty:
        logger.warning("⚠️ Nenhum trade executado pelo motor v24 em 11/03.")
        return

    # Ajuste de Chaves: BacktestPro usa 'pnl_fin' e 'pnl_pts'
    col_pnl = 'pnl_fin'
    
    # Métricas de Operação Comprada vs Vendida
    compras = df_trades[df_trades['side'] == 'buy']
    vendas = df_trades[df_trades['side'] == 'sell']
    
    lucro_total = df_trades[col_pnl].sum()
    taxa_acerto = (df_trades[col_pnl] > 0).mean() * 100
    
    logger.info("\n" + "="*40)
    logger.info("       RELATÓRIO DE POTENCIAL v24        ")
    logger.info("="*40)
    logger.info(f"💰 Capital Inicial: R$ {capital_inicial:.2f}")
    logger.info(f"💵 Resultado Líquido: R$ {lucro_total:.2f}")
    logger.info(f"🎯 Assertividade Geral: {taxa_acerto:.1f}%")
    logger.info("-"*40)
    logger.info(f"📈 COMPRAS: {len(compras)} trades | Pnl: R$ {compras[col_pnl].sum() if not compras.empty else 0:.2f}")
    logger.info(f"📉 VENDAS:  {len(vendas)} trades | Pnl: R$ {vendas[col_pnl].sum() if not vendas.empty else 0:.2f}")
    logger.info("="*40)
    
    # Identificação de melhorias (Análise de Drawdown)
    if 'drawdown' in df_trades.columns:
        logger.info(f"📉 Drawdown Máximo: R$ {df_trades['drawdown'].max():.2f}")

if __name__ == "__main__":
    asyncio.run(run_deep_audit_11mar())
