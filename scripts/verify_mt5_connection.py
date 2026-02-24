import MetaTrader5 as mt5
import sys
import os
import time

def verify_mt5():
    print("--- INICIANDO VERIFICAÇÃO DE CONEXÃO MT5 (GENIAL) ---")
    
    if not mt5.initialize():
        print(f"❌ Falha ao inicializar MT5. Erro: {mt5.last_error()}")
        sys.exit(1)

    # 1. Verificar Informações da Conta
    account = mt5.account_info()
    if not account:
        print("❌ Não foi possível ler informações da conta. Você está logado?")
        mt5.shutdown()
        sys.exit(1)

    print(f"✅ Login: {account.login}")
    print(f"✅ Nome: {account.name}")
    print(f"✅ Servidor: {account.server}")
    print(f"✅ Corretora: {account.company}")
    print(f"💰 Saldo: R$ {account.balance:.2f}")

    # 2. Validar Servidor Genial
    allowed_servers = ["GenialInvestimentos-PRD", "GenialInvestimentos-DEMO"]
    if account.server in allowed_servers:
        print(f"✅ Validação de Servidor: APROVADO ({account.server})")
    else:
        print(f"⚠️ AVISO: Servidor ({account.server}) não é o padrão Genial detectado.")

    # 3. Validar AlgoTrading
    terminal = mt5.terminal_info()
    if terminal.trade_allowed:
        print("✅ AlgoTrading: ATIVADO (Pronto para operar)")
    else:
        print("❌ AlgoTrading: DESATIVADO! Ative o botão 'AlgoTrading' no topo do MT5.")

    # 4. Validar Dados de Mercado (WIN/WDO)
    print("\nTestando Recebimento de Dados (Market Data)...")
    
    # Importar lógica de cálculo de símbolo da bridge para garantir consistência
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from backend.mt5_bridge import MT5Bridge
    bridge = MT5Bridge() # Instância para usar helpers (já conectado pelo main, mas ok instanciar leve)
    
    # Recalcular símbolos atuais
    win_sym = bridge.get_current_symbol("WIN")
    wdo_sym = bridge.get_current_symbol("WDO")
    
    def check_symbol_data(symbol):
        if not mt5.symbol_select(symbol, True):
            print(f"❌ Erro: Não foi possível selecionar o símbolo {symbol}. Verifique se adicionou no Market Watch.")
            return False
            
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print(f"⚠️ Aviso: Tick vazio para {symbol}. Mercado pode estar fechado ou sem liquidez.")
            return False
            
        print(f"✅ {symbol}: Preço={tick.last} | Bid={tick.bid} | Ask={tick.ask}")
        return True

    check_symbol_data(win_sym)
    check_symbol_data(wdo_sym)

    # 5. Teste de Latência (Ping Simples)
    print("\nTestando latência de conexão...")
    t0 = time.time()
    mt5.terminal_info() # Chamada leve
    latency = (time.time() - t0) * 1000
    print(f"📶 Latência API Local: {latency:.2f}ms")

    mt5.shutdown()
    print("\n--- FIM DA VERIFICAÇÃO ---")

if __name__ == "__main__":
    verify_mt5()
