from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import threading
import time
import analyze_volume
import database
import sqlite3

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
                    VALUES ('dev@protrade.local', 'Dev Tester', datetime('now', 'localtime'), 'stock_admin')
                    ON CONFLICT(email) DO UPDATE SET
                        last_login=excluded.last_login,
                        entitlements=COALESCE(users.entitlements, excluded.entitlements)
                ''')
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
                VALUES (?, ?, datetime('now', 'localtime'), ?)
                ON CONFLICT(email) DO UPDATE SET
                    name=excluded.name,
                    last_login=excluded.last_login,
                    entitlements=COALESCE(users.entitlements, excluded.entitlements)
            ''', (email, name, entitlements))
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
def index():
    return render_template('index.html')

@app.route('/admin')
def admin_view():
    if not check_admin_entitlement():
        return redirect('/')
    return render_template('index.html')

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
        limit = request.args.get('limit', 100, type=int)
        
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        
        query = "SELECT * FROM stock_news WHERE 1=1"
        params = []
        
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
        
        # Calculate statistics
        cur.execute("SELECT sentiment, COUNT(*) as count FROM stock_news GROUP BY sentiment")
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

def background_seeding_task():
    print("[Database Seeder] Checking database status...")
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
