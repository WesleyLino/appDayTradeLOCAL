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
logger = logging.getLogger("Auditoria_11Mar_SOTA")

async def run_audit():
    try:
        logger.info("🚀 Iniciando Auditoria Detalhada SOTA v23 - 11/03/2026")
        
        # 1. Coleta de Dados
        bridge = MT5Bridge()
        if not bridge.connect():
            logger.error("❌ Falha na conexão MT5.")
            return

        symbol = "WIN$"
        date_from = datetime(2026, 3, 11, 0, 0)
        date_to = datetime(2026, 3, 11, 23, 59)
        
        import MetaTrader5 as mt5
        date_from_pre = date_from - timedelta(hours=3)
        df = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, date_from_pre, date_to)
        
        if df.empty:
            logger.error("❌ Dados não encontrados.")
            bridge.disconnect()
            return

        # 2. Setup Backtest
        bt = BacktestPro(symbol=symbol, initial_balance=3000.0)
        bt.data = df
        
        # 3. Execução
        report = await bt.run()
        
        # 4. Processamento
        target_date = datetime(2026, 3, 11).date()
        trades = pd.DataFrame(report.get('trades', []))
        if not trades.empty:
            trades['entry_time'] = pd.to_datetime(trades['entry_time'])
            trades = trades[trades['entry_time'].dt.date == target_date]

        shadow = report.get('shadow_signals', {})
        
        # 5. Geração de Artefato (PT-BR)
        artifact_path = r"C:\Users\Wesley Lino\.gemini\antigravity\brain\ceff438f-e2a0-4d7f-b7c5-0346fcb35837\resultado_auditoria_detalhada_11mar.log"
        # Usando .log para evitar conflitos de mime, mas formatado como MD
        
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write("# Resultado Auditoria SOTA v23 - 11/03/2026\n\n")
            
            if not trades.empty:
                buys = trades[trades['side'] == 'buy']
                sells = trades[trades['side'] == 'sell']
                pnl_total = trades['pnl_fin'].sum()
                prejuizo = trades[trades['pnl_fin'] < 0]['pnl_fin'].sum()
                
                f.write(f"## 💰 Performance Financeira\n")
                f.write(f"- **PnL Total Líquido:** R$ {pnl_total:.2f}\n")
                f.write(f"- **Operações COMPRADAS:** {len(buys)} trades | PnL: R$ {buys['pnl_fin'].sum():.2f}\n")
                f.write(f"- **Operações VENDIDAS:** {len(sells)} trades | PnL: R$ {sells['pnl_fin'].sum():.2f}\n")
                f.write(f"- **Prejuízo (Loss):** R$ {prejuizo:.2f}\n")
                f.write(f"- **Taxa de Acerto:** {(len(trades[trades['pnl_fin'] > 0]) / len(trades) * 100):.1f}%\n\n")
            else:
                f.write("## ⚠️ Nenhuma operação executada sob as condições atuais.\n\n")

            f.write("## 🕵️ Análise de Oportunidades (Shadow Signals)\n")
            f.write(f"- **Alertas V22 (Sinais Candidatos):** {shadow.get('v22_candidates', 0)}\n")
            f.write(f"- **Vetos por Insegurança IA:** {shadow.get('filtered_by_ai', 0)}\n")
            f.write(f"- **Vetos por Gerenciamento de Risco:** {shadow.get('filtered_by_risk', 0)}\n\n")
            
            f.write("### Motivos dos Vetos (Perda de Oportunidade):\n")
            reasons = shadow.get('veto_reasons', {})
            for reason, count in reasons.items():
                f.write(f"- **{reason}:** {count} vezes\n")
            
            f.write("\n## 💡 Melhorias Identificadas\n")
            f.write("1. **Momentum Bias**: Ativar rali dinâmico quando ADX > 35 no M5.\n")
            f.write("2. **Proteção de Capital**: Trailing stop mais curto em dias de alta volatilidade.\n")
        
        logger.info(f"✅ Resultados salvos em: {artifact_path}")
        bridge.disconnect()

    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_audit())
