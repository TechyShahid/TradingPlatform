"""
Sync Script for PostgreSQL (Render / Remote Database)
Run this script locally to fetch live market data (NSE Bulk & Block Deals, IPOs + Subscription Multipliers, Mutual Funds)
and save it directly into your PostgreSQL database (e.g. hosted on Render).

Usage:
  DATABASE_URL="postgres://user:password@render-db-host/dbname" python3 sync_to_postgres.py
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(__file__))

import database

def run_sync():
    print("=" * 60)
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Local-to-PostgreSQL Sync...")
    print("=" * 60)
    
    postgres_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    if postgres_url:
        print(f"[Database] Target: PostgreSQL ({postgres_url[:25]}...)")
    else:
        print(f"[Database] Target: SQLite ({database.DB_PATH})")
        print("[Notice] Tip: Set DATABASE_URL=postgres://... to push directly to Render PostgreSQL DB!")

    # 1. Initialize Tables in DB
    print("\n1. Initializing database schema...")
    database.init_db()
    print("   [+] Schema initialization complete.")

    # 2. Sync Live IPO Data & Subscription Multipliers
    print("\n2. Fetching Live IPO Data & Subscription Demand Multipliers from NSE...")
    try:
        from services.ipo_service import fetch_live_ipos
        fetch_live_ipos()
        print("   [+] IPO & Subscription sync complete.")
    except Exception as ipo_err:
        print(f"   [!] IPO fetch warning: {ipo_err}")

    # 3. Sync NSE Bulk & Block Deals
    print("\n3. Fetching NSE Bulk & Block Deals...")
    try:
        import fetch_nse_deals
        fetch_nse_deals.fetch_and_store_deals()
        print("   [+] Deals sync complete.")
    except Exception as deals_err:
        print(f"   [!] Deals fetch warning: {deals_err}")

    # 4. Sync Mutual Funds Data
    print("\n4. Seeding/Updating Mutual Funds & Portfolios...")
    try:
        import seeder_funds
        seeder_funds.seed_data()
        print("   [+] Mutual Funds sync complete.")
    except Exception as mf_err:
        print(f"   [!] Mutual Funds sync warning: {mf_err}")

    print("\n" + "=" * 60)
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sync finished successfully!")
    print("=" * 60)

if __name__ == '__main__':
    run_sync()
