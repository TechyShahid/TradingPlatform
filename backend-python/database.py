import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'nse_deals.db')
POSTGRES_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')

class PostgreSQLCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        if params is not None:
            query = query.replace('?', '%s')
        if "AUTOINCREMENT" in query:
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        self.cursor.execute(query, params)

    def fetchall(self):
        rows = self.cursor.fetchall()
        if rows and hasattr(rows[0], 'keys'):
            return [dict(r) for r in rows]
        return rows

    def fetchone(self):
        row = self.cursor.fetchone()
        if row and hasattr(row, 'keys'):
            return dict(row)
        return row

    def executemany(self, query, params_list):
        query = query.replace('?', '%s')
        self.cursor.executemany(query, params_list)

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def description(self):
        return self.cursor.description

class PostgreSQLConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
        self._row_factory = None

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, val):
        self._row_factory = val

    def cursor(self):
        from psycopg2.extras import RealDictCursor
        if self._row_factory is not None:
            return PostgreSQLCursorWrapper(self.conn.cursor(cursor_factory=RealDictCursor))
        return PostgreSQLCursorWrapper(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

def get_db_connection():
    if POSTGRES_URL:
        import psycopg2
        conn = psycopg2.connect(POSTGRES_URL)
        return PostgreSQLConnectionWrapper(conn)
    else:
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
            ticker TEXT,
            region TEXT DEFAULT 'India'
        )
    ''')
    
    # Run migration to add region column to stock_news if it existed without it
    try:
        cursor.execute("ALTER TABLE stock_news ADD COLUMN region TEXT DEFAULT 'India'")
    except sqlite3.OperationalError:
        pass # Column already exists
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            last_login TEXT,
            entitlements TEXT
        )
    ''')
    
    # Run migration to add entitlements column if table existed without it
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN entitlements TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists
        
    # Create ipos table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ipos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            symbol TEXT UNIQUE NOT NULL,
            issue_start_date TEXT,
            issue_end_date TEXT,
            price_range TEXT,
            issue_size TEXT,
            lot_size INTEGER,
            status TEXT,
            retail_x REAL DEFAULT 0.0,
            hni_x REAL DEFAULT 0.0,
            qib_x REAL DEFAULT 0.0,
            total_x REAL DEFAULT 0.0,
            gmp TEXT DEFAULT 'N/A',
            updated_at TEXT
        )
    ''')

    try:
        cursor.execute("ALTER TABLE ipos ADD COLUMN gmp TEXT DEFAULT 'N/A'")
    except (sqlite3.OperationalError, Exception):
        pass # Column already exists or table handles it

    # Create mutual funds tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS funds (
            amfi_code TEXT PRIMARY KEY,
            scheme_name TEXT NOT NULL,
            category TEXT NOT NULL,       -- 'Equity', 'Debt', 'Hybrid'
            sub_category TEXT NOT NULL,   -- 'Large Cap', 'Mid Cap', 'Small Cap', 'ELSS', 'Liquid'
            risk_rating TEXT NOT NULL,    -- 'Low', 'Moderate', 'High', 'Very High'
            expense_ratio REAL,           -- e.g. 0.75 (%)
            exit_load TEXT,               -- exit load description
            fund_manager TEXT,            -- fund manager name
            aum REAL,                     -- AUM in Crores (INR)
            star_rating INTEGER DEFAULT 3, -- 1-5 stars
            launch_date TEXT,
            return_1y REAL DEFAULT 0.0,
            return_3y REAL DEFAULT 0.0,
            return_5y REAL DEFAULT 0.0
        )
    ''')

    try:
        cursor.execute("ALTER TABLE funds ADD COLUMN return_1y REAL DEFAULT 0.0")
    except (sqlite3.OperationalError, Exception):
        pass

    try:
        cursor.execute("ALTER TABLE funds ADD COLUMN return_3y REAL DEFAULT 0.0")
    except (sqlite3.OperationalError, Exception):
        pass

    try:
        cursor.execute("ALTER TABLE funds ADD COLUMN return_5y REAL DEFAULT 0.0")
    except (sqlite3.OperationalError, Exception):
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fund_nav_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amfi_code TEXT NOT NULL,
            nav_date TEXT NOT NULL,
            nav_price REAL NOT NULL,
            FOREIGN KEY (amfi_code) REFERENCES funds(amfi_code),
            UNIQUE(amfi_code, nav_date)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fund_portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amfi_code TEXT NOT NULL,
            asset_name TEXT NOT NULL,     -- Stock name / bond name
            sector TEXT,                  -- Stock sector (e.g. Finance, Technology)
            allocation_pct REAL NOT NULL, -- Weight of asset in portfolio (%)
            FOREIGN KEY (amfi_code) REFERENCES funds(amfi_code),
            UNIQUE(amfi_code, asset_name)
        )
    ''')
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print(f"Database initialized at {DB_PATH}")
