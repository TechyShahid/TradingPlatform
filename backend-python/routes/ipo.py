"""
IPO routes — upcoming IPO listing and subscription sync.
"""
import datetime
import random
from flask import Blueprint, jsonify
import database

ipo_bp = Blueprint('ipo', __name__)


@ipo_bp.route('/api/ipos')
def list_ipos():
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM ipos ORDER BY CASE status WHEN 'Active' THEN 1 WHEN 'Upcoming' THEN 2 WHEN 'Closed' THEN 3 ELSE 4 END, issue_start_date DESC")
        rows = cur.fetchall()
        conn.close()
        
        ipos = []
        for r in rows:
            gmp_val = "N/A"
            try:
                gmp_val = r["gmp"]
            except (IndexError, KeyError, TypeError):
                pass
            if not gmp_val:
                gmp_val = "N/A"
                
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
                "gmp": gmp_val,
                "updated_at": r["updated_at"]
            })
        return jsonify(ipos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ipo_bp.route('/api/ipos/sync', methods=['POST'])
def sync_ipos():
    try:
        from services.ipo_service import fetch_live_ipos
        success = fetch_live_ipos()
        if success:
            return jsonify({"success": True, "message": "Subscription multipliers refreshed from NSE India live feed."})
    except Exception as fetch_err:
        print(f"[IPO Route] Live fetch error: {fetch_err}")

    # Fallback to simulation if live fetch fails or is rate-limited
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
        return jsonify({"success": True, "message": "Subscription multipliers refreshed (Simulated fall-back)."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

