import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from database import fetch_all, execute_query
from auth_utils import roles_required, current_role

store_bp = Blueprint('store_bp', __name__)

@store_bp.route('/stores', methods=['GET', 'POST'])
@roles_required('OWNER', 'MANAGER', 'EMPLOYEE')
def stores():
    if request.method == 'POST':
        if current_role() != 'OWNER':
            abort(403)
        store_id = 'STORE-' + uuid.uuid4().hex[:12]
        store_name = request.form.get('store_name', '').strip()
        location = request.form.get('location', '').strip()
        store_type = request.form.get('store_type', 'RETAIL')
        if not store_name or not location:
            flash('Please enter store name and location.', 'error')
            return redirect(url_for('store_bp.stores'))
        try:
            execute_query("INSERT INTO Store (store_id, store_name, location, store_type, status) VALUES (%s, %s, %s, %s, 'ACTIVE')",
                          (store_id, store_name, location, store_type))
            flash('Store added successfully.', 'success')
        except Exception as error:
            flash(f'Unable to add store: {error}', 'error')
        return redirect(url_for('store_bp.stores'))
    stores_list = fetch_all('SELECT * FROM Store ORDER BY created_at DESC')
    return render_template('stores.html', stores=stores_list)
