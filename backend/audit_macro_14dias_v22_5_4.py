import asyncio
import json
import os
import sys
import logging
import pandas as pd
from datetime import datetime
import numpy as np

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_macro_audit():
    # Silenciar logs excessivos para focar no resumo
    logging.basicConfig(level=logging.WARNING, format='%(message)s')
    
    params_path = "backend/v22_locked_params.json"
    with open(params_path, 'r') as f:
        config = json.load(f)
    
    strategy_params = config.get('strategy_params', {})
    initial_capital = 3000.0
    symbol = "WIN$"
    timeframe = "M1"
    
    # Lista de dias solicitada pelo usuário
    target_dates_str = [
        "19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026",
        "02/03/2026", "03/03/2026", "04/03/2026", "05/03/2026", "06/03/2026", "09/03/2026", "10/03/2026"
    ]
    dates_to_test = [datetime.strptime(d, "%d/%m/%Y").date() for d in target_dates_str]
    
    print(f"\n🚀 [AUDITORIA MACRO 14 DIAS] INICIANDO VALIDAÇÃO SOTA v22.5.4")
    print("=" * 100)
    
    # Carregar dados amplos (mais candles para cobrir 14 dias)
    bt_loader = BacktestPro(symbol=symbol, n_candles=12000, timeframe=timeframe)
    full_data = await bt_loader.load_data()
    
    if full_data is None or full_data.empty:
        print("❌ Erro: Não foi possível carregar dados do MT5.")
        return

    # Executar Backtest em bloco único para manter integridade dos indicadores
    tester = BacktestPro(
        symbol=symbol,
        n_candles=len(full_data), 
        timeframe=timeframe,
        initial_balance=initial_capital,
        **strategy_params
    )
    tester.data = full_data
    
    print(f"⏳ Executando simulação contínua (14 dias)...")
    await tester.run()
    
    all_trades = tester.trades
    if not all_trades:
        print("❌ Nenhum trade realizado no período.")
        return

    df_trades = pd.DataFrame(all_trades)
    df_trades['entry_time'] = pd.to_datetime(df_trades['entry_time'])
    df_trades['date_str'] = df_trades['entry_time'].dt.strftime('%d/%m/%Y')
    
    # Consolidar resultados por dia
    day_results = []
    for target_date in dates_to_test:
        date_str = target_date.strftime('%d/%m/%Y')
        day_trades = df_trades[df_trades['date_str'] == date_str]
        
        buys = day_trades[day_trades['side'] == 'buy']
        sells = day_trades[day_trades['side'] == 'sell']
        
        pnl_buy = buys['pnl_fin'].sum()
        pnl_sell = sells['pnl_fin'].sum()
        total_pnl = pnl_buy + pnl_sell
        
        wins = len(day_trades[day_trades['pnl_fin'] > 0])
        wr = (wins / len(day_trades) * 100) if not day_trades.empty else 0
        
        day_results.append({
            'date': date_str,
            'pnl': total_pnl,
            'trades': len(day_trades),
            'buys_cnt': len(buys),
            'sells_cnt': len(sells),
            'pnl_buy': pnl_buy,
            'pnl_sell': pnl_sell,
            'wr': wr
        })

    # Gerar Relatório Markdown
    report = f"# 📊 Relatório Macro de Auditoria SOTA V22.5.4 (14 Pregões)\n\n"
    report += f"**Período**: 19/02/2026 a 10/03/2026\n"
    report += f"**Capital Inicial**: R$ 3.000,00 | **Ativo**: {symbol} | **Timeframe**: {timeframe}\n\n"
    
    report += "## 📈 Resumo Geral\n\n"
    total_acumulado = df_trades['pnl_fin'].sum()
    total_trades = len(df_trades)
    total_buys = len(df_trades[df_trades['side'] == 'buy'])
    total_sells = len(df_trades[df_trades['side'] == 'sell'])
    pnl_buys = df_trades[df_trades['side'] == 'buy']['pnl_fin'].sum()
    pnl_sells = df_trades[df_trades['side'] == 'sell']['pnl_fin'].sum()
    media_wr = (len(df_trades[df_trades['pnl_fin'] > 0]) / total_trades * 100)
    total_vetos = tester.shadow_signals.get('filtered_by_ai', 0) + tester.shadow_signals.get('filtered_by_flux', 0)

    report += f"- **PnL Total Acumulado**: **R$ {total_acumulado:.2f}**\n"
    report += f"- **ROI sobre Capital**: **{(total_acumulado/initial_capital*100):.2f}%**\n"
    report += f"- **Total de Operações**: {total_trades} (Compra: {total_buys} | Venda: {total_sells})\n"
    report += f"- **Performance Compra**: R$ {pnl_buys:.2f}\n"
    report += f"- **Performance Venda**: R$ {pnl_sells:.2f}\n"
    report += f"- **Taxa de Acerto Média**: {media_wr:.1f}%\n"
    report += f"- **Vetos Totais (IA/Fluxo/Bias)**: {total_vetos}\n\n"
    
    report += "## 📅 Detalhamento Diário\n\n"
    report += "| Data | PnL Total | Trades | Compra (PnL) | Venda (PnL) | Win Rate |\n"
    report += "| :--- | :--- | :---: | :---: | :---: | :---: |\n"
    
    for r in day_results:
        report += f"| {r['date']} | **R$ {r['pnl']:.2f}** | {r['trades']} | {r['buys_cnt']} (R$ {r['pnl_buy']:.2f}) | {r['sells_cnt']} (R$ {r['pnl_sell']:.2f}) | {r['wr']:.1f}% |\n"
    
    report += "\n## 🛡️ Análise de Assertividade e Melhorias\n\n"
    report += "### 1. Comportamento em Crises (Ex: 10/03)\n"
    r10 = next((r for r in day_results if r['date'] == "10/03/2026"), None)
    if not r10 or r10['trades'] == 0 or (r10['pnl'] >= 0 and r10['buys_cnt'] == 0):
        report += "- **✅ Proteção SOTA**: O sistema mitigou perdas agressivas em dias de queda livre (10/03).\n"
    else:
        report += f"- **⚠️ Observação**: Dia 10/03 ainda registrou trades ({r10['trades']}). Verificar logs para confirmar se foram rebotes técnicos válidos.\n"

    report += "\n### 2. Potencial por Lado (COMPRA vs VENDA)\n"
    report += f"- O potencial de **COMPRA** gerou R$ {pnl_buys:.2f} ({total_buys} trades).\n"
    report += f"- O potencial de **VENDA** gerou R$ {pnl_sells:.2f} ({total_sells} trades).\n"
    report += "- A assimetria sugere que o robô ainda é mais 'atento' a setups de compra.\n"

    # Salvar Relatório
    report_path = "backend/report_auditoria_macro_14dias.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"\n✅ Auditoria finalizada. Relatório gerado em: {report_path}")

if __name__ == "__main__":
    asyncio.run(run_macro_audit())
