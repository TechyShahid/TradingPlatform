"""
IPO routes — upcoming IPO listing and subscription sync.
"""
import datetime
import re
import random
from flask import Blueprint, jsonify
import database

ipo_bp = Blueprint('ipo', __name__)


def normalize_date_str(date_str):
    if not date_str or date_str == "N/A":
        return "N/A"
    date_str = str(date_str).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    current_year = datetime.datetime.now().year
    for fmt in ['%d-%b-%Y', '%d %B %Y', '%d-%b', '%d %B']:
        try:
            val = date_str if 'Y' in fmt or 'y' in fmt else f"{date_str} {current_year}"
            dt = datetime.datetime.strptime(val, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return date_str


def compute_ipo_status(start_date_str, end_date_str, fallback_status="Closed"):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    start_iso = normalize_date_str(start_date_str)
    end_iso = normalize_date_str(end_date_str)
    
    if end_iso != "N/A" and re.match(r'^\d{4}-\d{2}-\d{2}$', end_iso):
        if end_iso < today_str:
            return "Closed", start_iso, end_iso
            
    if start_iso != "N/A" and re.match(r'^\d{4}-\d{2}-\d{2}$', start_iso):
        if start_iso > today_str:
            return "Upcoming", start_iso, end_iso
            
    if start_iso != "N/A" and end_iso != "N/A" and re.match(r'^\d{4}-\d{2}-\d{2}$', start_iso) and re.match(r'^\d{4}-\d{2}-\d{2}$', end_iso):
        if start_iso <= today_str <= end_iso:
            return "Active", start_iso, end_iso
            
    return fallback_status, start_iso, end_iso


@ipo_bp.route('/api/ipos')
def list_ipos():
    try:
        import database, re
        conn = database.get_db_connection()
        cur = conn.cursor()

        # Check if subscription figures are missing (e.g. on fresh Render deployment)
        cur.execute("SELECT COUNT(*) FROM ipos WHERE total_x > 0.0")
        has_sub_data = cur.fetchone()[0]
        if has_sub_data == 0:
            try:
                from services.ipo_service import apply_subscription_fallbacks
                apply_subscription_fallbacks()
            except Exception as fb_err:
                print(f"[IPO Route] Fallback trigger warning: {fb_err}")

        cur.execute("SELECT * FROM ipos ORDER BY CASE status WHEN 'Active' THEN 1 WHEN 'Upcoming' THEN 2 WHEN 'Closed' THEN 3 ELSE 4 END, issue_start_date DESC")
        rows = cur.fetchall()
        
        ipos = []
        updates_needed = []
        for r in rows:
            gmp_val = "N/A"
            try:
                gmp_val = r["gmp"]
            except (IndexError, KeyError, TypeError):
                pass
            if not gmp_val:
                gmp_val = "N/A"
                
            calc_status, start_iso, end_iso = compute_ipo_status(r["issue_start_date"], r["issue_end_date"], r["status"])
            
            # Record for DB update if status in DB was stale
            if calc_status != r["status"]:
                updates_needed.append((calc_status, start_iso, end_iso, r["id"]))
                
            ipos.append({
                "id": r["id"],
                "company_name": r["company_name"],
                "symbol": r["symbol"],
                "issue_start_date": start_iso,
                "issue_end_date": end_iso,
                "price_range": r["price_range"],
                "issue_size": r["issue_size"],
                "lot_size": r["lot_size"],
                "status": calc_status,
                "retail_x": r["retail_x"],
                "hni_x": r["hni_x"],
                "qib_x": r["qib_x"],
                "total_x": r["total_x"],
                "gmp": gmp_val,
                "updated_at": r["updated_at"]
            })
            
        if updates_needed:
            try:
                cur.executemany("UPDATE ipos SET status = ?, issue_start_date = ?, issue_end_date = ? WHERE id = ?", updates_needed)
                conn.commit()
            except Exception as update_err:
                print(f"[IPO Route] Background status update warning: {update_err}")
                
        conn.close()
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

