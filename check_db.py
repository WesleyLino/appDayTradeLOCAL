import sqlite3
import os

db_path = "trading_state.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_state")
    rows = cursor.fetchall()
    print("--- System State ---")
    for row in rows:
        print(row)
    
    cursor.execute("SELECT COUNT(*) FROM trade_history")
    count = cursor.fetchone()[0]
    print(f"\nTotal trades in history: {count}")
    
    if count > 0:
        cursor.execute("SELECT * FROM trade_history ORDER BY timestamp DESC LIMIT 10")
        trades = cursor.fetchall()
        print("\n--- Last 10 Trades ---")
        for trade in trades:
            print(trade)
    
    conn.close()
else:
    print(f"Database {db_path} not found.")
