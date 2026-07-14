"""
News routes — financial news feed with filtering and manual sync trigger.
"""
from flask import Blueprint, jsonify, request
import database

news_bp = Blueprint('news', __name__)


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


@news_bp.route('/api/news')
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


@news_bp.route('/api/news/crawl', methods=['POST'])
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
