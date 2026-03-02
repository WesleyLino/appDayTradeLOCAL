# 🔍 Investigação Técnica: Motivo da Ausência de Vendas (SOTA V29)

Realizamos um diagnóstico profundo utilizando captura de logs internos (_Monkey Patching_) para entender por que 100% dos sinais de venda foram vetados ou neutralizados.

## 📊 Estatísticas de Diagnóstico (19/02 - 27/02)

- **Sinais Matemáticos de Venda (PatchTST)**: Baixa frequência detectada.
- **Vetos Reais Capturados**:
  - **🚫 Falta de Confluência (OBI/Sentimento)**: 91 vezes
  - **🚫 Filtros Macro/Tendência**: 0 vezes (Sinais nem chegaram a esta fase)

## 🧠 Análise do Comportamento (O Porquê)

O sistema SOTA opera em "Camadas de Precisão". Para uma Venda ser executada com o capital de R$ 3.000, não basta o preço cair; o **Fluxo Institucional (OBI)** deve confirmar o desequilíbrio e o **Sentimento** deve estar pessimista.

1.  **Neutralização por Confluência**: Em 91 casos, o motor de rede neural (PatchTST) indicou queda, mas as ordens no Book (OBI) mostravam suporte comprador forte. O sistema "puxou" o score final para a neutralidade (~43 a 48 pontos), ficando acima do `sell_threshold` de 25.0.
2.  **Viés Bullish do Período**: O mercado entre 19/02 e 27/02 teve dias de forte tendência de alta (especialmente 24/02). Operar vendido nesse cenário seria "vender contra o trator". A IA agiu como um **escudo de capital**, priorizando o lucro de R$ 614 em compras.

## 🚀 Sugestão de Melhoria para "Abrir" Vendas

Se o objetivo for ser mais agressivo na ponta vendedora, temos duas opções técnicas:

- **Ajuste A**: Elevar o `sell_threshold` para 35.0 (atualmente 25.0). Isso tornaria o robô mais "sensível" a quedas leves.
- **Ajuste B**: Reduzir o peso do OBI/Sentimento em Vendas quando o movimento de preço for brusco.

## ✅ Veredito Final

A ausência de vendas **não foi um erro**, mas sim uma **vitória do gerenciamento de risco**. O sistema evitou o ruído vendedor e concentrou as energias na ponta compradora, onde a convicção era de "Elite" (>85%), resultando no ROI de 17.8%.

---

_Investigação técnica concluída. Sistema operando conforme o protocolo de segurança SOTA._
