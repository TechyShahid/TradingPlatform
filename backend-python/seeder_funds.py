import sqlite3
import datetime
import random
import os
import database

def generate_nav_history(start_price, annual_drift, daily_volatility, start_date, end_date):
    # Generates a realistic NAV history using a geometric Brownian motion random walk
    nav_list = []
    current_price = start_price
    curr_date = start_date
    delta = datetime.timedelta(days=1)
    
    # Pre-calculate daily drift and volatility parameters
    daily_drift = annual_drift / 250
    daily_vol = daily_volatility / (250 ** 0.5)
    
    while curr_date <= end_date:
        # Only record prices for weekdays (Mon-Fri) to simulate trading days
        if curr_date.weekday() < 5:
            shock = random.normalvariate(0, 1)
            pct_change = daily_drift + (daily_vol * shock)
            current_price = max(1.0, current_price * (1 + pct_change))
            nav_list.append((curr_date.strftime('%Y-%m-%d'), round(current_price, 4)))
        curr_date += delta
        
    return nav_list

def seed_data():
    print("[Database Seeder] Checking mutual funds database status...")
    
    # Check if we already have funds seeded
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM funds")
        funds_count = cur.fetchone()[0]
        conn.close()
        if funds_count > 0:
            print(f"[Database Seeder] Funds table already contains {funds_count} records. Skipping mutual funds seeder.")
            return
    except Exception as e:
        print(f"[Database Seeder] Error checking funds table: {e}")
        return

    print("[Database Seeder] Seeding initial mutual funds and portfolios data...")
    
    funds = [
        {
            "amfi_code": "103001",
            "scheme_name": "SBI Bluechip Fund (Direct-Growth)",
            "category": "Equity",
            "sub_category": "Large Cap",
            "risk_rating": "Very High",
            "expense_ratio": 0.85,
            "exit_load": "1% if redeemed within 1 year",
            "fund_manager": "Sohini Andani",
            "aum": 46250.0,
            "star_rating": 4,
            "launch_date": "2013-01-01",
            "drift": 0.13,
            "vol": 0.14,
            "start_price": 38.5
        },
        {
            "amfi_code": "103002",
            "scheme_name": "HDFC Mid-Cap Opportunities Fund (Direct-Growth)",
            "category": "Equity",
            "sub_category": "Mid Cap",
            "risk_rating": "Very High",
            "expense_ratio": 0.72,
            "exit_load": "1% if redeemed within 1 year",
            "fund_manager": "Chirag Setalvad",
            "aum": 68400.0,
            "star_rating": 5,
            "launch_date": "2013-01-01",
            "drift": 0.17,
            "vol": 0.17,
            "start_price": 55.0
        },
        {
            "amfi_code": "103003",
            "scheme_name": "Nippon India Small Cap Fund (Direct-Growth)",
            "category": "Equity",
            "sub_category": "Small Cap",
            "risk_rating": "Very High",
            "expense_ratio": 0.68,
            "exit_load": "1% if redeemed within 1 month",
            "fund_manager": "Samir Rachh",
            "aum": 51300.0,
            "star_rating": 5,
            "launch_date": "2013-01-01",
            "drift": 0.22,
            "vol": 0.22,
            "start_price": 42.0
        },
        {
            "amfi_code": "103004",
            "scheme_name": "Parag Parikh Flexi Cap Fund (Direct-Growth)",
            "category": "Equity",
            "sub_category": "Flexi Cap",
            "risk_rating": "Very High",
            "expense_ratio": 0.58,
            "exit_load": "2% if redeemed within 1 year, 1% within 2 years",
            "fund_manager": "Rajeev Thakkar",
            "aum": 62100.0,
            "star_rating": 5,
            "launch_date": "2013-05-24",
            "drift": 0.16,
            "vol": 0.13,
            "start_price": 28.0
        },
        {
            "amfi_code": "103005",
            "scheme_name": "Quant Active Fund (Direct-Growth)",
            "category": "Equity",
            "sub_category": "ELSS / Multi Cap",
            "risk_rating": "Very High",
            "expense_ratio": 0.75,
            "exit_load": "Nil",
            "fund_manager": "Sanjeev Sharma",
            "aum": 10500.0,
            "star_rating": 4,
            "launch_date": "2013-01-01",
            "drift": 0.19,
            "vol": 0.20,
            "start_price": 120.0
        },
        {
            "amfi_code": "103006",
            "scheme_name": "SBI Equity Hybrid Fund (Direct-Growth)",
            "category": "Hybrid",
            "sub_category": "Aggressive Hybrid",
            "risk_rating": "High",
            "expense_ratio": 0.79,
            "exit_load": "1% if redeemed within 1 year",
            "fund_manager": "Rama Iyer Srinivasan",
            "aum": 65300.0,
            "star_rating": 3,
            "launch_date": "2013-01-01",
            "drift": 0.105,
            "vol": 0.09,
            "start_price": 95.0
        },
        {
            "amfi_code": "103007",
            "scheme_name": "ICICI Prudential Liquid Fund (Direct-Growth)",
            "category": "Debt",
            "sub_category": "Liquid",
            "risk_rating": "Moderate",
            "expense_ratio": 0.20,
            "exit_load": "Graduated exit load (Max 0.007% if within 6 days)",
            "fund_manager": "Rahul Goswami",
            "aum": 42900.0,
            "star_rating": 4,
            "launch_date": "2013-01-01",
            "drift": 0.065,
            "vol": 0.008,
            "start_price": 240.0
        }
    ]
    
    portfolios = {
        "103001": [
            ("HDFC Bank Ltd", "Financial Services", 8.4),
            ("ICICI Bank Ltd", "Financial Services", 7.8),
            ("Reliance Industries Ltd", "Energy & Oil", 6.5),
            ("Infosys Ltd", "Information Technology", 5.9),
            ("Larsen & Toubro Ltd", "Construction", 4.8),
            ("ITC Ltd", "Consumer Goods", 4.2),
            ("Tata Consultancy Services Ltd", "Information Technology", 3.8),
            ("Bharti Airtel Ltd", "Telecommunications", 3.5),
            ("Axis Bank Ltd", "Financial Services", 3.2),
            ("Maruti Suzuki India Ltd", "Automobile", 2.9)
        ],
        "103002": [
            ("Indian Hotels Co Ltd", "Services", 5.8),
            ("Cholamandalam Investment & Finance", "Financial Services", 5.2),
            ("Max Financial Services Ltd", "Financial Services", 4.9),
            ("Federal Bank Ltd", "Financial Services", 4.3),
            ("Tata Communications Ltd", "Telecommunications", 3.8),
            ("Bharat Electronics Ltd", "Capital Goods", 3.5),
            ("Apollo Tyres Ltd", "Automobile", 3.1),
            ("Coforge Ltd", "Information Technology", 2.9),
            ("IDFC First Bank Ltd", "Financial Services", 2.7),
            ("Supreme Industries Ltd", "Chemicals", 2.5)
        ],
        "103003": [
            ("Tube Investments of India Ltd", "Automobile", 4.9),
            ("HDFC Bank Ltd", "Financial Services", 3.8),
            ("Kirloskar Brothers Ltd", "Capital Goods", 3.4),
            ("KPIT Technologies Ltd", "Information Technology", 3.1),
            ("Karur Vysya Bank Ltd", "Financial Services", 2.8),
            ("Kei Industries Ltd", "Capital Goods", 2.6),
            ("Apar Industries Ltd", "Capital Goods", 2.4),
            ("Multi Commodity Exchange of India", "Financial Services", 2.2),
            ("Birlasoft Ltd", "Information Technology", 2.0),
            ("Grindwell Norton Ltd", "Capital Goods", 1.9)
        ],
        "103004": [
            ("HDFC Bank Ltd", "Financial Services", 8.9),
            ("ITC Ltd", "Consumer Goods", 7.2),
            ("ICICI Bank Ltd", "Financial Services", 6.8),
            ("Microsoft Corp (US)", "Information Technology", 5.4),
            ("Alphabet Inc (US)", "Information Technology", 4.9),
            ("Bajaj Holdings & Investment Ltd", "Financial Services", 4.3),
            ("Tata Consultancy Services Ltd", "Information Technology", 3.9),
            ("Axis Bank Ltd", "Financial Services", 3.5),
            ("Maruti Suzuki India Ltd", "Automobile", 3.1),
            ("Coal India Ltd", "Energy & Oil", 2.8)
        ],
        "103005": [
            ("Reliance Industries Ltd", "Energy & Oil", 7.2),
            ("HDFC Bank Ltd", "Financial Services", 6.5),
            ("Adani Power Ltd", "Energy & Oil", 5.2),
            ("ITC Ltd", "Consumer Goods", 4.8),
            ("Steel Authority of India Ltd", "Metals & Mining", 4.1),
            ("Aurobindo Pharma Ltd", "Healthcare", 3.8),
            ("State Bank of India", "Financial Services", 3.5),
            ("Jindal Steel & Power Ltd", "Metals & Mining", 3.2),
            ("Lupin Ltd", "Healthcare", 2.8),
            ("Macrotech Developers Ltd", "Construction", 2.5)
        ],
        "103006": [
            ("HDFC Bank Ltd", "Financial Services", 5.4),
            ("ICICI Bank Ltd", "Financial Services", 4.8),
            ("Government of India Securities (G-Sec)", "Sovereign Debt", 24.5),
            ("NHAI Corporate Bonds", "Corporate Debt", 14.8),
            ("Reliance Industries Ltd", "Energy & Oil", 3.9),
            ("Infosys Ltd", "Information Technology", 3.5),
            ("Larsen & Toubro Ltd", "Construction", 3.1),
            ("State Bank of India Bonds", "Corporate Debt", 8.2),
            ("ITC Ltd", "Consumer Goods", 2.8),
            ("Axis Bank Ltd", "Financial Services", 2.5)
        ],
        "103007": [
            ("91 Days Treasury Bills (GOI)", "Sovereign Debt", 38.5),
            ("182 Days Treasury Bills (GOI)", "Sovereign Debt", 18.2),
            ("HDFC Bank Commercial Paper", "Short Term Debt", 14.5),
            ("SIDBI Certificate of Deposit", "Short Term Debt", 12.8),
            ("NABARD Commercial Paper", "Short Term Debt", 10.2),
            ("Cash and Cash Equivalents", "Cash", 5.8)
        ]
    }
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # 1. Insert Funds
    for f in funds:
        cursor.execute('''
            INSERT OR REPLACE INTO funds (
                amfi_code, scheme_name, category, sub_category, risk_rating,
                expense_ratio, exit_load, fund_manager, aum, star_rating, launch_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f["amfi_code"], f["scheme_name"], f["category"], f["sub_category"], f["risk_rating"],
            f["expense_ratio"], f["exit_load"], f["fund_manager"], f["aum"], f["star_rating"], f["launch_date"]
        ))
        
    # 2. Insert Portfolios
    for amfi_code, holdings in portfolios.items():
        for asset, sector, weight in holdings:
            cursor.execute('''
                INSERT OR REPLACE INTO fund_portfolio (
                    amfi_code, asset_name, sector, allocation_pct
                ) VALUES (?, ?, ?, ?)
            ''', (amfi_code, asset, sector, weight))
            
    # 3. Generate and Insert NAV history (5 Years: 2021-01-01 to 2025-12-31)
    start_date = datetime.date(2021, 1, 1)
    end_date = datetime.date(2025, 12, 31)
    
    for f in funds:
        print(f"[Database Seeder] Generating and seeding NAV history for {f['scheme_name']}")
        navs = generate_nav_history(f["start_price"], f["drift"], f["vol"], start_date, end_date)
        
        cursor.executemany('''
            INSERT OR REPLACE INTO fund_nav_history (
                amfi_code, nav_date, nav_price
            ) VALUES (?, ?, ?)
        ''', [(f["amfi_code"], d, p) for d, p in navs])
        
    conn.commit()
    conn.close()
    print("[Database Seeder] Mutual funds data seeded successfully.")
