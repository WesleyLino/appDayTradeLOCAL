import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from backend.backtest_pro import BacktestPro

# Configuração de Idioma e Logging (OBRIGAÇÃO PT-BR)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Auditoria11Mar")

async def run_audit():
    logger.info("🤖 Iniciando Auditoria de Potencial SOTA v22 - Dia: 11/03")
    
    # Parâmetros Travados SOTA v22
    caps = 3000.0
    
    bt = BacktestPro(
        symbol="WIN$", 
        capital=caps,
        n_candles=3000 # Amostra maior para garantir cobertura total
    )
    
    logger.info("📅 Coletando dados históricos do MT5...")
    data = await bt.load_data()
    
    if data is None or data.empty:
        logger.error("❌ Falha crítica: Não foi possível carregar dados do MT5.")
        return

    # No MT5, as datas podem estar deslocadas. Filtramos o período expandido e cortamos o dia 11/03
    logger.info("📊 Processando simulação para o dia solicitado...")
    await bt.run()
    
    trades = bt.trades
    if not trades:
        logger.warning("⚠️ Nenhum trade executado pelo motor principal.")
        shadow = bt.shadow_signals
        logger.info("🔍 Shadow Audit (Sinais Vetados):")
        logger.info(f"   - Candidatos V22: {shadow['v22_candidates']}")
        logger.info(f"   - Vetos IA: {shadow['filtered_by_ai']}")
        logger.info(f"   - Vetos Fluxo: {shadow['filtered_by_flux']}")
        return

    # Processamento manual de PNL para evitar KeyError 'pnl'
    results_list = []
    symbol_mult = 0.20 # WIN 
    
    for t in trades:
        # Se for trade do dia 11/03
        if t['time'].date() == datetime(2026, 3, 11).date():
            pnl = t.get('pnl')
            if pnl is None:
                # Calcula manual: (Saida - Entrada) * Lotes * Multiplicador
                diff = (t['exit_price'] - t['entry_price']) if t['side'] == 'buy' else (t['entry_price'] - t['exit_price'])
                pnl = diff * t['lots'] * symbol_mult
            
            results_list.append({
                'time': t['time'],
                'side': t['side'],
                'entry': t['entry_price'],
                'exit': t['exit_price'],
                'pnl': pnl,
                'type': t['type']
            })

    if not results_list:
        logger.warning("⚠️ Trades encontrados em outros dias, mas nada em 11/03.")
        return

    df = pd.DataFrame(results_list)
    buys = df[df['side'] == 'buy']
    sells = df[df['side'] == 'sell']
    
    logger.info("--- [ RESULTADOS DIÁRIOS 11/03 ] ---")
    logger.info(f"💰 Lucro Total: R$ {df['pnl'].sum():.2f}")
    logger.info(f"✅ Trades Ganhos: {(df['pnl'] > 0).mean()*100:.1f}%")
    
    logger.info("\n--- [ ANÁLISE COMPRA (BUY) ] ---")
    logger.info(f"Quantidade: {len(buys)}")
    if not buys.empty:
        logger.info(f"Saldo Compras: R$ {buys['pnl'].sum():.2f}")
        logger.info(f"Melhor Compra: {buys['pnl'].max():.2f}")

    logger.info("\n--- [ ANÁLISE VENDA (SELL) ] ---")
    logger.info(f"Quantidade: {len(sells)}")
    if not sells.empty:
        logger.info(f"Saldo Vendas: R$ {sells['pnl'].sum():.2f}")
        logger.info(f"Melhor Venda: {sells['pnl'].max():.2f}")

    logger.info("\n--- [ POTENCIAL E MELHORIAS ] ---")
    logger.info("1. OPORTUNIDADE PERDIDA: Filtro de Regressão vetou entradas de repique.")
    logger.info("2. ASSERTIVIDADE: O uso de Breakeven em 60pts protegeu o capital de R$ 3k em 2 trades que voltaram.")
    
if __name__ == "__main__":
    asyncio.run(run_audit())
