import asyncio
import json
import os
import sys
import logging
from datetime import datetime
import itertools

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro
import pandas as pd

# Otimização Rápida: Sobrescreve generate_report para não gerar HTML a cada iteração
def fast_generate_report(self):
    df_trades = pd.DataFrame(self.trades)
    if df_trades.empty: return None

    win_rate = (len(df_trades[df_trades['pnl_fin'] > 0]) / len(df_trades)) * 100
    total_pnl = df_trades['pnl_fin'].sum()
    profit_factor = abs(df_trades[df_trades['pnl_fin'] > 0]['pnl_fin'].sum() / df_trades[df_trades['pnl_fin'] < 0]['pnl_fin'].sum()) if any(df_trades['pnl_fin'] < 0) else float('inf')
    
    return {
        'final_balance': self.balance,
        'total_pnl': total_pnl,
        'trades': df_trades.to_dict('records'),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_drawdown': self.max_drawdown * 100,
        'shadow_signals': self.shadow_signals
    }

BacktestPro.generate_report = fast_generate_report

async def run_calibration():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    print("\n" + "="*70)
    print("🚀 RETREINAMENTO E CALIBRAGEM ALTA PERFORMANCE (05/03)")
    print("Instrumento: WIN$ | Capital: R$ 500.00")
    print("Objetivo: Otimizar Assertividade, Ganhos e Reduzir Perdas")
    print("="*70 + "\n")

    # 1. Carregar Baseline (best_params_WIN.json)
    params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    with open(params_path, 'r') as f:
        baseline_config = json.load(f)
    baseline_params = baseline_config['params']
    
    baseline_params['use_trailing_stop'] = True
    
    # 2. Setup do Backtester para baixar os dados de HOJE
    bt_loader = BacktestPro(
        symbol="WIN$", 
        n_candles=600, 
        timeframe="M1", 
        initial_balance=500.0,
        **baseline_params
    )
    
    print("⏳ Conectando ao MT5 para baixar dados do dia...")
    df = await bt_loader.load_data()
    if df is None or len(df) == 0:
        print("❌ Falha crítica: Não foi possível carregar dados do MT5.")
        return
        
    start_date = df.index[0].strftime("%d/%m/%Y %H:%M")
    end_date = df.index[-1].strftime("%d/%m/%Y %H:%M")
    print(f"📅 Dados coletados: {start_date} até {end_date} ({len(df)} candles)")
    
    print("\n⏳ Executando Baseline (Parâmetros Atuais)...")
    await bt_loader.run()
    baseline_report = bt_loader.generate_report()
    
    # Se o baseline_report for None (sem trades)
    if not baseline_report:
        baseline_report = {'total_pnl': 0, 'win_rate': 0, 'trades': [], 'max_drawdown': 0, 'profit_factor': 0}
        baseline_trades_len = 0
    else:
        baseline_trades_len = len(baseline_report.get('trades', []))    
    # Grid de Otimização - Protegendo lucro atual, buscando melhorias pontuais
    # Baseline: sl=150, tp=550, conf=0.75, be_trigger=40
    grid = {
        'sl_dist': [130, 150],
        'tp_dist': [450, 550],
        'confidence_threshold': [0.75, 0.82],
        'be_trigger': [40],
        'vol_spike_mult': [0.8]
    }
    
    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    print(f"\n🔎 Iniciando Calibragem Rápida: Testando {len(combinations)} combinações em silêncio...")
    logging.getLogger().setLevel(logging.CRITICAL)
    
    best_pnl = baseline_report['total_pnl']
    best_params = None
    best_report = None
    best_winrate = baseline_report['win_rate']
    
    for i, p in enumerate(combinations):
        # Mesclar parâmetros base com a combinação atual
        test_params = baseline_params.copy()
        test_params.update(p)
        
        bt = BacktestPro(
            symbol="WIN$", 
            df=df.copy(), # usar o dataframe já baixado
            timeframe="M1", 
            initial_balance=500.0,
            **test_params
        )
        
        # Desabilitar logs do Backtester para não poluir
        await bt.run()
        report = bt.generate_report()
        
        if not report: continue
        
        report_trades_len = len(report.get('trades', []))
        
        # Critério de Seleção: Lucro MAIOR ou WinRate MAIOR com lucro similar (>= 90% do baseline)
        if report_trades_len > 0:
            if report['total_pnl'] > best_pnl or (report['win_rate'] > best_winrate and report['total_pnl'] >= best_pnl * 0.90):
                best_pnl = report['total_pnl']
                best_winrate = report['win_rate']
                best_params = p
                best_report = report
                print(f"✨ Nova Combinação Superior Encontrada: Lucro R$ {best_pnl:.2f} | WR {best_winrate:.2f}% | Configs: {p}")
                
    # Restaura Logs apenas para finalização
    logging.getLogger().setLevel(logging.INFO)
    
    print("\n" + "="*70)
    print("📊 RELATÓRIO FINAL DE CALIBRAGEM (05/03)")
    print("="*70)
    print("--- BASELINE (Configuração Atual) ---")
    print(f"Lucro: R$ {baseline_report['total_pnl']:.2f} | WinRate: {baseline_report['win_rate']:.2f}% | Trades: {baseline_trades_len}")
    print(f"DrawnDown: {baseline_report['max_drawdown']:.2f}% | Profit Factor: {baseline_report['profit_factor']:.2f}")
    
    if best_params:
        best_trades_len = len(best_report.get('trades', []))
        print("\n--- OTIMIZADO (Melhoria Absoluta Encontrada) ---")
        print(f"Lucro: R$ {best_report['total_pnl']:.2f} | WinRate: {best_report['win_rate']:.2f}% | Trades: {best_trades_len}")
        print(f"DrawnDown: {best_report['max_drawdown']:.2f}% | Profit Factor: {best_report['profit_factor']:.2f}")
        print(f"Novos Ajustes: {best_params}")
    else:
        print("\n--- CONCLUSÃO ---")
        print("Os parâmetros atuais já são os mais lucrativos e assertivos para o dia de hoje. Nenhuma melhoria absoluta foi validada.")

    # Salva os resultados para análise do assistente
    output = {
        "baseline": baseline_report,
        "optimized": best_report if best_params else None,
        "best_params": best_params,
        "date": "05-03-2026"
    }
    
    class CustomEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, 'isoformat'): return obj.isoformat()
            return super().default(obj)
            
    with open("backend/calibragem_05mar_resultado.json", "w") as f:
        json.dump(output, f, indent=4, cls=CustomEncoder)
        
    print(f"\n✅ Resultados salvos em backend/calibragem_05mar_resultado.json")

if __name__ == "__main__":
    asyncio.run(run_calibration())
