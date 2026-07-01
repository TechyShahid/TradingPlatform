from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import threading
import time
import analyze_volume
import database
import sqlite3

app = Flask(__name__)
CORS(app)

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
def index():
    return render_template('index.html')

@app.route('/growth')
def growth_page():
    return render_template('growth.html')

@app.route('/deals')
def deals_page():
    return render_template('deals.html')

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

@app.route('/news')
def news_page():
    return render_template('news.html')

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
