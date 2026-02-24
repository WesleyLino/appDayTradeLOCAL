import asyncio
import json
import os
import sys
import logging
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_potential_analysis():
    # Configuração de Logs para ver os sinais
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 1. Carregar parâmetros campeões
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        # Fallback se não existir na raiz
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    
    if not os.path.exists(params_path):
        print(f"Erro: Arquivo {params_path} não encontrado.")
        return
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    
    params = config['params']
    
    # Customizações para o teste solicitado pelo usuário
    initial_capital = 1000.0
    # Ativamos Trailing Stop e Breakeven se não estiverem explícitos
    params['use_trailing_stop'] = True
    params['be_trigger'] = 75.0 # Breakeven conservador
    params['be_lock'] = 10.0
    
    print("\n" + "="*60)
    print("🚀 TESTE DE POTENCIAL DE GANHO - QUANTUMTRADE PRO")
    print("Instrumento: WIN$ (Mini Índice)")
    print(f"Timeframe: M1 | Capital Inicial: R$ {initial_capital:.2f}")
    print("SOTA Aligned: Sim (Trailing Stop & Breakeven ATIVOS)")
    print("="*60 + "\n")

    # 2. Configurar o Backtester (Amostra de 1 dia ~ 540 candles)
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=600, 
        timeframe="M1", 
        initial_balance=initial_capital,
        **params
    )

    # 3. Rodar Backtest
    print("⏳ Sincronizando com MT5 e coletando dados históricos...")
    df = await bt.load_data()
    if df is not None:
        start_date = df.index[0].strftime("%d/%m/%Y %H:%M")
        end_date = df.index[-1].strftime("%d/%m/%Y %H:%M")
        print(f"📅 Janela de Análise: {start_date} até {end_date}")
        
        print("⏳ Processando simulação de alta fidelidade...")
        report = await bt.run()
        
        # 4. Exibir Resultados
        print("\n" + "="*60)
        print("📊 RELATÓRIO DE POTENCIAL (1 DIA)")
        print("="*60)
        for key, value in report.items():
            if key == 'trades': continue # Pula lista gigante de trades no print
            if isinstance(value, float):
                print(f"{key:.<40} {value:.2f}")
            else:
                print(f"{key:.<40} {value}")
        print("="*60 + "\n")
        
        # Salvar resultado para auditoria com encoder customizado para Timestamps
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return super().default(obj)

        report_path = "backend/potencial_ganho_report.txt"
        with open(report_path, 'w') as f:
            f.write("RELATÓRIO DE POTENCIAL DE GANHO - WIN$\n")
            f.write(f"Data Execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Janela: {start_date} - {end_date}\n\n")
            json.dump(report, f, indent=4, cls=CustomEncoder)
            
        print(f"✅ Relatório detalhado salvo em: {report_path}")
    else:
        print("❌ Falha crítica: Não foi possível carregar dados do MT5.")

if __name__ == "__main__":
    asyncio.run(run_potential_analysis())
