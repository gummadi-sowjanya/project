from flask import Flask, render_template, session
from config import Config
from database import fetch_all, fetch_one
from auth_utils import login_required
from routes.auth_routes import auth_bp
from routes.account_routes import account_bp
from routes.store_routes import store_bp
from routes.sku_routes import sku_bp
from routes.inventory_routes import inventory_bp
from routes.alert_routes import alert_bp
from routes.investigation_routes import investigation_bp
from routes.employee_routes import employee_bp
from routes.sales_routes import sales_bp
from routes.returns_routes import returns_bp

app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(auth_bp)
app.register_blueprint(account_bp)
app.register_blueprint(store_bp)
app.register_blueprint(sku_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(alert_bp)
app.register_blueprint(investigation_bp)
app.register_blueprint(employee_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(returns_bp)

@app.context_processor
def inject_user():
    return {
        'logged_in': bool(session.get('user_id')),
        'current_username': session.get('username'),
        'current_role': session.get('account_role')
    }


@app.route('/')
@login_required
def dashboard():
    role = session.get('account_role')
    stores = fetch_one("SELECT COUNT(*) AS total FROM Store")['total']
    products = fetch_one("SELECT COUNT(*) AS total FROM SKU")['total']
    movements = fetch_one("SELECT COUNT(*) AS total FROM InventoryMovement")['total']

    # Employees can open the dashboard, but alert information is restricted.
    if role in ('OWNER', 'MANAGER'):
        alerts = fetch_one(
            "SELECT COUNT(*) AS total FROM ShrinkageAlert WHERE status IN ('OPEN', 'UNDER_INVESTIGATION')"
        )['total']
        loss = fetch_one(
            "SELECT COALESCE(SUM(loss_quantity), 0) AS total FROM ShrinkageAlert WHERE status IN ('OPEN', 'UNDER_INVESTIGATION')"
        )['total']
        recent_alerts = fetch_all(
            """SELECT a.*, s.store_name, p.product_name
               FROM ShrinkageAlert a
               JOIN Store s ON a.store_id = s.store_id
               JOIN SKU p ON a.sku_id = p.sku_id
               ORDER BY a.created_at DESC LIMIT 5"""
        )
    else:
        alerts, loss, recent_alerts = None, None, []

    return render_template('dashboard.html', stores=stores, products=products,
                           movements=movements, alerts=alerts, loss=loss,
                           recent_alerts=recent_alerts)


@app.errorhandler(403)
def forbidden(_error):
    return render_template('403.html'), 403


@app.route('/health')
def health():
    return {'status': 'running'}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
