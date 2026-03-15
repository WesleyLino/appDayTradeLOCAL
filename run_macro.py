import sys
import os
import logging

# Adicionar diretório atual ao path
sys.path.append(os.getcwd())

# Mock modules if necessary, but we try to use real ones
try:
    from backend.mt5_bridge import MT5Bridge
    from backend.risk_manager import RiskManager
    import MetaTrader5 as mt5_module
except ImportError:
    print("Modules not found, skipping specific test.")
    sys.exit(0)

# Config logging
logging.basicConfig(level=logging.INFO)


def test_risk_logic():
    print("\n--- Testando Lógica do RiskManager (Macro) ---")
    risk = RiskManager()

    # Caso 1: Queda forte (-0.6%) -> Deve bloquear BUY
    ok, msg = risk.check_macro_filter("buy", -0.6)
    print(f"Buy w/ -0.6%: {ok} ({msg}) -> Esperado: False")
    if ok:
        print("❌ FALHA: Deveria bloquear Buy")

    # Caso 2: Queda forte (-0.6%) -> Deve permitir SELL (ou neutro)
    # A regra diz: "Bloqueia VENDA se subir > 0.5%". Queda não bloqueia venda.
    ok, msg = risk.check_macro_filter("sell", -0.6)
    print(f"Sell w/ -0.6%: {ok} ({msg}) -> Esperado: True")
    if not ok:
        print("❌ FALHA: Deveria permitir Sell")

    # Caso 3: Alta forte (+0.6%) -> Deve bloquear SELL
    ok, msg = risk.check_macro_filter("sell", 0.6)
    print(f"Sell w/ +0.6%: {ok} ({msg}) -> Esperado: False")
    if ok:
        print("❌ FALHA: Deveria bloquear Sell")

    # Caso 4: Neutro (0.0%)
    ok, msg = risk.check_macro_filter("buy", 0.0)
    print(f"Buy w/ 0.0%: {ok} ({msg}) -> Esperado: True")


def test_bridge_macro():
    print("\n--- Testando MT5Bridge.get_macro_data ---")
    bridge = MT5Bridge()
    # Mocking connection for test if MT5 is not actually running
    bridge.connected = True

    # We can't easily mock the mt5 calls without a mock framework or running MT5.
    # We will try to call it and catch errors if MT5 is missing.
    try:
        macro_val = bridge.get_macro_data()
        print(f"Valor retornado: {macro_val}")
        print("✅ get_macro_data executou sem crashar.")
    except Exception as e:
        print(f"⚠️ Erro ao chamar get_macro_data (Esperado se MT5 off): {e}")


if __name__ == "__main__":
    test_risk_logic()
    test_bridge_macro()
