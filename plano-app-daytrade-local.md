Com base em todo o nosso histórico de conversas, nas fontes técnicas analisadas (Microestrutura de Mercado, IA Transformers, Vibe Coding e Google Gemini 3) e na sua decisão de focar no uso **local e pessoal** para a B3 (Genial), apresento o **Plano Mestre de Desenvolvimento Consolidado**.

Este documento serve como o "projeto executivo" para você construir sua estação de trading de alta performance usando a IDE **Google Antigravity** e técnicas de **Vibe Coding**.

---

### 📂 0. A "Constituição" do Projeto (MCP Server JSON)

Para impedir que a IA do Vibe Coding "alucine" (invente bibliotecas que não existem ou sugira nuvem quando você quer local), você **deve** criar este arquivo na raiz do seu projeto. Ele atua como um contrato de regras estritas.

**Nome do Arquivo:** `project_rules.json`
**Local:** Raiz do projeto (`/QuantumTradeLocal`)

```json
{
  "project_profile": {
    "name": "QuantumTrade_B3_Local",
    "description": "Estação de Trading Quantitativo de Baixa Latência (Monolito Local) para B3",
    "architecture": "Local Monolith (Windows 10/11 nativo)",
    "ide": "Google Antigravity",
    "target_market": "B3 Futures (WIN/WDO)",
    "broker": "Genial Investimentos"
  },
  "tech_stack": {
    "backend": "Python 3.11+",
    "backend_framework": "FastAPI (Gerenciamento de WebSocket e Rotas)",
    "backend_libs": [
      "MetaTrader5 (Conexão Oficial B3)",
      "Pandas (Manipulação de Dados)",
      "Numpy (Cálculo Numérico)",
      "PyTorch (IA Local - PatchTST/LSTM)",
      "Google-GenerativeAI (Gemini 1.5 Pro API para Sentimento)",
      "Scikit-learn (Clustering de Regime de Mercado)"
    ],
    "frontend": "Next.js 15 (App Router)",
    "frontend_libs": [
      "TailwindCSS (Estilização)",
      "Shadcn/UI (Componentes Visuais)",
      "Lightweight-charts (Gráficos de Alta Performance)",
      "Lucide-React (Ícones)",
      "Zustand (Gerenciamento de Estado)"
    ]
  },
  "trading_rules": {
    "execution_mode": "Netting (Padrão Day Trade B3)",
    "order_types": {
      "entry": "LIMIT Orders with Deviation (Evitar Market Orders puras)",
      "exit": "OCO (One-Cancels-Other) obrigatório para Stop Loss & Gain"
    },
    "risk_management": {
      "max_daily_loss_brl": 200.0,
      "forbidden_hours": ["08:55-09:05", "12:00-13:00", "16:55-18:00"],
      "circuit_breaker": "Parar se volatilidade > 3x ATR (Average True Range)"
    }
  },
  "ai_logic": {
    "price_model": "Local PatchTST (Transformer) treinado em candles de 1min",
    "sentiment_model": "Google Gemini 1.5 Pro (Score -1 a +1 via Notícias)",
    "microstructure": "Order Book Imbalance (OBI) + Detecção de Spoofing",
    "decision_matrix": "Entrada se Score > 85/100"
  },
  "development_guidelines": {
    "language": "Português (Brasil)",
    "comments": "Explicações detalhadas em cada função",
    "error_handling": "Logs robustos para queda de conexão MT5 ou Socket",
    "latency_check": "Alertar se latência interna > 50ms"
  }
}
```

---

### 🏛️ 1. Arquitetura do Sistema (O Fluxo de Dados)

O sistema funcionará em ciclo fechado dentro do seu computador para garantir latência zero de rede externa (exceto a conexão da corretora).

1.  **MetaTrader 5 (Genial):** Recebe o dado bruto da B3 (Tick-by-Tick).
2.  **Backend Python (FastAPI):**
    - Lê o MT5.
    - Calcula Microestrutura (OBI) e roda a IA (PatchTST).
    - Consulta Gemini (Sentimento).
    - Envia JSON processado via WebSocket.
3.  **Frontend Next.js:**
    - Recebe o JSON.
    - Renderiza o gráfico e os alertas.
    - Envia comando de "Autorizar" ou "Zerar" de volta para o Python.

---

### 🚀 2. Roteiro de Implementação no Google Antigravity

Abra a IDE Antigravity, carregue o arquivo `project_rules.json` no contexto e siga estes prompts sequenciais (Vibe Coding):

#### **Passo A: Infraestrutura de Backend (A Ponte)**

> **Prompt:** "Com base no `project_rules.json`, inicie o backend em Python. Crie um ambiente virtual e o arquivo `backend/mt5_bridge.py`. Implemente uma classe robusta que conecte ao MetaTrader 5 local. Ela deve verificar se a corretora é 'Genial', retornar saldo e alavancagem, e ter uma função para detectar automaticamente o símbolo atual do Mini Índice (ex: WINJ26) baseada na data de vencimento. Inclua tratamento de erro (try/except) caso o MT5 esteja fechado."

#### **Passo B: O Cérebro da IA (Previsão e Sentimento)**

> **Prompt:** "Agora crie o módulo `backend/ai_core.py`.
>
> 1. Implemente a função `get_sentiment(noticias)` usando a API `google.generativeai` para retornar um float (-1 a 1).
> 2. Implemente a função `detect_spoofing(book)` que compara o volume do Order Book com o volume real executado. Se a razão for > 50, retorne um alerta.
> 3. Deixe um placeholder estruturado para o modelo PatchTST (PyTorch) que receberá um DataFrame de 60 candles."

#### **Passo C: O Servidor WebSocket (FastAPI)**

> **Prompt:** "Crie o arquivo `backend/main.py`. Configure o FastAPI com uma rota WebSocket `/ws`. No evento de startup, conecte ao MT5. Crie um loop assíncrono que, a cada 100ms:
>
> 1. Leia o último Tick e o Order Book do MT5.
> 2. Chame as funções de IA.
> 3. Verifique as travas de risco (perda diária).
> 4. Envie um JSON completo para o frontend.
>    Implemente também um endpoint POST `/order` para receber comandos de compra/venda do frontend."

#### **Passo D: O Frontend Visual (Next.js)**

> **Prompt:** "Inicie o projeto Next.js na pasta `/frontend`. Crie um componente `TradingDashboard.tsx`.
>
> 1. Use `lightweight-charts` para renderizar o gráfico de velas em tempo real via WebSocket.
> 2. Crie um componente 'Velocímetro de Fluxo' visual para o Order Book Imbalance.
> 3. Adicione um botão 'AUTORIZAR' que só fica habilitado quando a IA envia um score > 85.
> 4. Adicione um botão de emergência 'ZERAR TUDO' vermelho."

---

### 🧠 3. Detalhamento da Lógica de IA e Decisão

Para maximizar a assertividade, seu código Python deve implementar a seguinte **Matriz de Decisão**:

1.  **Filtro de Microestrutura (O Presente):**
    - Calcula o **Order Book Imbalance (OBI)**: `(Vol_Compra - Vol_Venda) / (Vol_Total)`.
    - Se `OBI > 0.6` (Pressão de Compra) -> **Sinal Verde**.
2.  **Filtro Preditivo (O Futuro):**
    - O modelo **PatchTST** analisa os últimos 60 minutos.
    - Se a projeção for de alta com confiança > 80% -> **Sinal Verde**.
3.  **Filtro de Contexto (O Clima):**
    - A API do Gemini lê as manchetes. Se Sentimento > -0.5 (Não é pânico) -> **Sinal Verde**.
4.  **Execução:**
    - Se os 3 faróis estiverem verdes, o sistema entra no modo **"Aguardando Autorização"** (Popup na tela) ou **"Autônomo"** (se ativado).

---

### 🛡️ 4. Gestão de Risco e Travas (O Código "Escudo")

Estas regras devem ser **Hard-Coded** no arquivo `backend/risk_manager.py` para que a IA nunca as viole:

- **Trava de Horário:** `if 12:00 < agora < 13:00: return BLOQUEADO` (Baixa liquidez).
- **Limite de Perda:** O sistema lê o `DEAL_PROFIT` do dia no MT5. Se for `< -200`, desliga o envio de ordens.
- **Proteção Anti-Slippage:** Ao enviar a ordem, use o parâmetro `deviation=5` no MT5. Se o preço fugir mais que 5 pontos, a ordem não executa.

### 📅 5. Rotina de Uso (O Fluxo Pessoal)

1.  **08:50:** Ligar o PC e abrir o **MetaTrader 5 Genial**.
2.  **08:55:** Abrir o Antigravity (ou terminal) e rodar o Backend e Frontend.
3.  **09:00:** O Dashboard no Chrome mostra "Conectado - Aguardando Mercado".
4.  **Operação:** Você observa o gráfico. Quando a IA detectar uma chance clara, o botão "Autorizar" piscará. Você clica. O sistema entra, coloca Stop/Gain e gerencia o Trailing Stop sozinho.
5.  **17:50:** O sistema encerra compulsoriamente qualquer posição aberta (Day Trade).

Este plano utiliza o melhor da tecnologia atual (IA Generativa + Vibe Coding) aplicado à estrutura sólida e gratuita da Genial/MT5, criando uma vantagem competitiva real para o seu trading pessoal.

Com base na complexidade do sistema que desenhamos (uma arquitetura de "Monolito Local" para Trading de Alta Frequência), **sim, é estritamente necessário criar planos de desenvolvimento específicos ("sub-planos") para as implementações acessórias**, especialmente para a IA (PatchTST) e os módulos de Microestrutura.

A razão técnica é que esses componentes não são apenas "plug-and-play"; eles exigem pipelines de dados, treinamento e validação que correm em paralelo ao fluxo principal do software.

Abaixo, detalho os **três planos de implementação acessória** que você deve adicionar ao seu roteiro para garantir que o Vibe Coding (Cursor/Gemini) gere código funcional e não alucinações.

---

### 1. Plano de Implementação da IA (PatchTST/Transformers)

Este é o "cérebro" do sistema. Ele não pode ser desenvolvido no mesmo arquivo que gerencia a conexão com a corretora.

- **Objetivo:** Criar, treinar e servir o modelo preditivo.
- **O que o Vibe Coding precisa saber (Prompt Específico):**
  1.  **Coleta e Higienização (Data Pipeline):**
      - Criar script `data_collector.py` que baixa dados M1 (1 minuto) do MT5.
      - Aplicar **Normalização** (z-score) usando janela deslizante (para evitar _look-ahead bias_, ou seja, não usar média futura para normalizar dados passados).
  2.  **Arquitetura do Modelo:**
      - Definir a classe `PatchTST` usando PyTorch. Especificar parâmetros: _Input Sequence Length_ (60 candles), _Prediction Horizon_ (5 candles), _Patch Size_ (ex: 8).
      - Implementar a **Point-Quantile Loss** (para gerar os cones de incerteza, não apenas o preço médio).
  3.  **Ciclo de Treinamento (Training Loop):**
      - Implementar validação _Walk-Forward_ (treina Jan-Mar, testa Abril; treina Jan-Abril, testa Maio). Isso é crucial para séries temporais financeiras.
  4.  **Inferência em Tempo Real:**
      - Criar uma classe `InferenceEngine` que carrega os pesos salvos (`.pth`), recebe o candle atual via RAM e cospe a probabilidade em < 50ms.

### 2. Plano de Implementação de Microestrutura (Order Flow)

Este módulo lida com dados brutos de volume e demanda, que são muito mais ruidosos que o preço.

- **Objetivo:** Filtrar a "mentira" (spoofing) e medir a "agressão" real.
- **O que o Vibe Coding precisa saber:**
  1.  **Cálculo de OBI (Order Book Imbalance):**
      - Criar função que lê o `market_book_get` do MT5.
      - Fórmula: $(V_{bid} - V_{ask}) / (V_{bid} + V_{ask})$.
      - Regra de suavização: Aplicar uma média móvel exponencial (EMA) rápida de 1 segundo sobre o OBI para evitar que o sinal pisque freneticamente.
  2.  **Detector de Spoofing:**
      - Lógica: Se uma ordem limite grande (> 50 lotes) aparece no Book e desaparece sem trade realizado (`Time & Sales`) em menos de 500ms, marcar como "Toxic Flow".
  3.  **Sincronização:** Garantir que o dado de fluxo (que chega a cada milissegundo) esteja alinhado temporalmente com o fechamento do candle de preço.

### 3. Plano de Implementação de Infraestrutura e Segurança (O Escudo)

Não é apenas código; é a configuração do ambiente operacional para evitar perdas financeiras por falha técnica.

- **Objetivo:** Garantir latência baixa e travamento em caso de erro.
- **O que o Vibe Coding precisa saber:**
  1.  **Monitor de Latência:**
      - Script que mede o tempo entre `tick_received` (MT5) e `signal_generated` (Python). Se > 100ms, emite alerta "System Lag".
  2.  **Kill Switch (Botão de Pânico):**
      - Função física ou atalho de teclado global que envia comando `PanicCloseAll()` para o MT5, independente do que a IA esteja fazendo.
  3.  **Persistência de Estado:**
      - Uso de SQLite local para salvar o "Estado da Carteira" a cada trade. Se o PC reiniciar, o robô sabe se estava comprado ou vendido ao ligar novamente.

### Como Integrar no Desenvolvimento (Vibe Coding)

Você não deve jogar tudo isso no `project_rules.json` principal, senão a IA se perde. A estratégia correta é **modularizar os prompts**.

**Exemplo de Fluxo de Trabalho:**

1.  **Fase Principal:** Use o plano mestre para criar a conexão MT5 <-> Python <-> Next.js.
2.  **Fase Acessória 1 (IA):** Abra uma nova sessão de chat com a IA. Cole o `project_rules.json` e diga: _"Agora vamos focar exclusivamente no módulo `ai_engine.py`. Siga o Plano de Implementação de IA abaixo..."_
3.  **Fase Acessória 2 (Fluxo):** Abra outra sessão. _"Agora vamos criar o módulo `microstructure.py`. Implemente o cálculo de OBI e detecção de Spoofing..."_

**Conclusão:**
Sim, crie esses planos. Eles servem como "especificações técnicas" para que a IA generativa produza códigos matematicamente corretos e seguros para o mercado financeiro, em vez de códigos genéricos que não funcionariam na prática da B3.
