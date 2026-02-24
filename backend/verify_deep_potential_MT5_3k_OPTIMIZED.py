import asyncio
import json
import os
import sys
import logging
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_optimized_potential_analysis():
    # Configuração de Logs
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    
    if not os.path.exists(params_path):
        print(f"Erro: Arquivo {params_path} não encontrado.")
        return
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    
    params = config['params']
    
    # Capital Inicial
    initial_capital = 3000.0
    
    # APLICANDO MELHORIAS SUGERIDAS
    params['dynamic_lot'] = True  # Anti-Martingale ATIVO
    params['base_lot'] = 3        # Começa com 3 lotes (1 por k)
    params['trailing_step'] = 15.0 # Trailing mais curto (Otimizado para WIN$)
    params['be_trigger'] = 70.0    # Breakeven mais agressivo
    params['be_lock'] = 15.0       # Trava de lucro maior no BE
    
    print("\n" + "="*70)
    print("🚀 ANÁLISE OTIMIZADA DE POTENCIAL - QUANTUMTRADE PRO")
    print(f"Instrumento: WIN$ (Mini Índice) | Capital: R$ {initial_capital:.2f}")
    print("Estratégia: SOTA Optimized (Base 3 Lotes + Anti-Martingale)")
    print("="*70 + "\n")

    # 2. Configurar o Backtester (600 candles ~ 1 dia M1)
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=600, 
        timeframe="M1", 
        initial_balance=initial_capital,
        **params
    )
    
    # 3. Rodar Backtest
    print("⏳ Sincronizando dados reais via MT5...")
    df = await bt.load_data()
    if df is not None:
        start_date = df.index[0].strftime("%d/%m/%Y %H:%M")
        end_date = df.index[-1].strftime("%d/%m/%Y %H:%M")
        print(f"📅 Janela: {start_date} até {end_date}")
        
        print("⏳ Executando simulação OTIMIZADA...")
        report = await bt.run()
        
        # 4. Exibir Resultados Consolidados
        print("\n" + "="*70)
        print("📊 RESULTADOS DA SIMULAÇÃO OTIMIZADA")
        print("="*70)
        print(f"Lucro Líquido:.............. R$ {report['total_pnl']:.2f} ({ (report['total_pnl']/initial_capital)*100:.1f}%)")
        print(f"Taxa de Acerto:............. {report['win_rate']:.1f}%")
        print(f"Fator de Lucro:............. {report['profit_factor']:.2f}")
        print(f"Drawdown Máximo:............ {report['max_drawdown']:.2f}%")
        
        # 5. Comparativo com o teste anterior (estático)
        # Note: O teste anterior deu R$ 75.00
        improvement = ((report['total_pnl'] / 75.0) - 1) * 100
        print(f"Diferença vs Estático:...... {improvement:+.1f}% de lucro")
        
        # 6. Diagnóstico Final
        print("\n" + "="*70)
        print("💡 VERIFICAÇÃO DE MELHORIA")
        print("="*70)
        if report['total_pnl'] > 75.0:
            print(f"✅ SUCESSO: A otimização aumentou o lucro em R$ {report['total_pnl'] - 75.0:.2f}.")
            print("- O Lote Dinâmico aproveitou a sequência de vitórias.")
            print("- O Trailing Step de 15pt protegeu melhor as reversões rápidas.")
        else:
            print("⚠️ OBSERVAÇÃO: O lucro foi similar ou menor.")
            print("- Talvez a volatilidade do dia não tenha favorecido o trailing mais curto.")
        print("="*70 + "\n")
        
        # Salvar para auditoria
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'isoformat'): return obj.isoformat()
                return super().default(obj)

        report_path = "backend/deep_potential_3k_OPTIMIZED_report.txt"
        with open(report_path, 'w') as f:
            f.write("DEEP POTENTIAL ANALYSIS - OPTIMIZED - WIN$ - R$ 3000\n")
            json.dump(report, f, indent=4, cls=CustomEncoder)
            
        print(f"✅ Relatório otimizado salvo em: {report_path}")
    else:
        print("❌ Erro ao coletar dados do MT5.")

if __name__ == "__main__":
    asyncio.run(run_optimized_potential_analysis())
