from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import threading
import time
import analyze_volume
import database
import sqlite3
import datetime

app = Flask(__name__)
CORS(app)

# --- OAuth2 Helper Code & Configurations ---
import secrets
import urllib.parse
import urllib.request
import json
import os
from flask import session, redirect, url_for

# --- Load .env files for local development ---
def load_env_file(dotenv_path):
    if os.path.exists(dotenv_path):
        with open(dotenv_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Load from backend-python or root workspace directory
load_env_file(os.path.join(os.path.dirname(__file__), '.env'))
load_env_file(os.path.join(os.path.dirname(__file__), '..', '.env'))

app.secret_key = os.environ.get('SECRET_KEY', 'trading_platform_dev_secret_key_92931')

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

def get_google_auth_url(redirect_uri, state):
    params = {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account"
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

def exchange_code_for_token(code, redirect_uri):
    payload = {
        "code": code,
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(GOOGLE_TOKEN_URL, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    response = urllib.request.urlopen(req)
    return json.loads(response.read().decode('utf-8'))

def get_user_info(access_token):
    req = urllib.request.Request(GOOGLE_USERINFO_URL)
    req.add_header('Authorization', f'Bearer {access_token}')
    response = urllib.request.urlopen(req)
    return json.loads(response.read().decode('utf-8'))


# --- Global Authentication Interceptor ---
@app.before_request
def restrict_access():
    # Allow authentication routes and static assets
    if request.path in ['/login', '/login/callback', '/logout'] or request.path.startswith('/static/'):
        return None
        
    # Check if user is authenticated in current session
    if not session.get('user'):
        if os.environ.get('DEV_BYPASS') == 'true':
            try:
                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (email, name, last_login, entitlements)
                    VALUES ('dev@protrade.local', 'Dev Tester', ?, 'stock_admin')
                    ON CONFLICT(email) DO UPDATE SET
                        last_login=excluded.last_login,
                        entitlements=COALESCE(users.entitlements, excluded.entitlements)
                ''', (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
                conn.commit()
                cursor.execute("SELECT entitlements FROM users WHERE email = 'dev@protrade.local'")
                row = cursor.fetchone()
                entitlements = row['entitlements'] if row else 'stock_admin'
                conn.close()
            except Exception as db_err:
                print(f"[Database] Error seeding dev user: {db_err}")
                entitlements = 'stock_admin'

            session['user'] = {
                'email': 'dev@protrade.local',
                'name': 'Dev Tester',
                'entitlements': entitlements
            }
            return None
        # For API endpoints, return 401 Unauthorized
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized', 'login_url': '/login'}), 401
            
        # For regular HTML pages, redirect to Google Login flow
        # Retain original target URL in next query param
        return redirect(url_for('login', next=request.url))


# --- Authentication Routes ---
@app.route('/login')
def login():
    # Save redirect destination
    next_url = request.args.get('next', '/')
    session['next_url'] = next_url
    
    # Generate anti-CSRF token
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    # Generate callback URI
    redirect_uri = url_for('login_callback', _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https':
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    return redirect(get_google_auth_url(redirect_uri, state))

@app.route('/login/callback')
def login_callback():
    # Verify state to prevent CSRF
    expected_state = session.pop('oauth_state', None)
    state = request.args.get('state')
    if not expected_state or expected_state != state:
        return "State mismatch (CSRF token verification failed)", 400
        
    code = request.args.get('code')
    if not code:
        return "Authorization code missing from provider callback", 400
        
    redirect_uri = url_for('login_callback', _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https':
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    try:
        # Retrieve tokens and email info
        token_response = exchange_code_for_token(code, redirect_uri)
        access_token = token_response.get('access_token')
        user_info = get_user_info(access_token)
        
        email = user_info.get('email')
        if not email:
            return "Unable to retrieve email ID from Google profile", 400
            
        name = user_info.get('name', '')
        
        # Save or update user profile in SQLite database
        entitlements = ''
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            
            # Fetch existing entitlements to avoid overwriting them
            cursor.execute("SELECT entitlements FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            
            # Grant 'stock_admin' if it's the dev user or if it's the very first user in the system
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            if row and row['entitlements'] is not None:
                entitlements = row['entitlements']
            else:
                if email == 'dev@protrade.local' or user_count == 0:
                    entitlements = 'stock_admin'
                    
            cursor.execute('''
                INSERT INTO users (email, name, last_login, entitlements)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name=excluded.name,
                    last_login=excluded.last_login,
                    entitlements=COALESCE(users.entitlements, excluded.entitlements)
            ''', (email, name, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), entitlements))
            conn.commit()
            conn.close()
            print(f"[Database] Logged user session for: {email} with entitlements: {entitlements}")
        except Exception as db_err:
            print(f"[Database] Error logging user session: {db_err}")
            
        # Initialize session profile
        session['user'] = {
            'email': email,
            'name': name,
            'entitlements': entitlements
        }
        
        # Redirect back to original resource
        next_url = session.pop('next_url', '/')
        return redirect(next_url)
    except Exception as e:
        return f"Authentication Error: {str(e)}", 500

@app.route('/logout')
def logout():
    session.clear()
    return "Successfully logged out. <a href='/login'>Login again</a>"

@app.route('/api/user/profile')
def get_user_profile():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Query database to get latest profile information (e.g. entitlements)
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, entitlements FROM users WHERE email = ?", (user['email'],))
        row = cursor.fetchone()
        conn.close()
        if row:
            user['name'] = row['name']
            user['entitlements'] = row['entitlements'] or ''
            # Update session as well
            session['user'] = user
    except Exception as e:
        print(f"[Database] Error updating profile info: {e}")
        
    return jsonify(user)

def check_admin_entitlement():
    user = session.get('user')
    if not user:
        return False
    
    # Check latest from DB to be secure
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT entitlements FROM users WHERE email = ?", (user['email'],))
        row = cursor.fetchone()
        conn.close()
        if row:
            entitlements = row['entitlements'] or ''
            return 'stock_admin' in [e.strip() for e in entitlements.split(',')]
    except Exception as e:
        print(f"[Database] Error checking admin status: {e}")
        
    # Fallback to session
    return 'stock_admin' in [e.strip() for e in user.get('entitlements', '').split(',')]

@app.route('/api/admin/users')
def list_admin_users():
    if not check_admin_entitlement():
        return jsonify({'error': 'Forbidden: stock_admin entitlement required'}), 403
        
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, name, last_login, entitlements FROM users ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        
        users_list = []
        for r in rows:
            users_list.append({
                'id': r['id'],
                'email': r['email'],
                'name': r['name'],
                'last_login': r['last_login'],
                'entitlements': r['entitlements'] or ''
            })
        return jsonify(users_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/update', methods=['POST'])
def update_user_entitlements():
    if not check_admin_entitlement():
        return jsonify({'error': 'Forbidden: stock_admin entitlement required'}), 403
        
    data = request.json or {}
    user_email = data.get('email')
    new_entitlements = data.get('entitlements', '')
    
    if not user_email:
        return jsonify({'error': 'User email required'}), 400
        
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        
        # Prevent self-demotion to avoid locking out the admin
        current_user = session.get('user')
        if current_user and current_user['email'] == user_email:
            # Check if we are removing stock_admin
            if 'stock_admin' not in [e.strip() for e in new_entitlements.split(',')]:
                conn.close()
                return jsonify({'error': 'Cannot demote yourself to prevent lockout!'}), 400
                
        cursor.execute("UPDATE users SET entitlements = ? WHERE email = ?", (new_entitlements, user_email))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Entitlements updated for {user_email}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Global state to track analysis
analysis_state = {
    'running': False,
    'progress': 0,
    'total': 0,
    'message': 'Idle',
    'last_results': None,
    'start_time': None
}

def run_analysis_task(check_trend=False, check_price_move=False):
    global analysis_state
    
    def progress_update(current, total, message):
        analysis_state['progress'] = current
        analysis_state['total'] = total
        analysis_state['message'] = message

    try:
        analysis_state['running'] = True
        analysis_state['start_time'] = time.time()
        analysis_state['message'] = "Starting analysis..."
        
        results = analyze_volume.analyze_volumes(progress_callback=progress_update, check_trend=check_trend, check_price_move=check_price_move)
        
        analysis_state['last_results'] = results
        analysis_state['message'] = "Analysis Complete"
    except Exception as e:
        analysis_state['message'] = f"Error: {str(e)}"
    finally:
        analysis_state['running'] = False

@app.route('/')
@app.route('/growth')
@app.route('/deals')
@app.route('/news')
@app.route('/ipo')
@app.route('/funds')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_view():
    if not check_admin_entitlement():
        return redirect('/')
    return render_template('index.html')

@app.route('/api/ipos')
def list_ipos():
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM ipos ORDER BY CASE status WHEN 'Active' THEN 1 WHEN 'Upcoming' THEN 2 WHEN 'Closed' THEN 3 ELSE 4 END, issue_start_date DESC")
        rows = cur.fetchall()
        conn.close()
        
        ipos = []
        for r in rows:
            ipos.append({
                "id": r["id"],
                "company_name": r["company_name"],
                "symbol": r["symbol"],
                "issue_start_date": r["issue_start_date"],
                "issue_end_date": r["issue_end_date"],
                "price_range": r["price_range"],
                "issue_size": r["issue_size"],
                "lot_size": r["lot_size"],
                "status": r["status"],
                "retail_x": r["retail_x"],
                "hni_x": r["hni_x"],
                "qib_x": r["qib_x"],
                "total_x": r["total_x"],
                "updated_at": r["updated_at"]
            })
        return jsonify(ipos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ipos/sync', methods=['POST'])
def sync_ipos():
    import random
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT symbol, retail_x, hni_x, qib_x FROM ipos WHERE status = 'Active'")
        active_ipos = cur.fetchall()
        
        for ipo in active_ipos:
            symbol = ipo["symbol"]
            new_retail = round(ipo["retail_x"] + random.uniform(0.1, 0.5), 2)
            new_hni = round(ipo["hni_x"] + random.uniform(0.1, 0.8), 2)
            new_qib = round(ipo["qib_x"] + random.uniform(0.2, 1.2), 2)
            new_total = round((new_retail * 0.35) + (new_hni * 0.15) + (new_qib * 0.50), 2)
            
            cur.execute('''
                UPDATE ipos 
                SET retail_x = ?, hni_x = ?, qib_x = ?, total_x = ?, updated_at = ?
                WHERE symbol = ?
            ''', (new_retail, new_hni, new_qib, new_total, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), symbol))
            
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Subscription multipliers refreshed."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def start_analyze():
    if analysis_state['running']:
        return jsonify({'error': 'Analysis already in progress'}), 400
    
    data = request.json or {}
    check_trend = data.get('trend_filter', False)
    
    # Reset stats
    analysis_state['progress'] = 0
    analysis_state['total'] = 0
    analysis_state['last_results'] = None
    
    thread = threading.Thread(target=run_analysis_task, args=(check_trend, False))
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/api/analyze_price_move', methods=['POST'])
def start_analyze_price_move():
    if analysis_state['running']:
        return jsonify({'error': 'Analysis already in progress'}), 400
    
    data = request.json or {}
    check_trend = data.get('trend_filter', False)
    
    # Reset stats
    analysis_state['progress'] = 0
    analysis_state['total'] = 0
    analysis_state['last_results'] = None
    
    thread = threading.Thread(target=run_analysis_task, args=(check_trend, True))
    thread.start()
    
    return jsonify({'status': 'started'})


@app.route('/api/status')
def get_status():
    elapsed = 0
    if analysis_state['start_time'] and analysis_state['running']:
        elapsed = time.time() - analysis_state['start_time']
        
    return jsonify({
        'running': analysis_state['running'],
        'progress': analysis_state['progress'],
        'total': analysis_state['total'],
        'message': analysis_state['message'],
        'results': analysis_state['last_results'],
        'elapsed': round(elapsed, 1)
    })

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@app.route('/api/deals/bulk')
def get_bulk_deals():
    try:
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        cur.execute("SELECT * FROM bulk_deals ORDER BY deal_date DESC LIMIT 500")
        rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deals/block')
def get_block_deals():
    try:
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        cur.execute("SELECT * FROM block_deals ORDER BY deal_date DESC LIMIT 500")
        rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fundamentals/compounders')
def get_consistent_compounders():
    try:
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        cur.execute("SELECT * FROM consistent_compounders ORDER BY avg_3yr_growth_pct DESC")
        rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/deals/potential_growth')
def get_potential_growth():
    try:
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        # Find stocks with multiple 'BUY' deals in bulk/block
        query = """
        SELECT symbol, security_name, COUNT(*) as buy_count, SUM(quantity_traded) as total_bought
        FROM (
            SELECT symbol, security_name, quantity_traded FROM bulk_deals WHERE buy_sell LIKE 'BUY%'
            UNION ALL
            SELECT symbol, security_name, quantity_traded FROM block_deals WHERE buy_sell LIKE 'BUY%'
        )
        GROUP BY symbol, security_name
        HAVING buy_count > 1
        ORDER BY buy_count DESC, total_bought DESC
        LIMIT 100
        """
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/fundamentals/growth')
def get_fundamental_growth():
    try:
        import analyze_fundamentals
        results = analyze_fundamentals.find_growth_stocks()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/predict')
def ai_predict_growth():
    try:
        import ai_analyzer
        # Llama 3 analysis might take 10-30 seconds depending on hardware
        predictions = ai_analyzer.predict_growth_stocks()
        return jsonify(predictions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/news')
def get_news():
    try:
        sentiment = request.args.get('sentiment')
        source = request.args.get('source')
        ticker = request.args.get('ticker')
        search = request.args.get('search')
        region = request.args.get('region')
        limit = request.args.get('limit', 100, type=int)
        
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        
        query = "SELECT * FROM stock_news WHERE 1=1"
        params = []
        
        if region and region != 'All':
            query += " AND region = ?"
            params.append(region)
        if sentiment:
            query += " AND sentiment = ?"
            params.append(sentiment)
        if source:
            query += " AND source = ?"
            params.append(source)
        if ticker:
            # Match within comma-separated ticker list
            query += " AND (',' || UPPER(ticker) || ',' LIKE ?)"
            params.append(f"%,{ticker.upper()},%")
        if search:
            query += " AND (title LIKE ? OR summary LIKE ?)"
            params.append(f"%{search}%")
            params.append(f"%{search}%")
            
        query += " ORDER BY published_at DESC LIMIT ?"
        params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Calculate statistics respecting region
        stats_query = "SELECT sentiment, COUNT(*) as count FROM stock_news WHERE 1=1"
        stats_params = []
        if region and region != 'All':
            stats_query += " AND region = ?"
            stats_params.append(region)
            
        stats_query += " GROUP BY sentiment"
        cur.execute(stats_query, stats_params)
        stats_rows = cur.fetchall()
        
        stats = {row['sentiment']: row['count'] for row in stats_rows}
        for s in ['Positive', 'Negative', 'Neutral']:
            if s not in stats:
                stats[s] = 0
                
        conn.close()
        return jsonify({
            'news': rows,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/news/crawl', methods=['POST'])
def trigger_news_crawl():
    try:
        import news_crawler
        new_count = news_crawler.crawl_all_news()
        return jsonify({
            'status': 'success',
            'new_articles_count': new_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Mutual Funds Analysis & Projections Backend Support ---
import math

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

@app.route('/api/funds')
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

@app.route('/api/funds/<amfi_code>')
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

@app.route('/api/funds/compare')
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

@app.route('/api/funds/predict')
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

def background_news_crawler_task():
    import news_crawler
    print("[News Crawler Thread] Background thread started.")
    # Run once immediately on startup
    try:
        news_crawler.crawl_all_news()
    except Exception as e:
        print(f"[News Crawler Thread] Error during startup crawl: {e}")
        
    while True:
        time.sleep(900) # Sleep for 15 minutes
        try:
            print("[News Crawler Thread] Running scheduled periodic news crawl...")
            news_crawler.crawl_all_news()
        except Exception as e:
            print(f"[News Crawler Thread] Error during scheduled crawl: {e}")
def seed_ipos_data():
    print("[Database Seeder] Seeding initial IPO tracker data...")
    ipos_data = [
        {
            "company_name": "Swiggy Limited",
            "symbol": "SWIGGY",
            "issue_start_date": "2026-11-06",
            "issue_end_date": "2026-11-08",
            "price_range": "₹371 - ₹390",
            "issue_size": "₹11,327 Cr",
            "lot_size": 38,
            "status": "Active",
            "retail_x": 1.48,
            "hni_x": 2.24,
            "qib_x": 6.02,
            "total_x": 3.59
        },
        {
            "company_name": "Acme Solar Holdings Limited",
            "symbol": "ACMESOLAR",
            "issue_start_date": "2026-11-06",
            "issue_end_date": "2026-11-08",
            "price_range": "₹275 - ₹289",
            "issue_size": "₹2,900 Cr",
            "lot_size": 51,
            "status": "Active",
            "retail_x": 3.10,
            "hni_x": 0.97,
            "qib_x": 3.54,
            "total_x": 2.75
        },
        {
            "company_name": "Niva Bupa Health Insurance Limited",
            "symbol": "NIVABUPA",
            "issue_start_date": "2026-11-07",
            "issue_end_date": "2026-11-11",
            "price_range": "₹70 - ₹74",
            "issue_size": "₹2,200 Cr",
            "lot_size": 200,
            "status": "Active",
            "retail_x": 0.85,
            "hni_x": 0.22,
            "qib_x": 1.15,
            "total_x": 0.78
        },
        {
            "company_name": "Sagility India Limited",
            "symbol": "SAGILITY",
            "issue_start_date": "2026-11-05",
            "issue_end_date": "2026-11-07",
            "price_range": "₹28 - ₹30",
            "issue_size": "₹2,106 Cr",
            "lot_size": 500,
            "status": "Closed",
            "retail_x": 11.20,
            "hni_x": 19.34,
            "qib_x": 3.52,
            "total_x": 9.07
        },
        {
            "company_name": "NTPC Green Energy Limited",
            "symbol": "NTPCGREEN",
            "issue_start_date": "2026-11-19",
            "issue_end_date": "2026-11-22",
            "price_range": "₹102 - ₹108",
            "issue_size": "₹10,000 Cr",
            "lot_size": 138,
            "status": "Upcoming",
            "retail_x": 0.0,
            "hni_x": 0.0,
            "qib_x": 0.0,
            "total_x": 0.0
        },
        {
            "company_name": "Zinka Logistics Solutions (BlackBuck)",
            "symbol": "ZINKA",
            "issue_start_date": "2026-11-13",
            "issue_end_date": "2026-11-18",
            "price_range": "₹259 - ₹273",
            "issue_size": "₹1,114 Cr",
            "lot_size": 54,
            "status": "Upcoming",
            "retail_x": 0.0,
            "hni_x": 0.0,
            "qib_x": 0.0,
            "total_x": 0.0
        }
    ]
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        for ipo in ipos_data:
            cur.execute('''
                INSERT INTO ipos (
                    company_name, symbol, issue_start_date, issue_end_date, 
                    price_range, issue_size, lot_size, status, 
                    retail_x, hni_x, qib_x, total_x, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    status=excluded.status,
                    retail_x=excluded.retail_x,
                    hni_x=excluded.hni_x,
                    qib_x=excluded.qib_x,
                    total_x=excluded.total_x,
                    updated_at=excluded.updated_at
            ''', (
                ipo["company_name"], ipo["symbol"], ipo["issue_start_date"], ipo["issue_end_date"],
                ipo["price_range"], ipo["issue_size"], ipo["lot_size"], ipo["status"],
                ipo["retail_x"], ipo["hni_x"], ipo["qib_x"], ipo["total_x"],
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
        conn.commit()
        conn.close()
        print("[Database Seeder] IPO tracker data seeded successfully.")
    except Exception as e:
        print(f"[Database Seeder] Error writing seed IPOs: {e}")

def background_seeding_task():
    print("[Database Seeder] Checking database status...")
    
    # Check and seed IPOs
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ipos")
        ipo_count = cur.fetchone()[0]
        conn.close()
        if ipo_count == 0:
            seed_ipos_data()
        else:
            print(f"[Database Seeder] IPO table contains {ipo_count} records. Skipping IPO seeder.")
    except Exception as e:
        print(f"[Database Seeder] Error checking IPO table: {e}")

    # Check and seed Mutual Funds
    try:
        import seeder_funds
        seeder_funds.seed_data()
    except Exception as e:
        print(f"[Database Seeder] Error seeding mutual funds: {e}")

    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bulk_deals")
        count = cur.fetchone()[0]
        conn.close()
    except Exception as e:
        print(f"[Database Seeder] Error checking database: {e}")
        count = 0

    if count == 0:
        print("[Database Seeder] Database is empty. Starting background seeding...")
        
        # 1. Fetch bulk/block deals
        try:
            import fetch_nse_deals
            print("[Database Seeder] Fetching bulk and block deals (1M period)...")
            fetch_nse_deals.fetch_and_store_deals(period="1M")
        except Exception as e:
            print(f"[Database Seeder] Error fetching deals: {e}")

        # 2. Fetch fundamentals for default watchlists
        try:
            import fetch_fundamentals
            print("[Database Seeder] Fetching fundamentals for default watchlist...")
            default_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
            fetch_fundamentals.fetch_fundamentals(default_symbols)
        except Exception as e:
            print(f"[Database Seeder] Error fetching fundamentals: {e}")

        # 3. Analyze compounders
        try:
            import fetch_historical_fundamentals
            print("[Database Seeder] Running compounder analysis on deals...")
            fetch_historical_fundamentals.fetch_and_analyze_compounders()
        except Exception as e:
            print(f"[Database Seeder] Error analyzing compounders: {e}")

        print("[Database Seeder] Seeding completed successfully!")
    else:
        print(f"[Database Seeder] Database already contains {count} records. Skipping seeder.")

if __name__ == '__main__':
    # Ensure database is initialized with all tables
    database.init_db()

    # Ensure templates folder exists
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
        
    # Start background tasks preventing double initialization by Flask reloader
    if not os.environ.get('WERKZEUG_RUN_MAIN') and app.debug:
        print("[Background Tasks] Waiting for Flask child process before spinning threads...")
    else:
        # Start news crawler
        crawler_thread = threading.Thread(target=background_news_crawler_task, daemon=True)
        crawler_thread.start()

        # Start database seeder
        seeder_thread = threading.Thread(target=background_seeding_task, daemon=True)
        seeder_thread.start()
        
    port = int(os.environ.get('PORT', 8083))
    is_render = os.environ.get('RENDER') is not None
    debug_mode = not is_render
    app.run(debug=debug_mode, port=port, host='0.0.0.0') # Using 0.0.0.0 to allow network access
