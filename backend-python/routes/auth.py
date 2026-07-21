"""
Authentication routes — Google OAuth2 login flow, session management, and access control.
"""
import os
import secrets
import datetime
from flask import Blueprint, session, redirect, url_for, request, jsonify, render_template
import database
import config

auth_bp = Blueprint('auth', __name__)


# --- Global Authentication Interceptor ---
@auth_bp.before_app_request
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
        return redirect(url_for('auth.login', next=request.url))


# --- Authentication Routes ---
@auth_bp.route('/login')
def login():
    # Save redirect destination
    next_url = request.args.get('next', '/')
    session['next_url'] = next_url
    
    # Generate anti-CSRF token
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    # Generate callback URI
    redirect_uri = url_for('auth.login_callback', _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https':
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    return redirect(config.get_google_auth_url(redirect_uri, state))


@auth_bp.route('/login/callback')
def login_callback():
    # Verify state to prevent CSRF
    expected_state = session.pop('oauth_state', None)
    state = request.args.get('state')
    if not expected_state or expected_state != state:
        return "State mismatch (CSRF token verification failed)", 400
        
    code = request.args.get('code')
    if not code:
        return "Authorization code missing from provider callback", 400
        
    redirect_uri = url_for('auth.login_callback', _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https':
        redirect_uri = redirect_uri.replace('http://', 'https://')
        
    try:
        # Retrieve tokens and email info
        token_response = config.exchange_code_for_token(code, redirect_uri)
        access_token = token_response.get('access_token')
        user_info = config.get_user_info(access_token)
        
        email = user_info.get('email')
        if not email:
            return "Unable to retrieve email ID from Google profile", 400
            
        name = user_info.get('name', '')
        
        # Save or update user profile in database
        entitlements = ''
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            
            # Fetch existing entitlements to avoid overwriting them
            cursor.execute("SELECT entitlements FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            
            # Grant 'stock_admin' if it's the dev user or if it's the very first user
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


@auth_bp.route('/logout')
def logout():
    session.clear()
    return "Successfully logged out. <a href='/login'>Login again</a>"


@auth_bp.route('/api/user/profile')
def get_user_profile():
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Query database to get latest profile information
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, entitlements FROM users WHERE email = ?", (user['email'],))
        row = cursor.fetchone()
        conn.close()
        if row:
            user['name'] = row['name']
            user['entitlements'] = row['entitlements'] or ''
            session['user'] = user
    except Exception as e:
        print(f"[Database] Error updating profile info: {e}")
        
    return jsonify(user)


# --- Shared Helper ---
def check_admin_entitlement():
    """Check if the current session user has stock_admin entitlement."""
    user = session.get('user')
    if not user:
        return False
    
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


# --- Page Routes ---
@auth_bp.route('/')
@auth_bp.route('/growth')
@auth_bp.route('/deals')
@auth_bp.route('/news')
@auth_bp.route('/ipo')
@auth_bp.route('/funds')
@auth_bp.route('/ai-assistant')
def index():
    return render_template('index.html')


@auth_bp.route('/admin')
def admin_view():
    if not check_admin_entitlement():
        return redirect('/')
    return render_template('index.html')
