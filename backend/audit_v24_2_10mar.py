import asyncio
import logging
import pandas as pd
import numpy as np
from backend.backtest_pro import BacktestPro

# Configuração de Idioma e Logging (OBRIGAÇÃO PT-BR)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AuditoriaV24_2_10mar")

async def run_final_audit():
    logger.info("🤖 Executando Simulação SOTA v24.2.1 - Dados 10/03")
    
    capital = 3000.0
    csv_path = "backend/historico_WIN_10mar_warmup.csv"
    
    try:
        df = pd.read_csv(csv_path)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        df.sort_index(inplace=True)
        
        bt = BacktestPro(symbol="WIN$", capital=capital)
        
        # Limpar NaNs de forma compatível com pandas modernos
        df = df.replace([np.inf, -np.inf], np.nan).ffill().fillna(0)
        
        bt.data = df
        
        logger.info(f"📊 Iniciando simulação com {len(df)} candles (incluindo warm-up)...")
        await bt.run()
        
        # Filtrar trades apenas para o dia 10/03
        trades_10mar = [t for t in bt.trades if t['entry_time'].date() == date(2026, 3, 10)]
        total_trades = len(trades_10mar)
        
        # Calcular PnL apenas do dia 10/03
        pnl_10mar = sum([t['pnl_fin'] for t in trades_10mar])
        
        print("\n" + "="*50)
        print("RESULTADOS AUDITORIA SOTA v24.2.1 - DIA 10/03")
        print("="*50)
        print(f"Saldo Inicial (Dia): R$ {capital:.2f}")
        print(f"Lucro Líquido (10/03): R$ {pnl_10mar:.2f}")
        print(f"Trades Executados (10/03): {total_trades}")
        
        if total_trades > 0:
            wins = len([t for t in bt.trades if t['pnl_fin'] > 0])
            win_rate = (wins / total_trades) * 100
            print(f"Win Rate: {win_rate:.1f}%")
        
        print("\nMOTIVOS DE VETO (SHADOW):")
        print(bt.shadow_signals.get('veto_reasons', {}))
        
        print("\nALVOS ESTENDIDOS (TP MULTIPLIERS):")
        tp_mults = [t.get('tp_multiplier', 1.0) for t in bt.trades]
        if tp_mults:
            print(f"Média TP Multiplier: {np.mean(tp_mults):.2f}x")
            print(f"Máximo TP Multiplier: {np.max(tp_mults):.2f}x")

        print("="*50)

    except Exception as e:
        logger.error(f"❌ Erro na auditoria: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_final_audit())
