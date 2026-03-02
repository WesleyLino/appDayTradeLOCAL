# Fluxo Operacional QuantumTrade SOTA v25 (Grau de Perfeição)

Este documento detalha o percurso completo da inteligência e execução do sistema, desde a captura de milissegundos até a liquidação da ordem.

---

## 1. Fase de Ingestão e Processamento (Inputs)

O sistema opera em um modelo de **8 Canais de Dados Sincronizados**, garantindo que a IA não tome decisões baseada apenas em preço, mas na intenção real do mercado.

- **Canais Centrais**: OHLCV (Abertura, Máxima, Mínima, Fechamento, Volume).
- **Canais de Microestrutura**:
  - **CVD (Cumulative Volume Delta)**: Mede a agressão líquida (compradores vs vendedores agredindo o book).
  - **OFI (Order Flow Imbalance)**: Mede a pressão de ordens limitadas no Book de Ofertas.
  - **Volume Ratio**: Relação de volume atual versus média histórica para detectar anomalias.

---

## 2. Camadas de Análise (A Inteligência)

### A. Análise de Sentimento e Notícias (Macro)

- **NewsSentimentWorker**: Um worker em background monitora manchetes financeiras via IA (Gemini).
- **Suavização (EMA)**: O sentimento não é reativo ao ruído; ele é processado através de uma média móvel exponencial de 60 minutos para identificar a tendência macro do dia.
- **Lock Macro**: Se o sentimento for fortemente baixista, o sistema trava compras (Lock Bull) para evitar ir contra o "humor" do mercado mundial.

### B. Correlação Inter-Mercados e Blue Chips

- **WDO vs WIN**: O sistema monitora o Dólar (WDO) simultaneamente. Movimentos explosivos no Dólar vetam operações no Índice (WIN) para evitar arbitragens negativas.
- **S&P500 & Petrovale**: Dados do índice americano e das principais ações brasileiras (Blue Chips) alimentam o score macro.

### C. Identificação de Regimes (KMeans)

- O sistema classifica o mercado em 3 estados:
  1. **Consolidação (Lateral)**: Alvos curtos e filtros de reversão à média agressivos.
  2. **Tendência**: Alvos expandidos para maximizar lucro.
  3. **Ruído (Alta Vol)**: O sistema entra em modo conservador ou trava a operação.

---

## 3. Suite de Filtros e Travas (O Escudo)

Antes de uma ordem ser enviada, ela deve passar por 7 "Gates" de segurança:

1. **Veto de Incerteza (IA)**: Se o modelo PatchTST reportar uma incerteza relativa > 30%, a operação é descartada.
2. **Veto de Divergência**: Se a IA diz "Compra", mas o CVD (fluxo) mostra que os grandes players estão vendendo, a operação é bloqueada por divergência.
3. **Mean Reversion Guard**: Impede "comprar topo" ou "vender fundo". Se o preço estiver esticado > 1.5 ATR da média de 20 períodos, o sistema aguarda retração.
4. **Anti-Violinada (Defensive Math)**: As ordens não são colocadas em números redondos (onde há acúmulo de robôs de HFT). O sistema desloca o Stop 15 pontos (WIN) ou 0.5 pontos (WDO) para longe das zonas de "caça".
5. **Veto de Calendário**: 3 minutos antes e depois de notícias críticas (EUA/Brasil), o sistema entra em hiato para evitar volatilidade irracional.
6. **Settlement Trap (Preço de Ajuste)**: O preço de ajuste da B3 é tratado como uma muralha de liquidez. O sistema evita abrir ordens coladas ao ajuste.
7. **Score de Convicção (0-100)**: Apenas scores > 75 (com pesos em Sentimento, OBI e PatchTST) geram execução.

---

## 4. Execução e Gestão de Posição (Operação)

### Compra (Long) / Venda (Short)

- **Ordem Limit OCO**: O sistema entra via Ordem Limite (reduzindo custo de corretagem) com ordens de Stop (SL) e Take Profit (TP) já anexadas.
- **Lote Probabilístico**: O tamanho da mão é ajustado conforme a confiança (70% confiança = lote mínimo; >85% confiança = lote cheio).

### Defesas em Tempo Real

- **Breakeven**: Quando a operação atinge 50 pontos de lucro, o SL é movido para o preço de entrada (risco zero).
- **Trailing Stop**: Se o gain continuar, o lucro é "travado" subindo o stop conforme o preço avança.
- **Saídas Parciais**: O sistema realiza a parcial de 50% da mão no primeiro alvo para garantir caixa.
- **Velocity Limit**: Se a operação fica "amarrada" negativamente por muito tempo, o sistema aborta o trade (Stop por tempo) para liberar margem.

---

## 5. Limites de Sobrevivência (Kill Switch)

- **Max Daily Loss**: Se o lucro total do dia (realizado + flutuante) atingir o limite negativo (ex: R$ 600), o sistema encerra tudo e desliga o bot (Trava de Segurança Master).
- **Horário de Pânico**: Às 17:50, todas as posições são encerradas compulsoriamente para evitar o pós-market.

---

> [!IMPORTANT]
> A lógica é desenhada para proteger o capital primeiro. Lucros são consequência de uma filtragem severa de cenário.
