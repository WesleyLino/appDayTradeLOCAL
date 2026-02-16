import sqlite3
import os
import logging
from datetime import datetime

class PersistenceManager:
    def __init__(self, db_path="trading_state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Inicializa as tabelas se não existirem."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabela de estado global
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            ''')
            
            # Tabela de logs de operações (para auditoria local)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    type TEXT,
                    price REAL,
                    volume INTEGER,
                    timestamp TIMESTAMP,
                    status TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Erro ao inicializar banco de dados: {e}")

    def save_state(self, key, value):
        """Salva um par chave-valor no estado do sistema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, str(value), datetime.now()))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Erro ao salvar estado: {e}")

    def get_state(self, key):
        """Recupera um valor do estado do sistema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM system_state WHERE key = ?', (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logging.error(f"Erro ao recuperar estado: {e}")
            return None

    def save_trade(self, symbol, side, price, volume, status="DONE"):
        """Registra uma operação executada no histórico para auditoria."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trade_history (symbol, type, price, volume, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (symbol, side, price, volume, datetime.now(), status))
            conn.commit()
            conn.close()
            logging.info(f"Trade salvo no SQLite: {side} {volume} de {symbol} a {price}")
        except Exception as e:
            logging.error(f"Erro ao salvar trade no banco: {e}")

if __name__ == "__main__":
    # Teste rápido
    pm = PersistenceManager("test_state.db")
    pm.save_state("is_trading", "True")
    print(f"Trading state: {pm.get_state('is_trading')}")
