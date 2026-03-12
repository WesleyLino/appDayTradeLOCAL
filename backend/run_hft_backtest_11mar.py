import asyncio
import logging
import pandas as pd
import os
import sys
from datetime import datetime

# Adiciona diretório raiz para importações
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

# Configuração de Idioma (OBRIGATÓRIO PT-BR)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Analise11Mar")

class BacktestCustom(BacktestPro):
    """Extensão para permitir filtrar direções específicas no backtest."""
    def __init__(self, direction_filter=None, **kwargs):
        super().__init__(**kwargs)
        self.direction_filter = direction_filter # 'buy', 'sell' ou None

    def _should_ignore_signal(self, side):
        if self.direction_filter and side != self.direction_filter:
            return True
        return False

# Nota: O BacktestPro original não chama uma função centralizada de sinal fácil de interceptar sem mudar muito o código.
# Então vou apenas rodar o SOTA completo e analisar os resultados segmentados por trade side.

async def run_analysis():
    data_file = "backend/historico_WIN_11mar.csv"
    if not os.path.exists(data_file):
        logger.error(f"❌ Arquivo de dados não encontrado: {data_file}")
        return

    logger.info("🎯 Iniciando Auditoria Técnica 11/03 - Capital R$ 3.000,00")
    
    # 1. Configuração do Backtest (SOTA v23.1)
    # O BacktestPro carrega os Golden Params de v22_locked_params.json automaticamente
    bt = BacktestPro(
        symbol="WIN$", 
        data_file=data_file, 
        initial_balance=3000.0,
        n_candles=2000 # Cobre o dia todo
    )
    
    await bt.run()
    
    # 2. Processamento de Resultados
    trades = bt.trades
    df_trades = pd.DataFrame(trades)
    
    if df_trades.empty:
        logger.warning("⚠️ Nenhum trade realizado no período com as travas atuais.")
        return

    # 3. Análise Segmentada (Potencial Buy vs Sell)
    buy_trades = df_trades[df_trades['side'] == 'buy']
    sell_trades = df_trades[df_trades['side'] == 'sell']
    
    logger.info("="*50)
    logger.info(f"📊 RESULTADO FINAL (HÍBRIDO): R$ {bt.balance - bt.initial_balance:.2f}")
    logger.info(f"💰 Saldo Final: R$ {bt.balance:.2f}")
    logger.info(f"📈 Total Trades: {len(df_trades)}")
    logger.info("="*50)
    
    def summarize_side(df_side, side_label):
        if df_side.empty:
            logger.info(f"[{side_label}] Sem trades.")
            return
        profit_total = df_side['pnl_fin'].sum()
        wins = len(df_side[df_side['pnl_fin'] > 0])
        losses = len(df_side[df_side['pnl_fin'] <= 0])
        acc = (wins / len(df_side)) * 100
        avg_profit = df_side['pnl_fin'].mean()
        logger.info(f"[{side_label}] Lucro Total: R$ {profit_total:.2f} | Trades: {len(df_side)} | Assertividade: {acc:.1f}% | Méd/Trade: R$ {avg_profit:.2f}")

    summarize_side(buy_trades, "COMPRA")
    summarize_side(sell_trades, "VENDA")
    
    # 4. Análise de Vetos e Perda de Oportunidades
    shadow = bt.shadow_signals
    logger.info("="*50)
    logger.info("🛡️ ANÁLISE DE VETOS (Oportunidades Filtradas pela IA)")
    logger.info(f"Total de candidatos descartados: {shadow['v22_candidates']}")
    logger.info(f"Filtrados por IA/Confiança: {shadow.get('filtered_by_ai', 0)}")
    logger.info(f"Filtrados por Fluxo/OBI: {shadow.get('filtered_by_flux', 0)}")
    logger.info(f"Filtrados por Bias H1/Tendência: {shadow.get('filtered_by_bias', 0)}")
    
    # Razões específicas de veto
    for reason, count in shadow.get('veto_reasons', {}).items():
        logger.info(f"   - {reason}: {count}")

    # 5. Exportação de Relatório Técnico
    results = {
        "status": "Finalizado",
        "date": "2026-03-11",
        "pnl_total": float(bt.balance - bt.initial_balance),
        "total_trades": int(len(df_trades)),
        "buy_pnl": float(buy_trades['pnl_fin'].sum()) if not buy_trades.empty else 0.0,
        "sell_pnl": float(sell_trades['pnl_fin'].sum()) if not sell_trades.empty else 0.0,
        "vetos": shadow
    }
    
    import json
    with open("backend/backtest_report_11mar.json", "w") as f:
        json.dump(results, f, indent=4)
        
    logger.info("✅ Relatório gerado em backend/backtest_report_11mar.json")

if __name__ == "__main__":
    asyncio.run(run_analysis())
