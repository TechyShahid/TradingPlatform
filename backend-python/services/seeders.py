"""
Background seeders and startup tasks.
- IPO seed data
- Database seeding orchestration (deals, fundamentals, compounders)
- News crawler background loop
"""
import time
import datetime
import database


def background_news_crawler_task():
    import news_crawler
    print("[News Crawler Thread] Background thread started.")
    # Run once immediately on startup
    try:
        news_crawler.crawl_all_news()
    except Exception as e:
        print(f"[News Crawler Thread] Error during startup crawl: {e}")
        
    while True:
        time.sleep(900)  # Sleep for 15 minutes
        try:
            print("[News Crawler Thread] Running scheduled periodic news crawl...")
            news_crawler.crawl_all_news()
        except Exception as e:
            print(f"[News Crawler Thread] Error during scheduled crawl: {e}")


def background_seeding_task():
    print("[Database Seeder] Checking database status...")
    
    # Clean up any legacy hardcoded IPO seed records
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        legacy_symbols = ["SWIGGY", "ACMESOLAR", "NIVABUPA", "SAGILITY", "NTPCGREEN", "ZINKA"]
        cur.execute(f"DELETE FROM ipos WHERE symbol IN ({','.join(['?']*len(legacy_symbols))})", legacy_symbols)
        conn.commit()
        conn.close()
        print("[Database Seeder] Legacy hardcoded IPO records cleared.")
    except Exception as clean_err:
        print(f"[Database Seeder] Error cleaning legacy IPO records: {clean_err}")
        
    # Always pull real live IPO data from NSE on startup
    try:
        from services.ipo_service import fetch_live_ipos
        fetch_live_ipos()
    except Exception as live_err:
        print(f"[Database Seeder] Error during live IPO startup fetch: {live_err}")

    # Check and seed Mutual Funds
    try:
        import seeder_funds
        seeder_funds.seed_data()
    except Exception as e:
        print(f"[Database Seeder] Error seeding mutual funds: {e}")

    # 1. Check & Seed Bulk/Block Deals & Compounders
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bulk_deals")
        deals_count = cur.fetchone()[0]
        conn.close()
    except Exception as e:
        print(f"[Database Seeder] Error checking bulk_deals table: {e}")
        deals_count = 0

    if deals_count == 0:
        print("[Database Seeder] Deals database is empty. Starting real live deals fetch...")
        
        try:
            import fetch_nse_deals
            fetch_nse_deals.fetch_and_store_deals(period="1M")
        except Exception as e:
            print(f"[Database Seeder] Live deals fetch notice: {e}")

        try:
            import fetch_historical_fundamentals
            fetch_historical_fundamentals.fetch_and_analyze_compounders()
        except Exception as e:
            print(f"[Database Seeder] Compounders analysis notice: {e}")
