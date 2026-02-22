import asyncio
import json
import os
import sys
import logging
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_deep_potential_analysis():
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
    
    # Customizações para R$ 3000
    initial_capital = 3000.0
    # 1 lote por 1000 reais = 3 lotes
    # No BacktestPro, se passarmos lots, ele usará fixo se dynamic_lot for False
    params['dynamic_lot'] = False 
    
    # Ativamos Trailing Stop e Breakeven (Modo SOTA)
    params['use_trailing_stop'] = True
    params['be_trigger'] = 75.0
    params['be_lock'] = 10.0
    
    print("\n" + "="*70)
    print(f"🚀 ANÁLISE PROFUNDA DE POTENCIAL - QUANTUMTRADE PRO")
    print(f"Instrumento: WIN$ (Mini Índice) | Capital: R$ {initial_capital:.2f}")
    print(f"Estratégia: SOTA Precision (3 Lotes Fixos - 1 por k)")
    print("="*70 + "\n")

    # 2. Configurar o Backtester (600 candles ~ 1 dia M1)
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=600, 
        timeframe="M1", 
        initial_balance=initial_capital,
        **params
    )
    
    # Forçamos 3 lotes para este teste de 3k (sobrescrevendo o default de 1 no backtest_pro.py:407 se necessário)
    # Na verdade, o backtest_pro usa self.opt_params, mas o lote é calculado no loop.
    # Vamos injetar o comportamento de 3 lotes fixos.
    bt.opt_params['force_lots'] = 3

    # 3. Rodar Backtest
    print("⏳ Sincronizando dados reaia via MT5...")
    df = await bt.load_data()
    if df is not None:
        start_date = df.index[0].strftime("%d/%m/%Y %H:%M")
        end_date = df.index[-1].strftime("%d/%m/%Y %H:%M")
        print(f"📅 Janela: {start_date} até {end_date}")
        
        print("⏳ Executando simulação e capturando sinais de sombra...")
        report = await bt.run()
        
        # 4. Exibir Resultados Consolidados
        print("\n" + "="*70)
        print("📊 RESULTADOS DA SIMULAÇÃO")
        print("="*70)
        print(f"Lucro Líquido:.............. R$ {report['total_pnl']:.2f} ({ (report['total_pnl']/initial_capital)*100:.1f}%)")
        print(f"Taxa de Acerto:............. {report['win_rate']:.1f}%")
        print(f"Fator de Lucro:............. {report['profit_factor']:.2f}")
        print(f"Drawdown Máximo:............ {report['max_drawdown']:.2f}%")
        
        # 5. Análise de Oportunidades Perdidas (Missed Insights)
        shadow = report.get('shadow_signals', {})
        print("\n" + "="*70)
        print("🕵️ ANÁLISE DE OPORTUNIDADES PERDIDAS (MISSING OPS)")
        print("="*70)
        print(f"Total de Sinais Filtrados:.. {shadow.get('total_missed', 0)}")
        print(f"Bloqueados por IA (SOTA):... {shadow.get('filtered_by_ai', 0)}")
        print(f"Bloqueados por Fluxo:....... {shadow.get('filtered_by_flux', 0)}")
        print(f"Bloqueados por Volatilidade: {shadow.get('filtered_by_vol', 0)}")
        
        # Breakdown por confiança
        tiers = shadow.get('tiers', {})
        print("\nBreakdown de Sinais Filtrados pela IA (Quase Entradas):")
        print(f"  70-75% Confiança:........ {tiers.get('70-75', 0)}")
        print(f"  75-80% Confiança:........ {tiers.get('75-80', 0)}")
        print(f"  80-85% Confiança:........ {tiers.get('80-85', 0)}")
        
        # 6. Diagnóstico de Melhorias
        print("\n" + "="*70)
        print("💡 DIAGNÓSTICO E MELHORIAS (ASSERTIVIDADE)")
        print("="*70)
        if report['win_rate'] >= 80:
            print("- Assertividade EXCELENTE. Sugestão: Aumentar volume progressivamente via Anti-Martingale.")
        elif shadow.get('filtered_by_ai', 0) > 5:
            print("- Muitos sinais bloqueados pela IA. Sugestão: Ajustar 'confidence_threshold' para 0.80 para capturar mais volume.")
        else:
            print("- Perfil conservador mantido. Sugestão: Refinar STOP loss dinâmico baseado no ATR para evitar ruído.")
        
        print("\n- Reduzir 'trailing_step' para 15 pontos pode travar lucros mais rápido em WIN$.")
        print("- Considerar filtro de 'Sentiment' agressivo para evitar contratendências macro.")
        print("="*70 + "\n")
        
        # Salvar para auditoria
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'isoformat'): return obj.isoformat()
                return super().default(obj)

        report_path = "backend/deep_potential_3k_report.txt"
        with open(report_path, 'w') as f:
            f.write(f"DEEP POTENTIAL ANALYSIS - WIN$ - R$ 3000\n")
            json.dump(report, f, indent=4, cls=CustomEncoder)
            
        print(f"✅ Relatório profundo salvo em: {report_path}")
    else:
        print("❌ Erro ao coletar dados do MT5.")

if __name__ == "__main__":
    asyncio.run(run_deep_potential_analysis())
