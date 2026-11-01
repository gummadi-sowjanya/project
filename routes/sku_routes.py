import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from database import fetch_all, execute_query
from auth_utils import roles_required, current_role

sku_bp = Blueprint('sku_bp', __name__)

@sku_bp.route('/products', methods=['GET', 'POST'])
@roles_required('OWNER', 'MANAGER', 'EMPLOYEE')
def products():
    if request.method == 'POST':
        if current_role() not in ('OWNER', 'MANAGER'):
            abort(403)
        sku_id = 'SKU-' + uuid.uuid4().hex[:12]
        product_name = request.form.get('product_name', '').strip()
        category = request.form.get('category', '').strip()
        unit_price = request.form.get('unit_price', '0')
        unit_of_measure = request.form.get('unit_of_measure', 'UNIT')
        try:
            if not product_name or not category:
                raise ValueError('Product name and category are required.')
            price = float(unit_price)
            if price < 0:
                raise ValueError('Price cannot be negative.')
            execute_query("""INSERT INTO SKU (sku_id, product_name, category, unit_price, unit_of_measure, status)
                           VALUES (%s, %s, %s, %s, %s, 'ACTIVE')""",
                          (sku_id, product_name, category, price, unit_of_measure))
            flash('Product added successfully.', 'success')
        except Exception as error:
            flash(f'Unable to add product: {error}', 'error')
        return redirect(url_for('sku_bp.products'))
    products_list = fetch_all('SELECT * FROM SKU ORDER BY product_name')
    return render_template('products.html', products=products_list)
