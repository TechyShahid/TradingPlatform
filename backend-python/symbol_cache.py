"""
symbol_cache.py — Weekly-cached NSE equity symbol list using SQLite.

Downloads EQUITY_L.csv from NSE only on first run or every Monday.
Stores symbols in data/symbols.db for instant access on subsequent starts.
"""

import sqlite3
import os
import io
import datetime
import requests
import pandas as pd

# Path to the SQLite database
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DATA_DIR, 'symbols.db')

EQUITY_L_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
}

FALLBACK_SYMBOLS = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN']


def _ensure_db():
    """Create the data directory and database tables if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS symbols (
            symbol TEXT PRIMARY KEY
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    return conn


def _get_last_download_date(conn):
    """Return the last download date as a date object, or None if never downloaded."""
    cur = conn.cursor()
    cur.execute("SELECT value FROM metadata WHERE key = 'last_download_date'")
    row = cur.fetchone()
    if row:
        try:
            return datetime.date.fromisoformat(row[0])
        except ValueError:
            return None
    return None


def _download_and_store(conn):
    """Download EQUITY_L.csv from NSE and store symbols in the database."""
    print("⬇️  Downloading EQUITY_L.csv (fresh)...")
    response = requests.get(EQUITY_L_URL, headers=HEADERS, timeout=10)
    response.raise_for_status()

    df = pd.read_csv(io.StringIO(response.text))
    symbols = [s for s in df['SYMBOL'].tolist() if isinstance(s, str) and len(s) > 0]

    cur = conn.cursor()
    # Clear old symbols and insert fresh list
    cur.execute("DELETE FROM symbols")
    cur.executemany("INSERT INTO symbols (symbol) VALUES (?)", [(s,) for s in symbols])

    # Update the last download date
    today_str = datetime.date.today().isoformat()
    cur.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_download_date', ?)",
        (today_str,)
    )
    conn.commit()
    print(f"✅  Cached {len(symbols)} symbols in {DB_PATH}")
    return symbols


def _read_cached_symbols(conn):
    """Read symbols from the SQLite database."""
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM symbols ORDER BY symbol")
    return [row[0] for row in cur.fetchall()]


def _should_refresh(last_download):
    """Determine whether to re-download based on weekday and last download date."""
    today = datetime.date.today()

    if last_download is None:
        return True  # Never downloaded

    # Refresh on Monday if last download was before today
    if today.weekday() == 0 and last_download < today:  # 0 = Monday
        return True

    return False


def get_symbols():
    """
    Return the list of NSE equity symbols.

    - On first run: downloads from NSE and caches in SQLite.
    - On Mondays: re-downloads to pick up any weekly changes.
    - Otherwise: returns cached data instantly.
    - Falls back to a hardcoded list if everything fails.
    """
    try:
        conn = _ensure_db()
        last_download = _get_last_download_date(conn)

        if _should_refresh(last_download):
            try:
                symbols = _download_and_store(conn)
                conn.close()
                return symbols
            except Exception as e:
                print(f"⚠️  Download failed: {e}")
                # Fall through to try cached data

        # Use cached data
        symbols = _read_cached_symbols(conn)
        conn.close()

        if symbols:
            print(f"📦  Using cached symbols ({len(symbols)} symbols, last download: {last_download})")
            return symbols

    except Exception as e:
        print(f"⚠️  Cache error: {e}")

    # Ultimate fallback
    print("🔄  Using fallback symbol list")
    return FALLBACK_SYMBOLS
