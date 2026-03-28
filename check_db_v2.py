import sqlite3
import os

db_path = "trading_state.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_state WHERE key IN ('sniper_trade_count', 'sniper_last_date')")
    rows = cursor.fetchall()
    print("--- Sniper Bot State ---")
    for row in rows:
        print(row)
    
    # Check if there are any specific simulation entries in trade_history
    cursor.execute("SELECT * FROM trade_history WHERE status LIKE '%SIM%' OR status LIKE '%TEST%'")
    rows = cursor.fetchall()
    print(f"\n--- Simulation Trades in History ({len(rows)}) ---")
    for row in rows:
        print(row)
        
    conn.close()
else:
    print(f"Database {db_path} not found.")
