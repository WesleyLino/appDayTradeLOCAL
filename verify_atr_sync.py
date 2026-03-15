import sys
import os

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.bot_sniper_win import SniperBotWIN


def verify():
    print("--- DIAGNÓSTICO DE SINCRONIZAÇÃO SOTA ---")

    # Instancia o Bot (que carrega o RiskManager e o JSON)
    # Usamos dry_run=True para não conectar no MT5 se não for necessário
    bot = SniperBotWIN(dry_run=True)

    # Verifica o valor no RiskManager
    current_atr_threshold = bot.risk.min_atr_threshold

    print("Símbolo Alvo: WIN$")
    print(f"Threshold ATR Ativo: {current_atr_threshold}")

    if current_atr_threshold == 40.0:
        print(
            "\n✅ SUCESSO: O ajuste de 40.0 foi detectado e está ATIVO no motor de risco."
        )
    else:
        print(
            f"\n❌ FALHA: O sistema ainda reporta {current_atr_threshold}. Verifique a sincronização."
        )


if __name__ == "__main__":
    try:
        verify()
    except Exception as e:
        print(f"Erro no diagnóstico: {e}")
