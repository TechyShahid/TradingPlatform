"""
ProTrade Platform — Flask Application Entry Point.
Registers all feature Blueprints and starts background tasks.
"""
import os
import threading
from flask import Flask
from flask_cors import CORS
import config
import database

# --- Create Flask App ---
app = Flask(__name__)
CORS(app)
app.secret_key = config.SECRET_KEY

# --- Register Blueprints ---
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.volume import volume_bp
from routes.deals import deals_bp
from routes.news import news_bp
from routes.ipo import ipo_bp
from routes.funds import funds_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(volume_bp)
app.register_blueprint(deals_bp)
app.register_blueprint(news_bp)
app.register_blueprint(ipo_bp)
app.register_blueprint(funds_bp)


# --- Disable Caching in Development ---
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


if __name__ == '__main__':
    # Ensure database is initialized with all tables
    database.init_db()

    # Ensure templates folder exists
    if not os.path.exists('templates'):
        os.makedirs('templates')
        
    # Start background tasks preventing double initialization by Flask reloader
    if not os.environ.get('WERKZEUG_RUN_MAIN') and app.debug:
        print("[Background Tasks] Waiting for Flask child process before spinning threads...")
    else:
        from services.seeders import background_news_crawler_task, background_seeding_task
        
        # Start news crawler
        crawler_thread = threading.Thread(target=background_news_crawler_task, daemon=True)
        crawler_thread.start()

        # Start database seeder
        seeder_thread = threading.Thread(target=background_seeding_task, daemon=True)
        seeder_thread.start()
        
    port = int(os.environ.get('PORT', 8083))
    is_render = os.environ.get('RENDER') is not None
    debug_mode = not is_render
    app.run(debug=debug_mode, port=port, host='0.0.0.0')
