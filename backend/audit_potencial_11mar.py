import asyncio
import pandas as pd
import numpy as np
import logging
import os
import sys
from datetime import datetime

# Configuração de path para backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.backtest_pro import BacktestPro

async def auditoria_11mar():
    """
    Analisa o potencial de ganho do dia 11/03/2026.
    Focado em separar COMPRA/VENDA e identificar melhorias.
    """
    print("🔎 Iniciando Auditoria de Alta Performance - 11/03/2026")
    
    # Configuração do Backtest focado em HOJE
    bt = BacktestPro(symbol="WIN$", n_candles=2000, initial_balance=3000.0, use_ai_core=True)
    all_data = await bt.load_data()
    
    # Filtro para o dia 11/03
    today = "2026-03-11"
    data_hoje = all_data[all_data.index.strftime('%Y-%m-%d') == today].copy()
    
    if data_hoje.empty:
        print(f"❌ Nenhum dado encontrado para {today}. Verifique a coleta.")
        return

    bt.data = data_hoje
    
    # MODO AUDITORIA: Desativa travas para ver o potencial bruto
    bt.opt_params['confidence_threshold'] = 0.45 # Ligeiramente relaxado
    bt.opt_params['daily_trade_limit'] = 100
    bt.opt_params['rsi_period'] = 9
    bt.opt_params['audit_mode'] = True
    
    # Execução
    await bt.run()
    
    # Processamento de Resultados
    trades = pd.DataFrame(bt.trades)
    
    def extrair_metricas(df_ponta):
        if df_ponta.empty:
            return 0, 0.0, 0.0
        qtd = len(df_ponta)
        lucro = df_ponta['pnl_fin'].sum()
        assertiv = (len(df_ponta[df_ponta['pnl_fin'] > 0]) / qtd) * 100
        return qtd, lucro, assertiv

    buys = trades[trades['side'] == 'buy'] if not trades.empty else pd.DataFrame()
    sells = trades[trades['side'] == 'sell'] if not trades.empty else pd.DataFrame()
    
    q_b, l_b, a_b = extrair_metricas(buys)
    q_s, l_s, a_s = extrair_metricas(sells)
    
    # Relatório Final em PT-BR
    report = f"""# Relatório de Alta Performance - 11/03/2026

## 📈 1. Performance por Operação (Executado em Auditoria)
Foco: SNIPER RSI 18/82 | 3 Lotes

| Operação | Qtd Trades | Lucro/Prejuízo (R$) | Assertividade |
| :--- | :---: | :---: | :---: |
| **COMPRA** | {q_b} | R$ {l_b:.2f} | {a_b:.1f}% |
| **VENDA** | {q_s} | R$ {l_s:.2f} | {a_s:.1f}% |
| **TOTAL** | {q_b + q_s} | R$ {l_b + l_s:.2f} | {( (a_b*q_b + a_s*q_s) / (q_b+q_s) if (q_b+q_s) > 0 else 0):.1f}% |

## 🕵️ 2. Oportunidades e Perdas (Shadow Trading)
- **Sinais Brutos Gerados:** {bt.shadow_signals.get('v22_candidates', 0)}
- **Vetos por Volatilidade:** {bt.shadow_signals.get('filtered_by_vol_low', 0)}
- **Vetos por Tendência H1:** {bt.shadow_signals.get('filtered_by_bias', 0)}
- **Vetos da IA (Incerteza):** {bt.shadow_signals.get('buy_vetos_ai', 0) + bt.shadow_signals.get('sell_vetos_ai', 0)}

## 🚀 3. Calibragem e Melhorias
1. **Ponta Dominante:** {"Compra" if l_b > l_s else "Venda"} foi mais lucrativa hoje.
2. **Perdas de Oportunidade:** Identificados {bt.shadow_signals.get('v22_candidates', 0) - (q_b + q_s)} sinais que poderiam ser capturados com relaxamento controlado do filtro de Bias H1.
3. **Melhoria Absoluta:** Ajustar o `confidence_threshold` para 0.52 em vez de 0.55 nas operações de VENDA para aproveitar o bias de baixa do IBOV.

---
*Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*
"""

    report_path = "backend/relatorio_alta_performance_11mar.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"✅ Auditoria 11/03 finalizada. Relatório em: {report_path}")
    print(f"PnL Total Hoje: R$ {l_b + l_s:.2f}")

if __name__ == "__main__":
    asyncio.run(auditoria_11mar())
