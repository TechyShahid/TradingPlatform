"""
Volume Radar routes — NSE intraday volume spike scanner.
"""
import threading
import time
from flask import Blueprint, jsonify, request
import analyze_volume

volume_bp = Blueprint('volume', __name__)

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


from routes.auth import check_admin_entitlement

@volume_bp.route('/api/analyze', methods=['POST'])
def start_analyze():
    if not check_admin_entitlement():
        return jsonify({'error': 'Forbidden: stock_admin entitlement required'}), 403

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


@volume_bp.route('/api/analyze_price_move', methods=['POST'])
def start_analyze_price_move():
    if not check_admin_entitlement():
        return jsonify({'error': 'Forbidden: stock_admin entitlement required'}), 403
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


@volume_bp.route('/api/status')
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
