import sqlite3
import datetime
import random
import os
import urllib.request
import json
import database

def generate_nav_history(start_price, annual_drift, daily_volatility, start_date, end_date):
    nav_list = []
    current_price = start_price
    curr_date = start_date
    delta = datetime.timedelta(days=1)
    
    daily_drift = annual_drift / 250
    daily_vol = daily_volatility / (250 ** 0.5)
    
    while curr_date <= end_date:
        if curr_date.weekday() < 5:
            shock = random.normalvariate(0, 1)
            pct_change = daily_drift + (daily_vol * shock)
            current_price = max(1.0, current_price * (1 + pct_change))
            nav_list.append((curr_date.strftime('%Y-%m-%d'), round(current_price, 4)))
        curr_date += delta
    return nav_list

def fetch_real_nav_history(amfi_code):
    url = f"https://api.mfapi.in/mf/{amfi_code}"
    print(f"[Database Seeder] Fetching real NAV history for code {amfi_code}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=15)
        res_data = json.loads(response.read().decode('utf-8'))
        
        if res_data.get("status") == "SUCCESS" and "data" in res_data:
            nav_list = []
            for item in res_data["data"]:
                try:
                    d_str = item["date"]
                    nav_val = float(item["nav"])
                    parts = d_str.split('-')
                    if len(parts) == 3:
                        formatted_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                        nav_list.append((formatted_date, nav_val))
                except:
                    continue
            nav_list.sort(key=lambda x: x[0])
            return nav_list
    except Exception as e:
        print(f"[Database Seeder] Network error fetching real NAV for {amfi_code}: {e}")
    return None

def parse_amfi_nav_file():
    """Downloads NAVAll.txt from AMFI and parses it to extract active schemes."""
    url = "https://portal.amfiindia.com/spages/NAVAll.txt"
    print("[Database Seeder] Downloading master active mutual schemes from AMFI...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=25)
        content = response.read().decode('utf-8', errors='ignore')
        
        schemes = []
        current_category = "Equity"
        current_sub_category = "Multi Cap"
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Identify category header
            # Example: "Open Ended Schemes(Debt Scheme - Banking and PSU Fund)"
            if '(' in line and ')' in line and ';' not in line:
                try:
                    start_idx = line.find('(') + 1
                    end_idx = line.find(')')
                    category_text = line[start_idx:end_idx].strip()
                    # e.g. "Debt Scheme - Banking and PSU Fund" or "Equity Scheme - Large Cap Fund"
                    if ' - ' in category_text:
                        parts = category_text.split(' - ')
                        cat = parts[0].replace('Scheme', '').strip()
                        sub_cat = parts[1].strip()
                        current_category = cat
                        current_sub_category = sub_cat
                except:
                    pass
                continue
            
            # Semicolon separated data line
            # Format: Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
            if ';' in line:
                parts = line.split(';')
                if len(parts) >= 5:
                    code = parts[0].strip()
                    name = parts[3].strip()
                    nav_str = parts[4].strip()
                    date_str = parts[5].strip()
                    
                    if not code or not name or code == "Scheme Code":
                        continue
                    
                    try:
                        nav_val = float(nav_str)
                    except:
                        nav_val = 10.0 # default fallback
                        
                    # Format date: 15-Jul-2026 -> 2026-07-15
                    try:
                        d_obj = datetime.datetime.strptime(date_str, '%d-%b-%Y')
                        formatted_date = d_obj.strftime('%Y-%m-%d')
                    except:
                        formatted_date = datetime.date.today().strftime('%Y-%m-%d')
                        
                    schemes.append({
                        "amfi_code": code,
                        "scheme_name": name,
                        "category": current_category,
                        "sub_category": current_sub_category,
                        "latest_nav": nav_val,
                        "latest_date": formatted_date
                    })
        print(f"[Database Seeder] Successfully parsed {len(schemes)} active mutual fund schemes.")
        return schemes
    except Exception as e:
        print(f"[Database Seeder] Error downloading/parsing AMFI schemes file: {e}")
        return []

# Dynamic realistic portfolio pools
STOCK_POOL = [
    ("HDFC Bank Ltd", "Financial Services"), ("ICICI Bank Ltd", "Financial Services"),
    ("Reliance Industries Ltd", "Energy & Oil"), ("Infosys Ltd", "Information Technology"),
    ("Larsen & Toubro Ltd", "Construction"), ("ITC Ltd", "Consumer Goods"),
    ("Tata Consultancy Services Ltd", "Information Technology"), ("Bharti Airtel Ltd", "Telecommunications"),
    ("Axis Bank Ltd", "Financial Services"), ("Maruti Suzuki India Ltd", "Automobile"),
    ("State Bank of India", "Financial Services"), ("Kotak Mahindra Bank Ltd", "Financial Services"),
    ("Hindustan Unilever Ltd", "Consumer Goods"), ("ITC Ltd", "Consumer Goods"),
    ("L&T Ltd", "Construction"), ("Tata Motors Ltd", "Automobile")
]

DEBT_POOL = [
    ("Government of India Securities (G-Sec)", "Sovereign Debt"),
    ("91 Days Treasury Bills (GOI)", "Sovereign Debt"),
    ("182 Days Treasury Bills (GOI)", "Sovereign Debt"),
    ("HDFC Bank Commercial Paper", "Short Term Debt"),
    ("SIDBI Certificate of Deposit", "Short Term Debt"),
    ("NABARD Commercial Paper", "Short Term Debt"),
    ("NHAI Corporate Bonds", "Corporate Debt"),
    ("State Bank of India Bonds", "Corporate Debt"),
    ("Cash and Cash Equivalents", "Cash")
]

def generate_random_portfolio(category):
    pool = DEBT_POOL if category in ["Debt", "Liquid"] else STOCK_POOL
    # Pick 6 to 10 assets
    k = random.randint(6, 10)
    assets = random.sample(pool, min(k, len(pool)))
    
    # Random allocations summing to 100
    weights = [random.randint(5, 20) for _ in range(len(assets))]
    total = sum(weights)
    allocations = [round((w / total) * 100, 2) for w in weights]
    
    # Adjust last one to ensure exact 100% sum
    diff = round(100.0 - sum(allocations), 2)
    allocations[-1] = round(allocations[-1] + diff, 2)
    
    return [(assets[i][0], assets[i][1], allocations[i]) for i in range(len(assets))]

def seed_data():
    print("[Database Seeder] Checking mutual funds database status...")
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Verify if we already have the expanded database seeded
    try:
        cursor.execute("SELECT COUNT(*) FROM funds")
        funds_count = cursor.fetchone()[0]
        # If we have more than 1000 schemes, we already have the full list
        if funds_count > 1000:
            print(f"[Database Seeder] Funds database contains {funds_count} schemes. Skipping seeder.")
            conn.close()
            return
    except Exception as e:
        print(f"[Database Seeder] Checking funds table error: {e}")
    
    print("[Database Seeder] Beginning complete active mutual funds migration...")
    
    # Parse schemes from AMFI portal
    schemes = parse_amfi_nav_file()
    if not schemes:
        print("[Database Seeder] AMFI download failed or returned empty. Seeding flagship mutual fund fallbacks...")
        seed_fallback_funds()
        conn.close()
        return
        
    print("[Database Seeder] Cleaving legacy schemes...")
    cursor.execute("DELETE FROM funds")
    cursor.execute("DELETE FROM fund_portfolio")
    cursor.execute("DELETE FROM fund_nav_history")
    conn.commit()
    
    # Popular flagship codes to pre-seed with complete NAV histories
    flagship_codes = {
        "120586", "118989", "118778", "122639", "120823", "119609", "120197",
        "120237", "120716", "119062", "118825", "120146", "120542", "120018",
        "119819", "119771", "120828", "120244", "118721", "120166"
    }
    
    # Managers pool for dynamic generation
    managers = [
        "Rajeev Thakkar", "Chirag Setalvad", "Samir Rachh", "Sohini Andani", "Anish Tawakley",
        "Rama Iyer Srinivasan", "Rahul Goswami", "Sanjeev Sharma", "Sankaran Naren", "Jinesh Gopani"
    ]
    
    # Risk ratings mapping based on category keywords
    def get_risk_rating(category, sub_cat):
        c = category.lower()
        s = sub_cat.lower()
        if "liquid" in s or "overnight" in s:
            return "Low"
        if "debt" in c or "money market" in s:
            return "Moderate"
        if "hybrid" in c:
            return "High"
        return "Very High"
        
    print("[Database Seeder] Storing schemes in database...")
    batch_funds = []
    batch_portfolios = []
    batch_navs = []
    
    for s in schemes:
        code = s["amfi_code"]
        name = s["scheme_name"]
        cat = s["category"]
        sub = s["sub_category"]
        nav = s["latest_nav"]
        date = s["latest_date"]
        
        # Populate defaults/simulations for metadata
        risk = get_risk_rating(cat, sub)
        exp = round(random.uniform(0.15, 2.2), 2)
        exit_ld = "Nil" if cat in ["Debt", "Liquid"] else "1% if redeemed within 1 year"
        mgr = random.choice(managers)
        aum = round(random.uniform(50.0, 48000.0), 2)
        stars = random.randint(3, 5)
        
        batch_funds.append((
            code, name, cat, sub, risk, exp, exit_ld, mgr, aum, stars, "2013-01-01"
        ))
        
        # Insert latest nav
        batch_navs.append((code, date, nav))
        
        # Generate and append portfolio holdings
        holdings = generate_random_portfolio(cat)
        for asset, sector, weight in holdings:
            batch_portfolios.append((code, asset, sector, weight))
            
    # Executemany insertions in batches to be fast
    cursor.executemany('''
        INSERT OR REPLACE INTO funds (
            amfi_code, scheme_name, category, sub_category, risk_rating,
            expense_ratio, exit_load, fund_manager, aum, star_rating, launch_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', batch_funds)
    
    cursor.executemany('''
        INSERT OR REPLACE INTO fund_portfolio (
            amfi_code, asset_name, sector, allocation_pct
        ) VALUES (?, ?, ?, ?)
    ''', batch_portfolios)
    
    cursor.executemany('''
        INSERT OR REPLACE INTO fund_nav_history (
            amfi_code, nav_date, nav_price
        ) VALUES (?, ?, ?)
    ''', batch_navs)
    
    conn.commit()
    print("[Database Seeder] All scheme structures successfully written.")
    
    # 4. Pre-seed flagship scheme histories
    start_date = datetime.date(2021, 1, 1)
    end_date = datetime.date(2025, 12, 31)
    
    for code in flagship_codes:
        # Check if this flagship scheme is present in our list
        cursor.execute("SELECT scheme_name FROM funds WHERE amfi_code = ?", (code,))
        row = cursor.fetchone()
        if not row:
            continue
        
        name = row['scheme_name']
        print(f"[Database Seeder] Seeding historical NAV for flagship fund: {name} ({code})")
        
        navs = fetch_real_nav_history(code)
        if not navs:
            # simulated fallback
            navs = generate_nav_history(random.uniform(20.0, 150.0), 0.15, 0.15, start_date, end_date)
            
        cursor.executemany('''
            INSERT OR REPLACE INTO fund_nav_history (
                amfi_code, nav_date, nav_price
            ) VALUES (?, ?, ?)
        ''', [(code, d, p) for d, p in navs])
        
    conn.commit()
    
    # 5. Update performance metrics for seeded funds in DB
    print("[Database Seeder] Pre-calculating performance metrics for flagship schemes...")
    import services.fund_analytics
    
    for code in flagship_codes:
        stats = services.fund_analytics.get_analytics(code)
        if stats:
            cursor.execute('''
                UPDATE funds 
                SET return_1y = ?, return_3y = ?, return_5y = ?
                WHERE amfi_code = ?
            ''', (stats["return_1y"], stats["return_3y"], stats["return_5y"], code))
            
    conn.commit()
    conn.close()
    print("[Database Seeder] Seeding complete! Database populated successfully.")

if __name__ == '__main__':
    seed_data()
