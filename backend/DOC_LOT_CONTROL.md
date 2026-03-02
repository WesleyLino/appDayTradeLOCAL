# Documentação Técnica: Controle de Lotes HFT (V22/V23)

Este documento descreve a lógica de dimensionamento e controle de lotes integrada no ecossistema de alta frequência, abrangendo tanto o **Modo Sniper (Manual/Direcional)** quanto o **Modo Autônomo (SOTA/Quant)**.

---

## 1. Escalonamento por Convicção (Modo Sniper)

A convicção é determinada pela assimetria e incerteza das bandas de previsão (Quantis Q10, Q50, Q90) do modelo PatchTST.

### Hierarquia de Lotes (Default: Mini Índice WIN)

- **NORMAL**: **1 Contrato**  
  _Critério_: Sinal padrão com confiança balanceada e incerteza dentro dos limites base.
- **HIGH (Alta Convicção)**: **2 Contratos**  
  _Critério_: Banda assimétrica (Q10/Q90) superior a 5 pontos ou incerteza significativamente reduzida.
- **VERY_HIGH (Convicção Extrema)**: **3 Contratos**  
  _Critério_: Banda assimétrica superior a 20% do range médio ou alta convergência entre sentimento e fluxo institucional.

> [!NOTE]
> Esta lógica está implementada no arquivo `backend/bot_sniper_win.py` dentro do método `execute_trade`.

---

## 2. Dimensionamento por Volatilidade (Modo Autônomo / SOTA)

Utilizado pelo motor de execução em tempo real (`main.py`) para ajustar a exposição ao risco de mercado atual.

### Fórmula SOTA

Os lotes são calculados dinamicamente com base no capital disponível e na volatilidade (ATR):

$$Lotes = \frac{Saldo \times Risco\%}{ATR \times ValorDoPonto}$$

- **Saldo**: Saldo atual da conta MT5.
- **Risco/Sinal**: Fração do risco diário permitida por trade (ajustada pelo multiplicador de sinal da IA).
- **ATR (Average True Range)**: Média da volatilidade real dos últimos 28 períodos (M1).
- **Valor do Ponto**: WIN = R$ 0,20 | WDO = R$ 10,00.

---

## 3. Travas de Segurança e Arredondamento

Para garantir a execução HFT e a conformidade com as regras da B3:

- **Volume Mínimo**: Sempre respeita o lote mínimo do ativo (1 contrato para WIN/WDO).
- **Arredondamento HFT**: Lotes calculados são arredondados para baixo (Floor) para evitar sobre-alavancagem acidental.
- **Multiplicador de Exposição**: A IA aplica um multiplicador final ($0.25x$ a $4.0x$) baseado na clareza do sinal, permitindo reduzir a mão em mercados ruidosos.
- **Limites Diários**: O `RiskManager` bloqueia novas ordens se o `DailyLoss` ou `MaxExposure` for atingido.

---

## 4. Auditoria de Código

As regras acima foram auditadas e localizadas nos seguintes componentes:

- `backend/bot_sniper_win.py`: (Scaling Sniper)
- `backend/main.py`: (SOTA Volatility Sizing)
- `backend/risk_manager.py`: (Volatility logic & Safe Quantization)
- `backend/ai_core.py`: (Quantile Confidence Analysis)

---

_Documento gerado em 2026-03-01 após auditoria estrutural do sistema._
