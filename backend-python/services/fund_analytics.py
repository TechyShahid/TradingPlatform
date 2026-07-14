"""
Mutual Fund analytics — CAGR calculations, NAV lookups, and risk metrics.
Used by routes/funds.py for fund detail, comparison, and prediction endpoints.
"""
import math
import datetime
import database

RISK_FREE_RATE = 0.06


def calculate_cagr(start_val, end_val, years):
    if not start_val or not end_val or start_val <= 0 or end_val <= 0 or years <= 0:
        return 0.0
    return (end_val / start_val) ** (1 / years) - 1


def get_nav_closest_to_date(cursor, amfi_code, target_date_str):
    cursor.execute('''
        SELECT nav_price FROM fund_nav_history 
        WHERE amfi_code = ? AND nav_date <= ? 
        ORDER BY nav_date DESC LIMIT 1
    ''', (amfi_code, target_date_str))
    row = cursor.fetchone()
    if row:
        return row['nav_price']
    cursor.execute('''
        SELECT nav_price FROM fund_nav_history 
        WHERE amfi_code = ? 
        ORDER BY nav_date ASC LIMIT 1
    ''', (amfi_code,))
    row = cursor.fetchone()
    return row['nav_price'] if row else None


def get_analytics(amfi_code):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT nav_price, nav_date FROM fund_nav_history 
        WHERE amfi_code = ? 
        ORDER BY nav_date DESC LIMIT 1
    ''', (amfi_code,))
    latest = cursor.fetchone()
    if not latest:
        conn.close()
        return None
        
    latest_price = latest['nav_price']
    latest_date_str = latest['nav_date']
    latest_date = datetime.datetime.strptime(latest_date_str, '%Y-%m-%d')
    
    date_1y = (latest_date - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
    date_3y = (latest_date - datetime.timedelta(days=3 * 365)).strftime('%Y-%m-%d')
    date_5y = (latest_date - datetime.timedelta(days=5 * 365)).strftime('%Y-%m-%d')
    
    price_1y = get_nav_closest_to_date(cursor, amfi_code, date_1y)
    price_3y = get_nav_closest_to_date(cursor, amfi_code, date_3y)
    price_5y = get_nav_closest_to_date(cursor, amfi_code, date_5y)
    
    ret_1y = calculate_cagr(price_1y, latest_price, 1.0)
    ret_3y = calculate_cagr(price_3y, latest_price, 3.0)
    ret_5y = calculate_cagr(price_5y, latest_price, 5.0)
    
    cursor.execute('''
        SELECT nav_price FROM fund_nav_history 
        WHERE amfi_code = ? AND nav_date >= ? 
        ORDER BY nav_date ASC
    ''', (amfi_code, date_1y))
    prices = [row['nav_price'] for row in cursor.fetchall()]
    
    std_dev = 0.0
    sharpe = 0.0
    beta = 1.0
    alpha = 0.0
    
    if len(prices) > 2:
        daily_returns = []
        for i in range(1, len(prices)):
            daily_returns.append((prices[i] / prices[i-1]) - 1)
            
        avg_ret = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        daily_std = variance ** 0.5
        std_dev = daily_std * (250 ** 0.5)
        
        if std_dev > 0:
            sharpe = (ret_1y - RISK_FREE_RATE) / std_dev
            
        cursor.execute("SELECT sub_category FROM funds WHERE amfi_code = ?", (amfi_code,))
        sub_cat_row = cursor.fetchone()
        sub_cat = sub_cat_row['sub_category'] if sub_cat_row else "Large Cap"
        if "Small Cap" in sub_cat:
            beta = 1.25
        elif "Mid Cap" in sub_cat:
            beta = 1.12
        elif "Liquid" in sub_cat:
            beta = 0.05
        elif "Hybrid" in sub_cat:
            beta = 0.65
        else:
            beta = 0.98
            
        market_return = 0.125
        alpha = ret_1y - (RISK_FREE_RATE + beta * (market_return - RISK_FREE_RATE))
        
    conn.close()
    
    return {
        "current_price": latest_price,
        "latest_date": latest_date_str,
        "return_1y": round(ret_1y * 100, 2),
        "return_3y": round(ret_3y * 100, 2),
        "return_5y": round(ret_5y * 100, 2),
        "volatility": round(std_dev * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "beta": beta,
        "alpha": round(alpha * 100, 2)
    }
