"""
Validação de Melhorias: BE=40pts + Janela 09:15
vs. Configuração Atual: BE=50pts + Janela padrão
Dia referência: 19/02/2026 | Capital: R$ 3.000 | WIN$ M1
"""
import asyncio
import json
import os
import sys
import logging
from datetime import date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

TARGET_DATE = date(2026, 2, 20)

_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'backend', 'audit_20fev_v2_result.txt')
_fout = open(_LOG_FILE, 'w', encoding='utf-8')
class _Tee:
    def write(self, msg):
        sys.__stdout__.write(msg)
        _fout.write(msg)
    def flush(self):
        sys.__stdout__.flush()
        _fout.flush()
sys.stdout = _Tee()


async def _run_scenario(day_chunk: object, capital: float, label: str, **params) -> dict:
    """Executa um cenário de backtest e retorna métricas consolidadas."""
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=len(day_chunk),
        timeframe="M1",
        initial_balance=capital,
        **params
    )
    bt.df = day_chunk
    async def _mock(): return day_chunk
    bt.load_data = _mock
    report = await bt.run()
    if not report:
        return {}
    trades = report.get('trades', [])
    wins   = [t for t in trades if t['pnl_fin'] > 0]
    losses = [t for t in trades if t['pnl_fin'] < 0]
    total  = sum(t['pnl_fin'] for t in trades)
    wr     = (len(wins) / len(trades)) * 100 if trades else 0
    pf     = abs(sum(t['pnl_fin'] for t in wins) / sum(t['pnl_fin'] for t in losses)) if losses else float('inf')
    shadow = report.get('shadow_signals', {'filtered_by_ai': 0, 'filtered_by_flux': 0})
    return {
        'label':      label,
        'pnl':        total,
        'trades':     len(trades),
        'wins':       len(wins),
        'losses':     len(losses),
        'wr':         wr,
        'pf':         pf,
        'max_dd':     report.get('max_drawdown', 0),
        'shadow_ai':  shadow['filtered_by_ai'],
        'shadow_flux':shadow['filtered_by_flux'],
        'trade_list': trades,
    }


def _print_detail(r: dict):
    if not r:
        return
    print(f"\n{'='*90}")
    print(f"  CENARIO: {r['label']}")
    print(f"{'='*90}")
    print(f"  P&L Total   : R$ {r['pnl']:+.2f}  |  Win Rate: {r['wr']:.1f}%  ({r['wins']}V/{r['losses']}D)")
    print(f"  Drawdown    : {r['max_dd']:.2f}%  |  Profit Factor: {r['pf']:.2f}")
    print(f"  Shadow AI   : {r['shadow_ai']} sinais  |  Shadow FLUX: {r['shadow_flux']} sinais")
    if r['trade_list']:
        print(f"\n  {'#':<3} {'HORA':<8} {'PNL':>10}  STATUS")
        print(f"  {'-'*35}")
        for i, t in enumerate(r['trade_list'], 1):
            hora = str(t.get('entry_time', ''))[-8:-3] if t.get('entry_time') else '--:--'
            pnl  = t['pnl_fin']
            st   = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
            print(f"  {i:<3} {hora:<8} R$ {pnl:>8.2f}  {st}")


def _print_comparison(a: dict, b: dict):
    """Tabela comparativa lado a lado."""
    print("\n\n" + "="*90)
    print("  COMPARATIVO: CONFIGURACAO ATUAL  vs.  MELHORIAS PROPOSTAS")
    print("="*90)
    fmt = "  {:<28} {:>20} {:>20}"
    print(fmt.format("Metrica", "ATUAL (BE=50 / 09:20)", "MELHORIA (BE=40 / 09:15)"))
    print("  " + "-"*86)
    def diff(new, old, pct=False):
        d = new - old
        sign = "+" if d >= 0 else ""
        if pct:
            return f"({sign}{d:.1f}%)"
        return f"({sign}R$ {d:.2f})"
    print(fmt.format("Lucro/Prejuizo", f"R$ {a['pnl']:+.2f}", f"R$ {b['pnl']:+.2f}  {diff(b['pnl'], a['pnl'])}"))
    print(fmt.format("Trades Executados", str(a['trades']), str(b['trades'])))
    print(fmt.format("Win Rate", f"{a['wr']:.1f}%", f"{b['wr']:.1f}%  {diff(b['wr'], a['wr'], pct=True)}"))
    print(fmt.format("Drawdown Max", f"{a['max_dd']:.2f}%", f"{b['max_dd']:.2f}%  {diff(b['max_dd'], a['max_dd'], pct=True)}"))
    print(fmt.format("Profit Factor", f"{a['pf']:.2f}", f"{b['pf']:.2f}"))
    print(fmt.format("Shadow IA", str(a['shadow_ai']), str(b['shadow_ai'])))
    print(fmt.format("Shadow FLUX", str(a['shadow_flux']), str(b['shadow_flux'])))
    print("  " + "-"*86)
    if b['pnl'] > a['pnl']:
        print("  VEREDITO: MELHORIAS PROPOSTAS sao SUPERIORES para este dia.")
    elif b['pnl'] < a['pnl']:
        print("  VEREDITO: Configuracao ATUAL foi superior neste dia.")
    else:
        print("  VEREDITO: EMPATE. Ambas configuracoes produziram o mesmo resultado.")
    print("="*90)


async def run_validation():
    logging.basicConfig(level=logging.ERROR, format='%(message)s')

    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    with open(params_path, 'r') as f:
        config = json.load(f)
    base_params = dict(config['params'])

    # Parâmetros fixos para ambos
    base_params['force_lots'] = 3
    base_params['dynamic_lot'] = False
    base_params['aggressive_mode'] = True
    base_params['use_trailing_stop'] = True
    initial_capital = 3000.0

    print("\n" + "="*90)
    print(f"  RAIO-X COMPARATIVO: WIN$ | {TARGET_DATE.strftime('%d/%m/%Y')} | R$ {initial_capital:.2f}")
    print(f"  Trailing: {base_params['trailing_trigger']}pts | Flux: {base_params['vol_spike_mult']}x")
    print("  Cenario A (Atual)   : BE=50pts, Janela=padrao (sem alteracao)")
    print("  Cenario B (Melhoria): BE=40pts, Janela iniciando 09:15")
    print("="*90 + "\n")

    # Carregar dados do MT5
    bt_loader = BacktestPro(symbol="WIN$", n_candles=3000, timeframe="M1")
    print("Sincronizando dados do MetaTrader 5...")
    df = await bt_loader.load_data()

    if df is None or df.empty:
        print("ERRO: Falha ao obter dados do MT5.")
        return

    df['date'] = df.index.date
    available = sorted(df['date'].unique())
    print(f"Periodo disponivel: {available[0]} ate {available[-1]}")

    if TARGET_DATE not in available:
        print(f"AVISO: Dia {TARGET_DATE} nao encontrado. Dias disponíveis: {available}")
        return

    # Montar day_chunk com padding de 100 candles
    all_dates_list = list(df.index.date)
    first_idx_of_day = next(i for i, d in enumerate(all_dates_list) if d == TARGET_DATE)
    start_idx = max(0, first_idx_of_day - 100)
    target_rows = df[df['date'] == TARGET_DATE]
    end_idx = df.index.get_loc(target_rows.index[-1]) + 1
    day_chunk = df.iloc[start_idx:end_idx].copy()

    print(f"\nDia: {TARGET_DATE.strftime('%d/%m/%Y')} | {len(target_rows)} candles + 100 de padding")
    print("Rodando 2 cenarios...\n")

    # CENÁRIO A - Configuração atual de produção
    params_a = dict(base_params)
    params_a['be_trigger'] = 50.0
    # start_time não alterado — usa o default do BacktestPro
    result_a = await _run_scenario(day_chunk, initial_capital, "A: ATUAL (BE=50)", **params_a)
    _print_detail(result_a)

    # CENÁRIO B - Melhorias propostas
    params_b = dict(base_params)
    params_b['be_trigger'] = 40.0
    params_b['start_time'] = "09:15"  # janela expandida
    result_b = await _run_scenario(day_chunk, initial_capital, "B: MELHORIA (BE=40 + 09:15)", **params_b)
    _print_detail(result_b)

    # Comparativo final
    _print_comparison(result_a, result_b)

    # Diagnóstico final
    print("\nDIAGNOSTICO FINAL")
    gained_a = result_a.get('pnl', 0)
    gained_b = result_b.get('pnl', 0)
    extra_trades = result_b.get('trades', 0) - result_a.get('trades', 0)

    if extra_trades > 0:
        print(f"  A janela 09:15 gerou {extra_trades} trade(s) a mais na manha.")
    if gained_b > gained_a:
        print(f"  BE=40pts protegeu melhor o capital: +R$ {gained_b - gained_a:.2f} vs atual.")
    elif gained_b <= gained_a:
        print("  Neste dia, o BE=50pts foi mais permissivo e capturou mais ganho.")
        print("  Sugestao: Manter BE=50 por enquanto. Testar BE=40 em mais dias antes de alterar producao.")

    print()
    print("="*90)
    print("Auditoria concluida.")
    print("="*90 + "\n")


if __name__ == "__main__":
    asyncio.run(run_validation())
    _fout.close()
    sys.stdout = sys.__stdout__
    print(f"Log salvo em: {_LOG_FILE}")
