import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'nse_deals.db')
POSTGRES_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')

class PostgreSQLCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def _transform_query(self, query):
        if not query:
            return query
        import re
        
        # Replace ? parameter placeholder with %s
        transformed = query.replace('?', '%s')
        
        # Replace AUTOINCREMENT
        if "AUTOINCREMENT" in transformed:
            transformed = transformed.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            
        # Replace REGEXP operator with PostgreSQL case-insensitive regex operator ~*
        transformed = re.sub(r'(\w+)\s+REGEXP\s+%s', r'\1 ~* %s', transformed, flags=re.IGNORECASE)
        
        # Translate INSERT OR REPLACE INTO for PostgreSQL compatibility
        if "INSERT OR REPLACE INTO" in transformed.upper():
            if "fund_nav_history" in transformed:
                transformed = transformed.replace("INSERT OR REPLACE INTO fund_nav_history", "INSERT INTO fund_nav_history")
                if "ON CONFLICT" not in transformed.upper():
                    transformed += " ON CONFLICT (amfi_code, nav_date) DO UPDATE SET nav_price = EXCLUDED.nav_price"
            elif "fund_portfolio" in transformed:
                transformed = transformed.replace("INSERT OR REPLACE INTO fund_portfolio", "INSERT INTO fund_portfolio")
                if "ON CONFLICT" not in transformed.upper():
                    transformed += " ON CONFLICT (amfi_code, asset_name) DO UPDATE SET sector = EXCLUDED.sector, allocation_pct = EXCLUDED.allocation_pct"
            elif "funds" in transformed:
                transformed = transformed.replace("INSERT OR REPLACE INTO funds", "INSERT INTO funds")
                if "ON CONFLICT" not in transformed.upper():
                    transformed += " ON CONFLICT (amfi_code) DO UPDATE SET scheme_name = EXCLUDED.scheme_name, category = EXCLUDED.category, sub_category = EXCLUDED.sub_category, risk_rating = EXCLUDED.risk_rating, expense_ratio = EXCLUDED.expense_ratio, exit_load = EXCLUDED.exit_load, fund_manager = EXCLUDED.fund_manager, aum = EXCLUDED.aum, star_rating = EXCLUDED.star_rating, launch_date = EXCLUDED.launch_date"
            elif "metadata" in transformed:
                transformed = transformed.replace("INSERT OR REPLACE INTO metadata", "INSERT INTO metadata")
                if "ON CONFLICT" not in transformed.upper():
                    transformed += " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            else:
                transformed = transformed.replace("INSERT OR REPLACE INTO", "INSERT INTO")
                if "ON CONFLICT" not in transformed.upper():
                    transformed += " ON CONFLICT DO NOTHING"
                
        # Translate INSERT OR IGNORE INTO
        if "INSERT OR IGNORE INTO" in transformed.upper():
            transformed = transformed.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            if "ON CONFLICT" not in transformed.upper():
                transformed += " ON CONFLICT DO NOTHING"
                
        return transformed

    def execute(self, query, params=None):
        transformed = self._transform_query(query)
        if params is not None:
            self.cursor.execute(transformed, params)
        else:
            self.cursor.execute(transformed)

    def executemany(self, query, params_list):
        transformed = self._transform_query(query)
        self.cursor.executemany(transformed, params_list)

    def fetchall(self):
        rows = self.cursor.fetchall()
        if rows:
            return [dict(r) if hasattr(r, 'keys') or isinstance(r, dict) else r for r in rows]
        return []

    def fetchone(self):
        row = self.cursor.fetchone()
        if row:
            return dict(row) if hasattr(row, 'keys') or isinstance(row, dict) else row
        return None

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
        return PostgreSQLCursorWrapper(self.conn.cursor(cursor_factory=RealDictCursor))

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
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        
        # Register a safe case-insensitive REGEXP function for regex symbol searching
        import re
        def regexp(expr, item):
            if not expr:
                return True
            if not item:
                return False
            try:
                return re.search(expr, item, re.IGNORECASE) is not None
            except:
                return expr.lower() in item.lower()
        conn.create_function("REGEXP", 2, regexp)
        
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
    except Exception:
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
    except Exception:
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
