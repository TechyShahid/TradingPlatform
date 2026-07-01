import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'nse_deals.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create bulk_deals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bulk_deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_date TEXT,
            symbol TEXT,
            security_name TEXT,
            client_name TEXT,
            buy_sell TEXT,
            quantity_traded INTEGER,
            trade_price REAL,
            remarks TEXT,
            UNIQUE(deal_date, symbol, client_name, buy_sell, quantity_traded)
        )
    ''')
    
    # Create block_deals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS block_deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_date TEXT,
            symbol TEXT,
            security_name TEXT,
            client_name TEXT,
            buy_sell TEXT,
            quantity_traded INTEGER,
            trade_price REAL,
            remarks TEXT,
            UNIQUE(deal_date, symbol, client_name, buy_sell, quantity_traded)
        )
    ''')
    
    # Create fundamentals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fundamentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            year TEXT,
            total_revenue REAL,
            net_income REAL,
            ebitda REAL,
            total_assets REAL,
            total_liabilities REAL,
            UNIQUE(symbol, year)
        )
    ''')
    
    # Create consistent_compounders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consistent_compounders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE,
            avg_3yr_growth_pct REAL,
            ai_driving_factor TEXT,
            last_updated TEXT
        )
    ''')
    
    # Create stock_news table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            url TEXT UNIQUE,
            summary TEXT,
            published_at TEXT,
            sentiment TEXT,
            ticker TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print(f"Database initialized at {DB_PATH}")
