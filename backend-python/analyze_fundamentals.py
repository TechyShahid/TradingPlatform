import database
import sqlite3

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def find_growth_stocks():
    conn = database.get_db_connection()
    conn.row_factory = dict_factory
    cur = conn.cursor()
    
    # Fetch all fundamental data sorted by symbol and year (descending so we have latest first)
    cur.execute("SELECT * FROM fundamentals ORDER BY symbol, year DESC")
    rows = cur.fetchall()
    
    conn.close()
    
    company_data = {}
    for row in rows:
        symbol = row['symbol']
        if symbol not in company_data:
            company_data[symbol] = []
        company_data[symbol].append(row)
        
    growth_stocks = []
    
    for symbol, records in company_data.items():
        if len(records) < 2:
            continue # Need at least 2 years of data to calculate growth
            
        latest = records[0]
        previous = records[1]
        
        latest_rev = latest['total_revenue'] or 0.0
        prev_rev = previous['total_revenue'] or 0.0
        
        latest_profit = latest['net_income'] or 0.0
        prev_profit = previous['net_income'] or 0.0
        
        latest_ebitda = latest['ebitda'] or 0.0
        
        # Criteria 1: Positive EBITDA currently
        if latest_ebitda <= 0:
            continue
            
        # Criteria 2: Revenue Growth > 10% YoY
        if prev_rev <= 0:
            continue
            
        rev_growth = (latest_rev - prev_rev) / prev_rev * 100
        
        if rev_growth > 10.0:
            # Criteria 3: Profit Growth (or turn around to profit)
            profit_growth = 0
            if prev_profit > 0:
                profit_growth = (latest_profit - prev_profit) / prev_profit * 100
                
            growth_stocks.append({
                'symbol': symbol,
                'latest_year': latest['year'],
                'revenue_growth_pct': round(rev_growth, 2),
                'profit_growth_pct': round(profit_growth, 2) if prev_profit > 0 else "Turnaround",
                'latest_revenue': latest_rev,
                'latest_net_income': latest_profit,
                'latest_ebitda': latest_ebitda
            })
            
    # Sort by revenue growth
    growth_stocks.sort(key=lambda x: x['revenue_growth_pct'], reverse=True)
    return growth_stocks

if __name__ == '__main__':
    results = find_growth_stocks()
    for r in results:
        print(f"{r['symbol']} | Rev Growth: {r['revenue_growth_pct']}% | Profit Growth: {r['profit_growth_pct']}%")
