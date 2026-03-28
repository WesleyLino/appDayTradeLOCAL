import sqlite3
import os

db_path = "backend/trading_state.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM trade_history ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        print("--- ÚLTIMAS 20 OPERAÇÕES ---")
        for row in rows:
            print(row)
        if not rows:
            print("Nenhuma operação registrada no banco de dados hoje.")
    except Exception as e:
        print(f"Erro ao ler banco de dados: {e}")
    conn.close()
else:
    print("Banco de dados trading_state.db não encontrado.")
