"""
Admin routes — user management and entitlement control.
"""
from flask import Blueprint, jsonify, request, session
import database
from routes.auth import check_admin_entitlement

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/api/admin/users')
def list_admin_users():
    if not check_admin_entitlement():
        return jsonify({'error': 'Forbidden: stock_admin entitlement required'}), 403
        
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, name, last_login, entitlements FROM users ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        
        users_list = []
        for r in rows:
            users_list.append({
                'id': r['id'],
                'email': r['email'],
                'name': r['name'],
                'last_login': r['last_login'],
                'entitlements': r['entitlements'] or ''
            })
        return jsonify(users_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/admin/users/update', methods=['POST'])
def update_user_entitlements():
    if not check_admin_entitlement():
        return jsonify({'error': 'Forbidden: stock_admin entitlement required'}), 403
        
    data = request.json or {}
    user_email = data.get('email')
    new_entitlements = data.get('entitlements', '')
    
    if not user_email:
        return jsonify({'error': 'User email required'}), 400
        
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        
        # Prevent self-demotion to avoid locking out the admin
        current_user = session.get('user')
        if current_user and current_user['email'] == user_email:
            if 'stock_admin' not in [e.strip() for e in new_entitlements.split(',')]:
                conn.close()
                return jsonify({'error': 'Cannot demote yourself to prevent lockout!'}), 400
                
        cursor.execute("UPDATE users SET entitlements = ? WHERE email = ?", (new_entitlements, user_email))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Entitlements updated for {user_email}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
