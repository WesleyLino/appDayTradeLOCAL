# 📊 Relatório de Auditoria SOTA V22.5.2: 06/03, 09/03 e 10/03
**Ativo**: WIN$ | **Capital Inicial**: R$ 3000.00

### 📈 Resumo de Performance

| Data | PnL Total | Trades | Compra (PnL) | Venda (PnL) | Win Rate | Oport. Perdidas (IA/Flux) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 06/03/2026 | **R$ 121.00** | 6 | 6 (R$ 121.00) | 0 (R$ 0.00) | 83.3% | 8 / 0 |
| 09/03/2026 | **R$ 55.00** | 8 | 7 (R$ 52.00) | 1 (R$ 3.00) | 87.5% | 17 / 0 |
| 10/03/2026 | **R$ -61.00** | 6 | 6 (R$ -61.00) | 0 (R$ 0.00) | 50.0% | 17 / 0 |

## 🏆 Resultado Acumulado (3 dias): R$ 115.00

## 🔍 Análise Detalhada e Shadow Mode

### 📅 Pregão: 06/03/2026
- **Resultado**: R$ 121.00 (Compras: R$ 121.00 | Vendas: R$ 0.00)
- **Trades Totais**: 6 (6C / 0V)
- **Shadow Mode (Vetos)**:
  - Filtros de IA (SOTA): 8 oportunidades vetadas por baixa confiança.
  - Filtros de Fluxo: 0 oportunidades vetadas por falta de agressão.
- **Oportunidades Perdidas**: A IA vetou 8 entradas. Analisar se o relaxamento da V22.5.2 (RSI 38/62) teria capturado esses movimentos.
---
### 📅 Pregão: 09/03/2026
- **Resultado**: R$ 55.00 (Compras: R$ 52.00 | Vendas: R$ 3.00)
- **Trades Totais**: 8 (7C / 1V)
- **Shadow Mode (Vetos)**:
  - Filtros de IA (SOTA): 17 oportunidades vetadas por baixa confiança.
  - Filtros de Fluxo: 0 oportunidades vetadas por falta de agressão.
- **Oportunidades Perdidas**: A IA vetou 17 entradas. Analisar se o relaxamento da V22.5.2 (RSI 38/62) teria capturado esses movimentos.
---
### 📅 Pregão: 10/03/2026
- **Resultado**: R$ -61.00 (Compras: R$ -61.00 | Vendas: R$ 0.00)
- **Trades Totais**: 6 (6C / 0V)
- **Shadow Mode (Vetos)**:
  - Filtros de IA (SOTA): 17 oportunidades vetadas por baixa confiança.
  - Filtros de Fluxo: 0 oportunidades vetadas por falta de agressão.
- **Alerta de Perda**: O dia resultou em prejuízo. Verificar se o drawdown máximo foi respeitado e se houve falha no Trailing Stop.
- **Oportunidades Perdidas**: A IA vetou 17 entradas. Analisar se o relaxamento da V22.5.2 (RSI 38/62) teria capturado esses movimentos.
---

## 🚀 Sugestões para Elevar a Assertividade
1. **Calibragem de Fluxo**: Se as oportunidades perdidas por fluxo forem altas em dias de tendência, considerar reduzir o `flux_imbalance_threshold` para 1.02.
2. **Regime Macro**: Ativar o `Trend Bias` para travar operações contra a tendência primária do dia (Baseado no H1).
3. **Ajuste de Lote**: Em dias de alta performance (WR > 70%), aumentar o multiplicador de lote dinâmico para maximizar o ganho exponencial.
