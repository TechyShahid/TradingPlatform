"""
Mutual Funds routes — explorer, details, comparison, and NAV prediction.
"""
import math
import datetime
from flask import Blueprint, jsonify, request
import database
from services.fund_analytics import get_analytics

funds_bp = Blueprint('funds', __name__)


@funds_bp.route('/api/funds')
def list_funds():
    category = request.args.get('category', 'All')
    search_query = request.args.get('search', '')
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM funds WHERE 1=1"
    params = []
    
    if category != 'All':
        query += " AND category = ?"
        params.append(category)
        
    if search_query:
        query += " AND (scheme_name LIKE ? OR amfi_code LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    funds_list = []
    for r in rows:
        amfi = r['amfi_code']
        stats = get_analytics(amfi)
        
        funds_list.append({
            "amfi_code": amfi,
            "scheme_name": r["scheme_name"],
            "category": r["category"],
            "sub_category": r["sub_category"],
            "risk_rating": r["risk_rating"],
            "expense_ratio": r["expense_ratio"],
            "exit_load": r["exit_load"],
            "fund_manager": r["fund_manager"],
            "aum": r["aum"],
            "star_rating": r["star_rating"],
            "launch_date": r["launch_date"],
            "stats": stats
        })
        
    conn.close()
    return jsonify(funds_list)


@funds_bp.route('/api/funds/<amfi_code>')
def fund_details(amfi_code):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM funds WHERE amfi_code = ?", (amfi_code,))
    f = cursor.fetchone()
    if not f:
        conn.close()
        return jsonify({"error": "Fund not found"}), 404
        
    fund_info = {
        "amfi_code": f["amfi_code"],
        "scheme_name": f["scheme_name"],
        "category": f["category"],
        "sub_category": f["sub_category"],
        "risk_rating": f["risk_rating"],
        "expense_ratio": f["expense_ratio"],
        "exit_load": f["exit_load"],
        "fund_manager": f["fund_manager"],
        "aum": f["aum"],
        "star_rating": f["star_rating"],
        "launch_date": f["launch_date"],
        "stats": get_analytics(amfi_code)
    }
    
    cursor.execute("SELECT asset_name, sector, allocation_pct FROM fund_portfolio WHERE amfi_code = ? ORDER BY allocation_pct DESC", (amfi_code,))
    holdings = [{"asset_name": r["asset_name"], "sector": r["sector"], "allocation_pct": r["allocation_pct"]} for r in cursor.fetchall()]
    fund_info["portfolio"] = holdings
    
    cursor.execute("SELECT nav_date, nav_price FROM fund_nav_history WHERE amfi_code = ? ORDER BY nav_date ASC", (amfi_code,))
    raw_navs = cursor.fetchall()
    
    nav_history = []
    for idx, r in enumerate(raw_navs):
        if idx % 10 == 0 or idx == len(raw_navs) - 1:
            nav_history.append({"date": r["nav_date"], "price": r["nav_price"]})
            
    fund_info["nav_history"] = nav_history
    conn.close()
    return jsonify(fund_info)


@funds_bp.route('/api/funds/compare')
def compare_funds():
    codes = request.args.getlist('codes')
    if len(codes) < 2:
        return jsonify({"error": "Select at least two schemes to compare"}), 400
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    schemes_data = []
    portfolios = {}
    
    for amfi in codes:
        cursor.execute("SELECT scheme_name, category, sub_category, expense_ratio, aum FROM funds WHERE amfi_code = ?", (amfi,))
        r = cursor.fetchone()
        if not r:
            continue
            
        stats = get_analytics(amfi)
        
        cursor.execute("SELECT asset_name, allocation_pct FROM fund_portfolio WHERE amfi_code = ?", (amfi,))
        holdings = {row["asset_name"]: row["allocation_pct"] for row in cursor.fetchall()}
        portfolios[amfi] = holdings
        
        schemes_data.append({
            "amfi_code": amfi,
            "scheme_name": r["scheme_name"],
            "category": r["category"],
            "sub_category": r["sub_category"],
            "expense_ratio": r["expense_ratio"],
            "aum": r["aum"],
            "stats": stats
        })
        
    overlap_pct = 0.0
    if len(codes) >= 2:
        p1 = portfolios.get(codes[0], {})
        p2 = portfolios.get(codes[1], {})
        common_assets = set(p1.keys()).intersection(set(p2.keys()))
        overlap_pct = sum(min(p1[asset], p2[asset]) for asset in common_assets)
        
    conn.close()
    return jsonify({
        "schemes": schemes_data,
        "overlap_pct": round(overlap_pct, 2)
    })


@funds_bp.route('/api/funds/predict')
def predict_nav():
    amfi_code = request.args.get('amfi_code')
    projection_years = int(request.args.get('years', '3'))
    
    if not amfi_code:
        return jsonify({"error": "AMFI scheme code required"}), 400
        
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT nav_date, nav_price FROM fund_nav_history WHERE amfi_code = ? ORDER BY nav_date ASC", (amfi_code,))
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 10:
        return jsonify({"error": "Insufficient NAV historical data for prediction"}), 400
        
    prices = [r["nav_price"] for r in rows]
    dates = [r["nav_date"] for r in rows]
    
    n = len(prices)
    x = list(range(n))
    y = prices
    
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(val ** 2 for val in x)
    sum_xy = sum(x[i] * y[i] for i in range(n))
    
    denominator = (n * sum_xx) - (sum_x ** 2)
    if denominator == 0:
        return jsonify({"error": "Mathematical variance error during calculation"}), 500
        
    slope = ((n * sum_xy) - (sum_x * sum_y)) / denominator
    intercept = (sum_y - (slope * sum_x)) / n
    
    residuals_sum_sq = sum((y[i] - (intercept + slope * x[i])) ** 2 for i in range(n))
    std_error = (residuals_sum_sq / (n - 2)) ** 0.5
    
    project_steps = int(projection_years * 250)
    last_nav = prices[-1]
    
    latest_date_str = dates[-1]
    latest_date = datetime.datetime.strptime(latest_date_str, '%Y-%m-%d')
    
    future_predictions = []
    delta = datetime.timedelta(days=1)
    
    future_date = latest_date
    step = 0
    while step < project_steps:
        future_date += delta
        if future_date.weekday() < 5:
            x_val = n + step
            trend_val = intercept + slope * x_val
            trend_val = max(1.0, trend_val)
            uncertainty_spread = std_error * (1.96 * (math.sqrt(1 + (step / 50))))
            
            optimistic = round(trend_val + uncertainty_spread, 4)
            pessimistic = round(max(1.0, trend_val - uncertainty_spread), 4)
            
            future_predictions.append({
                "date": future_date.strftime('%Y-%m-%d'),
                "expected": round(trend_val, 4),
                "optimistic": optimistic,
                "pessimistic": pessimistic
            })
            step += 1
            
    sampled_predictions = [future_predictions[i] for i in range(len(future_predictions)) if i % 5 == 0 or i == len(future_predictions) - 1]
    
    return jsonify({
        "amfi_code": amfi_code,
        "last_price": last_nav,
        "last_date": latest_date_str,
        "predictions": sampled_predictions
    })
