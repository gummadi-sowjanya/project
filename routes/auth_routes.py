from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database import fetch_one, execute_query


auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = fetch_one(
            """SELECT user_id, employee_role_id, username, password_hash,
                      account_role, status
               FROM UserAccount WHERE username = %s""",
            (username,)
        )

        if (not user or user['status'] != 'ACTIVE'
                or not check_password_hash(user['password_hash'], password)):
            flash('Invalid username or password, or account is inactive.', 'error')
            return render_template('login.html')

        session.clear()
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        session['account_role'] = user['account_role']
        session['employee_role_id'] = user['employee_role_id']
        flash('Login successful.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth_bp.login'))
