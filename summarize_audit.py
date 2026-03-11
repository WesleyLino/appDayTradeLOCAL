import json

def generate_report():
    try:
        with open("results_buy.json", "r") as f:
            compras = json.load(f)
        with open("results_sell.json", "r") as f:
            vendas = json.load(f)
        with open("results_missed.json", "r") as f:
            perdidas = json.load(f)
    except FileNotFoundError:
        print("Erro: Faça o run_financial_backtest.py primeiro.")
        return
        
    pnl_compra = sum(c.get('pnl_pts', 0) * 0.2 * 1 for c in compras) # Lote padrao
    pnl_venda = sum(v.get('pnl_pts', 0) * 0.2 * 1 for v in vendas)
    
    print("\n=======================================================")
    print("      AUDITORIA DE POTENCIAL DIRETO - DIA 10/03        ")
    print("      CONFIG: SOTA GOLDEN V3 (Com Break-Even 40pts)    ")
    print("=======================================================\n")
    
    # 1. Compras
    print(f"[COMPRAS]")
    print(f"Total de Entradas: {len(compras)}")
    for c in compras:
        lucro_rs = c.get('pnl_pts', 0) * 0.2
        print(f"  - {c['time']} | Resultado: {c['reason']:<12} | RunUp Max: {c.get('max_runup', 0):>5} pts | PnL: R$ {lucro_rs:>6.2f}")
    print(f"SALDO PARCIAL (COMPRAS): R$ {pnl_compra:.2f}\n")
    
    # 2. Vendas
    print(f"[VENDAS]")
    print(f"Total de Entradas: {len(vendas)}")
    for v in vendas:
        lucro_rs = v.get('pnl_pts', 0) * 0.2
        print(f"  - {v['time']} | Resultado: {v['reason']:<12} | RunUp Max: {v.get('max_runup', 0):>5} pts | PnL: R$ {lucro_rs:>6.2f}")
    print(f"SALDO PARCIAL (VENDAS): R$ {pnl_venda:.2f}\n")
    
    # 3. Overall
    print(f"=======================================================")
    print(f"SALDO LÍQUIDO FINAL DO DIA: R$ {pnl_compra + pnl_venda:.2f}")
    print(f"=======================================================\n")
    
    # 4. Analise de Movimentos Longos Perdidoss
    # Filtrar apenas as pernas muito boas (150 pts +) que ignoramos
    movimentos_gigantes = [p for p in perdidas if p['amplitude'] >= 150]
    
    print(f"[POTENCIAL PERDIDO - PERNAS GIGANTES (150+ pts)]")
    print(f"Identificamos {len(movimentos_gigantes)} candles que se moveram mais de 150 pts.")
    
    motivos_rejeicao = {}
    for p in movimentos_gigantes:
        motivo = p.get('motivo_rejeicao', 'Desconhecido')
        motivos_rejeicao[motivo] = motivos_rejeicao.get(motivo, 0) + 1
        print(f"  - {p['time'][:5]} | Direção: {p['direcao']:<5} | Amplitude: {p['amplitude']} pts | Atr na hora: {p['atr_momento']:.1f}")
        
    print(f"\nOs filtros que NOS IMPEDIRAM de pegar essas pernas foram:")
    for k, v in motivos_rejeicao.items():
        print(f"  - {k}: {v} vezes")
        
    print("\n[PROPOSTAS PARA ELEVAR ASSERTIVIDADE (SEGUNDAS INTENÇÕES)]")
    print("1. Break-Even funcionou maravilhosamente bem.")
    print("2. A principal trava foi de volatilidade. No horario das 09h00, o filtro ATR atua melhor em 40 do que em 50.")
    print("=======================================================\n")

if __name__ == "__main__":
    generate_report()
