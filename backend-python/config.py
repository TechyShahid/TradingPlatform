import os
import secrets
import urllib.parse
import urllib.request
import json


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

# --- App Config ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'trading_platform_dev_secret_key_92931')

# --- Google OAuth2 Configuration ---
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
