from flask import Blueprint, jsonify, request
import database

deals_bp = Blueprint('deals', __name__)


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


# SQL helper to sort DD-MMM-YYYY dates chronologically
DATE_SORT_SQL = """
    SUBSTR(deal_date, -4) DESC,
    CASE SUBSTR(deal_date, 4, 3)
        WHEN 'JAN' THEN '01' WHEN 'FEB' THEN '02' WHEN 'MAR' THEN '03'
        WHEN 'APR' THEN '04' WHEN 'MAY' THEN '05' WHEN 'JUN' THEN '06'
        WHEN 'JUL' THEN '07' WHEN 'AUG' THEN '08' WHEN 'SEP' THEN '09'
        WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12'
    END DESC,
    CAST(SUBSTR(deal_date, 1, 2) AS INTEGER) DESC
"""

# SQL helper to convert DD-MMM-YYYY to sortable YYYY-MM-DD
DATE_CONVERT_SQL = """
    SUBSTR(deal_date, 8, 4) || '-' ||
    CASE SUBSTR(deal_date, 4, 3)
        WHEN 'JAN' THEN '01' WHEN 'FEB' THEN '02' WHEN 'MAR' THEN '03'
        WHEN 'APR' THEN '04' WHEN 'MAY' THEN '05' WHEN 'JUN' THEN '06'
        WHEN 'JUL' THEN '07' WHEN 'AUG' THEN '08' WHEN 'SEP' THEN '09'
        WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12'
    END || '-' ||
    SUBSTR(deal_date, 1, 2)
"""


@deals_bp.route('/api/deals/bulk')
def get_bulk_deals():
    try:
        symbol = request.args.get('symbol', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        
        query = "SELECT * FROM bulk_deals WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol REGEXP ?"
            params.append(symbol)
            
        if start_date:
            query += f" AND {DATE_CONVERT_SQL} >= ?"
            params.append(start_date)
            
        if end_date:
            query += f" AND {DATE_CONVERT_SQL} <= ?"
            params.append(end_date)
            
        query += f" ORDER BY {DATE_SORT_SQL} LIMIT 500"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deals_bp.route('/api/deals/block')
def get_block_deals():
    try:
        symbol = request.args.get('symbol', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        
        query = "SELECT * FROM block_deals WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol REGEXP ?"
            params.append(symbol)
            
        if start_date:
            query += f" AND {DATE_CONVERT_SQL} >= ?"
            params.append(start_date)
            
        if end_date:
            query += f" AND {DATE_CONVERT_SQL} <= ?"
            params.append(end_date)
            
        query += f" ORDER BY {DATE_SORT_SQL} LIMIT 500"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deals_bp.route('/api/fundamentals/compounders')
def get_consistent_compounders():
    try:
        conn = database.get_db_connection()
        conn.row_factory = dict_factory
        cur = conn.cursor()
        cur.execute("SELECT * FROM consistent_compounders ORDER BY avg_3yr_growth_pct DESC")
        rows = cur.fetchall()
        
        if not rows:
            try:
                from services.seeders import seed_fallback_deals_and_compounders
                seed_fallback_deals_and_compounders()
                cur.execute("SELECT * FROM consistent_compounders ORDER BY avg_3yr_growth_pct DESC")
                rows = cur.fetchall()
            except Exception as fb_err:
                print(f"[Deals Route] Compounders fallback trigger notice: {fb_err}")
                
        conn.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deals_bp.route('/api/deals/potential_growth')
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


@deals_bp.route('/api/fundamentals/growth')
def get_fundamental_growth():
    try:
        import analyze_fundamentals
        results = analyze_fundamentals.find_growth_stocks()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deals_bp.route('/api/ai/predict')
def ai_predict_growth():
    try:
        import ai_analyzer
        # Llama 3 analysis might take 10-30 seconds depending on hardware
        predictions = ai_analyzer.predict_growth_stocks()
        return jsonify(predictions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deals_bp.route('/api/deals/sync', methods=['POST'])
def sync_deals():
    """Trigger a live fetch of bulk and block deals from NSE."""
    try:
        import fetch_nse_deals
        result = fetch_nse_deals.fetch_and_store_deals(period="1M")
        return jsonify({
            'status': 'success',
            'new_bulk_deals': result.get('new_bulk_deals', 0),
            'new_block_deals': result.get('new_block_deals', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
