# GEMINI.md - Antigravity Kit (Workspace Rules)

> This document defines immutable architectural constraints and AI behavioral rules for this workspace.

---

## 🛑 HARDWARE ACCELERATION PROTOCOL (MANDATORY)

To prevent regression in the AMD/DirectML inference pipeline, any AI modifying the SOTA model MUST adhere to:

### 1. NO DYNAMIC AXES

- **Rule**: Never use `dynamic_axes` in `torch.onnx.export` for the SOTA model.
- **Reason**: DirectML triggers `MatMul` dimension mismatches when encountering dynamic shapes in the transformer blocks.

### 2. PREFER CONV1D FOR PATCHING

- **Rule**: Avoid `unfold()` or `view()` patterns that create non-contiguous memory layouts during patching.
- **Reason**: `Conv1d` creates a much cleaner ONNX graph that validates successfully on DmlExecutionProvider.

### 3. FLOAT32 ONLY

- **Rule**: Do not attempt FP16 optimization on the ONNX model.
- **Reason**: The `SimpleRevIN` and specific Attention ops trigger `Cast` errors in the DirectML kernel when using float16.

---

## 📡 INFERENCE STABILITY

- **Rule**: AI must always verify `DmlExecutionProvider` availability before recommending ONNX configurations.
- **Rule**: Maintain the `try-except` structure with `repr(e)` logging in `ai_core.py` to prevent `UnicodeDecodeError`.

---

## 📋 PRE-FLIGHT CHECKLIST (AI-ONLY)

Before committing changes to `backend/models/` or `backend/ai_core.py`:

1. Run `python amd_gpu_test.py`
2. Run `python .agent/scripts/checklist.py .`

---

> [!IMPORTANT]
> These rules were established on 2026-02-19 after solving a critical structural mismatch in the PatchTST -> ONNX -> DirectML pipeline. DO NOT OVERWRITE WITHOUT STRESS-TEST VERIFICATION.

---

## 🇧🇷 PROTOCOLO DE IDIOMA (OBRIGATÓRIO)

- **Regra**: TODA a comunicação da IA, comentários de código, instruções, logs e alertas da aplicação DEVEM ser em **Português do Brasil (PT-BR)**.
- **Exceção**: Nomes de variáveis, funções e classes permanecem em Inglês por padrão técnico de programação.

---

## 🔒 LOCKDOWN DE CONFIGURAÇÕES (SOTA 09/03)

Para garantir a estabilidade absoluta após as melhorias de assertividade e sincronização:

1. **Pesos das Blue Chips**: Os pesos no `market_data_worker.py` (VALE3: 0.14, PETR4: 0.12, etc.) são EXCLUSIVOS e estão bloqueados.
2. **Balizamento B3**: O cálculo de variação via `copy_rates_from_pos(..., 2)` e `rates[0].close` no `mt5_bridge.py` é a única fonte de verdade permitida.
3. **Janela Operacional**: O encerramento às 17:15 e o filtro de notícias são regras pétreas do `risk_manager.py`.
4. **Hiperparâmetros da IA**: Qualquer alteração em `ai_core.py` ou `v22_locked_params.json` exige 48h de backtest comprovado.

---

## 🛡️ ANTI-VIBE-CODING PROTOCOL (MANDATORY)

To preserve the absolute stability of the HFT ecosystem and defend against AI hallucinations or unnecessary "clean-ups":

1. **Working Code is Sacred**: NEVER alter, refactor, or delete code that is currently functioning without errors just because it could be "optimized" or "looks better" (vibe coding).
2. **Mandatory Authorization**: If an alteration to fully functioning code is deemed STRICTLY NECESSARY (e.g., to append a new requested feature, patch an edge-case, or explicitly required enhancement), the AI **MUST** halt and use `notify_user` to request explicit authorization _before_ making the change.
3. **Justification Requirement**: When requesting authorization, the AI must explicitly state WHY the update is needed (e.g., "necessário para o UI refletir X", "correção de bug crítico", ou "ajuste solicitado pelo usuário").
4. **Contract Freeze**: Critical API payloads and UI mappings (like numbers 0, 1, 2 for regimes) must be frozen with a `# [ANTIVIBE-CODING]` inline comment.
5. **V22 GOLDEN PARAMS**: The file `backend/v22_locked_params.json` contains the validated golden parameters for the 3000 BRL account. **NO AI** is allowed to modify this file or the corresponding hardcoded defaults in `BacktestPro` without a dedicated validation session (Min 2 days of backtest proof) AND explicit user authorization.
