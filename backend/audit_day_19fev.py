import asyncio
import json
import os
import sys
import logging
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Redirecionar stdout para arquivo de log
_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'backend', 'audit_19fev_result.txt')
_fout = open(_LOG_FILE, 'w', encoding='utf-8')
class _Tee:
    def write(self, msg):
        sys.__stdout__.write(msg)
        _fout.write(msg)
    def flush(self):
        sys.__stdout__.flush()
        _fout.flush()
sys.stdout = _Tee()

from backend.backtest_pro import BacktestPro

# Data alvo do raio-x
TARGET_DATE = date(2026, 2, 19)

async def run_audit():
    logging.basicConfig(level=logging.ERROR, format='%(message)s')

    # Carregar parâmetros campeões de produção
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']

    # Config fixa: capital 3k, 3 lotes, modo produção
    initial_capital = 3000.0
    params['force_lots'] = 3
    params['dynamic_lot'] = False
    params['aggressive_mode'] = True  # fluxo 1.2x
    params['use_trailing_stop'] = True

    print("\n" + "="*90)
    print(f"  RAIO-X DE PRODUCAO: WIN$ | {TARGET_DATE.strftime('%d/%m/%Y')} | CAPITAL: R$ {initial_capital:.2f}")
    print(f"  Trailing: {params['trailing_trigger']}pts | BE: {params['be_trigger']}pts | Flux: {params['vol_spike_mult']}x")
    print("="*90 + "\n")

    # Buscar historico suficiente para conter o dia alvo + padding
    # ~5 dias de candles M1 (5*510 = 2550) eh mais que suficiente para o dia 19/02
    bt_loader = BacktestPro(symbol="WIN$", n_candles=3000, timeframe="M1")
    print("Sincronizando dados do MetaTrader 5 (pode levar alguns segundos)...")
    df = await bt_loader.load_data()

    if df is None or df.empty:
        print("ERRO: Falha ao obter dados do MT5. Verifique se o terminal esta aberto.")
        return

    df['date'] = df.index.date
    available_days = sorted(df['date'].unique())
    print(f"Periodo disponivel: {available_days[0]} ate {available_days[-1]}")

    if TARGET_DATE not in available_days:
        print(f"AVISO: Dia {TARGET_DATE} nao encontrado. Dias disponiveis: {available_days}")
        print("Verifique se 19/02/2026 foi um dia util com dados no MT5.")
        return

    # Filtrar apenas o dia alvo + 100 candles de padding anterior (para indicadores)
    day_data_idx = list(df.index.date).index(TARGET_DATE)
    start_idx = max(0, day_data_idx - 100)
    target_rows = df[df['date'] == TARGET_DATE]
    end_idx = df.index.get_loc(target_rows.index[-1]) + 1
    day_chunk = df.iloc[start_idx:end_idx].copy()

    print(f"\nDia analisado : {TARGET_DATE.strftime('%d/%m/%Y')}")
    print(f"Candles M1    : {len(target_rows)} candles do dia ({len(day_chunk)} com padding)")
    print("Rodando simulacao...\n")

    # Executar backtest no dia alvo
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=len(day_chunk),
        timeframe="M1",
        initial_balance=initial_capital,
        **params
    )
    bt.df = day_chunk
    async def _mock_load(): return day_chunk
    bt.load_data = _mock_load

    report = await bt.run()

    if not report:
        print("ERRO: Falha na geracao do relatorio.")
        return

    # ============================
    # RESULTADOS FINANCEIROS
    # ============================
    trades = report.get('trades', [])
    wins   = [t for t in trades if t['pnl_fin'] > 0]
    losses = [t for t in trades if t['pnl_fin'] < 0]
    total_pnl = sum(t['pnl_fin'] for t in trades)
    wr     = (len(wins) / len(trades)) * 100 if trades else 0
    max_dd = report.get('max_drawdown', 0)

    avg_win  = sum(t['pnl_fin'] for t in wins)  / max(len(wins),  1)
    avg_loss = sum(t['pnl_fin'] for t in losses) / max(len(losses), 1)
    pf = abs(sum(t['pnl_fin'] for t in wins) / sum(t['pnl_fin'] for t in losses)) if losses else float('inf')

    print("-"*90)
    print("RESULTADO FINANCEIRO")
    print(f"  Saldo Inicial    : R$ {initial_capital:.2f}")
    print(f"  Lucro/Prejuizo   : R$ {total_pnl:+.2f}  ({'+' if total_pnl>=0 else ''}{(total_pnl/initial_capital)*100:.2f}%)")
    print(f"  Saldo Final      : R$ {initial_capital + total_pnl:.2f}")
    print(f"  Drawdown Max     : {max_dd:.2f}%")
    print(f"  Profit Factor    : {pf:.2f}")
    print("-"*90)

    # ============================
    # BREAKDOWN DE TRADES
    # ============================
    print("\nBREAKDOWN DE TRADES")
    print(f"  Total de Trades  : {len(trades)}")
    print(f"  Vitorias         : {len(wins)} ({wr:.1f}%)")
    print(f"  Derrotas         : {len(losses)} ({100-wr:.1f}%)")
    print(f"  Ganho Medio Win  : R$ {avg_win:+.2f}")
    print(f"  Perda Media Loss : R$ {avg_loss:+.2f}")
    print()

    if trades:
        print(f"  {'#':<3} {'HORA':<8} {'DIRECAO':<7} {'ENTRY':<9} {'EXIT':<9} {'PNL':>10}  STATUS")
        print(f"  {'-'*70}")
        for i, t in enumerate(trades, 1):
            hora = str(t.get('entry_time', ''))[-8:-3] if t.get('entry_time') else '--:--'
            direc = t.get('direction', '?').upper()
            entry = t.get('entry_price', 0)
            ext   = t.get('exit_price', 0)
            pnl   = t['pnl_fin']
            status = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
            print(f"  {i:<3} {hora:<8} {direc:<7} {entry:<9.0f} {ext:<9.0f} R$ {pnl:>8.2f}  {status}")

    # ============================
    # OPORTUNIDADES PERDIDAS
    # ============================
    shadow = report.get('shadow_signals', {'filtered_by_ai': 0, 'filtered_by_flux': 0})
    total_shadow = shadow['filtered_by_ai'] + shadow['filtered_by_flux']

    print()
    print("-"*90)
    print("OPORTUNIDADES PERDIDAS (Shadow Signals)")
    print(f"  Bloqueadas por IA  (Score < 85%) : {shadow['filtered_by_ai']}")
    print(f"  Bloqueadas por FLUX (vol < 1.2x) : {shadow['filtered_by_flux']}")
    print(f"  TOTAL ignorado                   : {total_shadow}")

    # Receita potencial se tudo tivesse a taxa de acerto atual
    if total_shadow > 0 and len(trades) > 0:
        avg_pnl_trade = total_pnl / len(trades)
        potential_extra = total_shadow * avg_pnl_trade * (wr / 100)
        print(f"  Potencial nao capturado (estim.) : R$ {potential_extra:+.2f}")

    # ============================
    # DIAGNOSTICO E MELHORIAS
    # ============================
    print()
    print("-"*90)
    print("DIAGNOSTICO E SUGESTOES DE MELHORIA")

    if total_pnl > 0:
        print("  RESULTADO: DIA LUCRATIVO com as configuracoes de producao!")
    elif total_pnl == 0:
        print("  RESULTADO: Capital preservado (breakeven). Filtros funcionaram.")
    else:
        print(f"  RESULTADO: Dia de perda (R$ {total_pnl:.2f}). Analise as derrotas abaixo.")

    # Sugestao 1: Score da IA
    if shadow['filtered_by_ai'] > 5:
        print()
        print("  [1] Muitos sinais bloqueados pela IA (>5).")
        print("      Sugestao: Testar threshold de 0.80 no confidence_threshold.")
        print("      Risco: Mais trades, porem win rate potencialmente menor.")
    elif shadow['filtered_by_ai'] <= 2:
        print()
        print("  [1] IA com filtragem eficiente (<= 2 sinais bloqueados).")
        print("      Manter threshold em 0.85 por ora.")

    # Sugestao 2: Filtro de fluxo
    if shadow['filtered_by_flux'] > 5:
        print()
        print("  [2] Filtro de Fluxo bloqueou muitos sinais (>5).")
        print("      Sugestao: Testar vol_spike_mult = 1.0 em modo tendencia.")
    elif shadow['filtered_by_flux'] == 0:
        print()
        print("  [2] Filtro de Fluxo (1.2x): Dia de alta volatilidade. Captura totalmente eficiente.")

    # Sugestao 3: Trailing Stop
    if losses:
        print()
        print("  [3] Existem operacoes perdedoras.")
        print("      Avaliar se o Trailing Trigger de 70pts protegeu o pior cenario.")
        print("      Se nao, considerar BE mais rapido (40pts).")
    else:
        print()
        print("  [3] Trailing Stop de 70pts: Zero perdas. Configuracao IDEAL para este regime.")

    # Sugestao 4: Frequencia
    if len(trades) < 3:
        print()
        print("  [4] Baixa frequencia de trades (<3 no dia).")
        print("      Expandir janela de operacao: testar inicio as 09:15.")
    
    print()
    print("="*90)
    print("Auditoria concluida.")
    print("="*90 + "\n")

if __name__ == "__main__":
    asyncio.run(run_audit())
    _fout.close()
    sys.stdout = sys.__stdout__
    print(f"\nLog salvo em: {_LOG_FILE}")
