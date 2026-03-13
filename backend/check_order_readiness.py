import MetaTrader5 as mt5
import sys

def check_readiness():
    if not mt5.initialize():
        print(f"ERRO: Falha ao inicializar MT5: {mt5.last_error()}")
        return

    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        print("ERRO: Não foi possível obter informações do terminal.")
        mt5.shutdown()
        return

    account_info = mt5.account_info()
    if account_info is None:
        print("ERRO: Não foi possível obter informações da conta.")
        mt5.shutdown()
        return

    t_dict = terminal_info._asdict()
    a_dict = account_info._asdict()

    print("--- DIAGNÓSTICO DE PRONTIDÃO ---")
    print(f"Conta: {a_dict.get('login')}")
    print(f"Servidor: {a_dict.get('server')}")
    print(f"Margem Livre: {a_dict.get('margin_free')}")
    print(f"Equity: {a_dict.get('equity')}")
    
    print("\n--- STATUS DE EXECUÇÃO (MT5) ---")
    
    # Propriedades do Terminal
    t_trade_allowed = t_dict.get('trade_allowed', False)
    t_algo_allowed = t_dict.get('trade_expert', False) # No MT5 Python, as vezes é trade_expert
    
    # Propriedades da Conta
    a_trade_allowed = a_dict.get('trade_allowed', False)
    a_expert_allowed = a_dict.get('trade_expert', False) # Alguns servidores tem trava de EA na conta

    print(f"Trading Permitido no Terminal: {'SIM' if t_trade_allowed else 'NÃO'}")
    print(f"AlgoTrading (EA) Permitido no Terminal: {'SIM' if t_algo_allowed else 'NÃO'}")
    print(f"Trading Permitido na Conta: {'SIM' if a_trade_allowed else 'NÃO'}")
    print(f"Expert Advisors Permitidos na Conta: {'SIM' if a_expert_allowed else 'NÃO'}")

    # Verificação Final
    if t_trade_allowed and t_algo_allowed and a_trade_allowed:
        print("\n✅ CONCLUSÃO: O sistema está TCNICAMENTE APTO a executar ordens.")
    else:
        print("\n❌ CONCLUSÃO: O sistema possui bloqueios ativos.")
        if not t_algo_allowed:
            print("   -> ATENÇÃO: O botão 'Algo Trading' no topo do MT5 deve estar VERDE.")
        if not a_trade_allowed:
            print("   -> ATENÇÃO: A corretora bloqueou o trading nesta conta (Disabled on Server).")

    mt5.shutdown()

if __name__ == "__main__":
    check_readiness()
