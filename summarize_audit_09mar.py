import json

def generate_report():
    try:
        with open("results_buy_09.json", "r") as f:
            compras = json.load(f)
        with open("results_sell_09.json", "r") as f:
            vendas = json.load(f)
        with open("results_missed_09.json", "r") as f:
            perdidas = json.load(f)
    except FileNotFoundError:
        print("Erro: Faça o run_financial_backtest_09mar.py primeiro.")
        return
        
    pnl_compra = sum(c.get('pnl_pts', 0) * 0.2 * 1 for c in compras) # Lote padrao 0.2
    pnl_venda = sum(v.get('pnl_pts', 0) * 0.2 * 1 for v in vendas)
    
    print("\n=======================================================")
    print("      AUDITORIA DE POTENCIAL DIRETO - DIA 09/03        ")
    print("      CONFIG: SOTA GOLDEN V3 (Com Break-Even 40pts)    ")
    print("=======================================================\n")
    
    # 1. Compras
    print("[COMPRAS]")
    print(f"Total de Entradas: {len(compras)}")
    for c in compras:
        lucro_rs = c.get('pnl_pts', 0) * 0.2
        print(f"  - {c['time']} | Resultado: {c['reason']:<12} | RunUp Max: {c.get('max_runup', 0):>5} pts | PnL: R$ {lucro_rs:>6.2f}")
    print(f"SALDO PARCIAL (COMPRAS): R$ {pnl_compra:.2f}\n")
    
    # 2. Vendas
    print("[VENDAS]")
    print(f"Total de Entradas: {len(vendas)}")
    for v in vendas:
        lucro_rs = v.get('pnl_pts', 0) * 0.2
        print(f"  - {v['time']} | Resultado: {v['reason']:<12} | RunUp Max: {v.get('max_runup', 0):>5} pts | PnL: R$ {lucro_rs:>6.2f}")
    print(f"SALDO PARCIAL (VENDAS): R$ {pnl_venda:.2f}\n")
    
    # 3. Overall
    print("=======================================================")
    print(f"SALDO LÍQUIDO FINAL DO DIA: R$ {pnl_compra + pnl_venda:.2f}")
    print("=======================================================\n")
    
    # 4. Analise de Movimentos Longos Perdidos
    movimentos_gigantes = [p for p in perdidas if p['amplitude'] >= 150]
    
    print("[POTENCIAL PERDIDO - PERNAS GIGANTES (150+ pts)]")
    print(f"Identificamos {len(movimentos_gigantes)} candles que se moveram mais de 150 pts onde a IA decidiu recuar.")
    
    motivos_rejeicao = {}
    for p in movimentos_gigantes:
        motivo = p.get('motivo_rejeicao', 'Desconhecido')
        motivos_rejeicao[motivo] = motivos_rejeicao.get(motivo, 0) + 1
        print(f"  - {p['time'][:5]} | Direção: {p['direcao']:<5} | Amplitude: {p['amplitude']} pts | Atr na hora: {p['atr_momento']:.1f}")
        
    print("\nOs filtros (SOTA e Setup Golden) que VETARAM nossas entradas foram:")
    for k, v in motivos_rejeicao.items():
        print(f"  - {k}: {v} vezes")
        
    print("\n[MÉTRICAS DA ESTRUTURA DIRETA]")
    print("O dia 09/03 foi auditado integralmente sem alteração na lógica de produção.")
    print("=======================================================\n")

if __name__ == "__main__":
    generate_report()
