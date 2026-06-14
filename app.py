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

if __name__ == '__main__':
    # Ensure templates folder exists
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(debug=True, port=8083, host='0.0.0.0') # Using 0.0.0.0 to allow network access
