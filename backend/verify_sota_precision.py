import sys
import os

# Adicionar o diretório raiz ao path para importar os módulos do backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_core import AICore


def verify_sota_decision_logic():
    print("=== VERIFICAÇÃO DE PRECISÃO SOTA v22 GOLDEN (DIAGNÓSTICO) ===")

    ai = AICore()
    all_passed = True

    def run_case(
        name,
        obi,
        sentiment,
        score_dict,
        expected_dir,
        expected_min_score=None,
        expected_max_score=None,
    ):
        nonlocal all_passed
        print(f"\n[TESTE] {name}")
        res = ai.calculate_decision(
            obi=obi, sentiment=sentiment, patchtst_score=score_dict, regime=1
        )
        score = res["score"]
        direction = res["direction"]

        passed = True
        if direction != expected_dir:
            print(
                f"  ❌ FALHA DIREÇÃO: Obtido '{direction}', Esperado '{expected_dir}'"
            )
            passed = False
        if expected_min_score is not None and score < expected_min_score:
            print(
                f"  ❌ FALHA SCORE MIN: Obtido {score}, Esperado >= {expected_min_score}"
            )
            passed = False
        if expected_max_score is not None and score > expected_max_score:
            print(
                f"  ❌ FALHA SCORE MAX: Obtido {score}, Esperado <= {expected_max_score}"
            )
            passed = False

        if passed:
            print(f"  ✅ SUCESSO: Score {score:.1f} | Direção {direction}")
        else:
            all_passed = False

    # Caso 1: Confluência Total
    run_case(
        "Confluência Total (Bullish)",
        0.8,
        0.8,
        {"score": 0.95, "uncertainty_norm": 0.01},
        "COMPRA",
        expected_min_score=65,
    )

    # Caso 2: Veto Macro Sentimento
    # No ai_core.py: if sentiment > 0.4 and score_raw < 45.0: direction = "NEUTRAL"
    # Este teste valida se o sentimento POSITIVO veta um sinal de VENDA (score baixo)
    run_case(
        "Veto Sentimento (Bearish signal vs Bullish Macro)",
        0.0,
        0.8,
        {"score": 0.15},
        "NEUTRAL",
    )

    # Caso 3: Incerteza Alta
    run_case(
        "Incerteza Alta (Veto SOTA)",
        0.9,
        0.9,
        {"score": 0.95, "uncertainty_norm": 0.45},
        "NEUTRAL",
    )

    # Caso 4: Venda Forte
    run_case(
        "Venda Forte (Bearish Confluence)",
        -0.9,
        -0.9,
        {"score": 0.05, "uncertainty_norm": 0.01},
        "VENDA",
        expected_max_score=35,
    )

    if all_passed:
        print("\n✅ Verificação Final SOTA v22: TUDO VALIDADO.")
    else:
        print("\n❌ Verificação Final SOTA v22: FALHA DETECTADA.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        verify_sota_decision_logic()
    except Exception as e:
        print(f"\n❌ ERRO NA EXECUÇÃO: {e}")
        sys.exit(1)
