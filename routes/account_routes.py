import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash ,session
from werkzeug.security import generate_password_hash,check_password_hash
from database import fetch_all, fetch_one, execute_query,get_db_connection
from auth_utils import roles_required

account_bp = Blueprint('account_bp', __name__)


@account_bp.route('/accounts', methods=['GET', 'POST'])
@roles_required('OWNER')
def accounts():
    if request.method == 'POST':
        employee_role_id = request.form.get('employee_role_id') or None
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        account_role = request.form.get('account_role', '')

        try:
            if not username or len(password) < 8:
                raise ValueError('Enter a username and a password with at least 8 characters.')
            if account_role not in ('MANAGER', 'EMPLOYEE'):
                raise ValueError('Only MANAGER or EMPLOYEE accounts can be created here.')
            if not employee_role_id:
                raise ValueError('Select an employee profile for this account.')

            employee = fetch_one(
                "SELECT employee_role_id, status FROM EmployeeRole WHERE employee_role_id = %s",
                (employee_role_id,)
            )
            if not employee or employee['status'] != 'ACTIVE':
                raise ValueError('Select an active employee.')

            existing = fetch_one(
                "SELECT user_id FROM UserAccount WHERE employee_role_id = %s",
                (employee_role_id,)
            )
            if existing:
                raise ValueError('This employee already has a login account.')

            execute_query(
                """INSERT INTO UserAccount
                   (user_id, employee_role_id, username, password_hash, account_role, status)
                   VALUES (%s, %s, %s, %s, %s, 'ACTIVE')""",
                ('USR-' + uuid.uuid4().hex[:16], employee_role_id, username,
                 generate_password_hash(password), account_role)
            )
            flash('Login account created successfully.', 'success')
        except Exception as error:
            flash(f'Unable to create account: {error}', 'error')
        return redirect(url_for('account_bp.accounts'))

    employees = fetch_all(
        """SELECT e.employee_role_id, e.employee_name, e.employee_code
           FROM EmployeeRole e LEFT JOIN UserAccount u
             ON u.employee_role_id = e.employee_role_id
           WHERE e.status = 'ACTIVE' AND u.user_id IS NULL
           ORDER BY e.employee_name"""
    )
    accounts_list = fetch_all(
        """SELECT u.user_id, u.username, u.account_role, u.status,
                  e.employee_name
           FROM UserAccount u LEFT JOIN EmployeeRole e
             ON e.employee_role_id = u.employee_role_id
           ORDER BY u.created_at DESC"""
    )
    transfer_candidates = fetch_all(
    """
    SELECT user_id, username, account_role
    FROM UserAccount
    WHERE status = 'ACTIVE'
      AND account_role IN ('MANAGER', 'EMPLOYEE')
    ORDER BY username
    """
    )
    return render_template('accounts.html', employees=employees, accounts=accounts_list,  transfer_candidates=transfer_candidates)
    
@account_bp.route('/accounts/transfer-owner', methods=['POST'])
@roles_required('OWNER')
def transfer_owner():

    current_owner_id = session.get('user_id')
    new_owner_id = request.form.get('new_owner_id', '').strip()
    current_password = request.form.get('current_password', '')

    if not new_owner_id or not current_password:
        flash('Select a new Owner and enter your current password.', 'error')
        return redirect(url_for('account_bp.accounts'))

    if new_owner_id == current_owner_id:
        flash('Please select a different account.', 'error')
        return redirect(url_for('account_bp.accounts'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # START TRANSACTION BEFORE EXECUTING ANY SQL QUERY
        connection.start_transaction()

        # Verify current Owner
        cursor.execute(
            """
            SELECT user_id, password_hash, account_role, status
            FROM UserAccount
            WHERE user_id = %s
            FOR UPDATE
            """,
            (current_owner_id,)
        )

        old_owner = cursor.fetchone()

        if (
            not old_owner
            or old_owner['account_role'] != 'OWNER'
            or old_owner['status'] != 'ACTIVE'
            or not check_password_hash(
                old_owner['password_hash'], current_password
            )
        ):
            raise ValueError('Incorrect password or inactive Owner account.')

        # Check selected account
        cursor.execute(
            """
            SELECT user_id, account_role, status
            FROM UserAccount
            WHERE user_id = %s
            FOR UPDATE
            """,
            (new_owner_id,)
        )

        new_owner = cursor.fetchone()

        if (
            not new_owner
            or new_owner['status'] != 'ACTIVE'
            or new_owner['account_role'] not in ('MANAGER', 'EMPLOYEE')
        ):
            raise ValueError(
                'Select an active Manager or Employee account.'
            )

        # Activate new Owner
        cursor.execute(
            """
            UPDATE UserAccount
            SET account_role = 'OWNER',
                status = 'ACTIVE'
            WHERE user_id = %s
            """,
            (new_owner_id,)
        )

        # Deactivate previous Owner
        cursor.execute(
            """
            UPDATE UserAccount
            SET status = 'INACTIVE'
            WHERE user_id = %s
              AND account_role = 'OWNER'
              AND status = 'ACTIVE'
            """,
            (current_owner_id,)
        )

        if cursor.rowcount != 1:
            raise ValueError('Unable to deactivate the previous Owner.')

        # Save both changes together
        connection.commit()

        # Log out previous Owner
        session.clear()

        flash(
            'Ownership transferred successfully. '
            'Please log in using the new Owner account.',
            'success'
        )

        return redirect(url_for('auth_bp.login'))

    except Exception as error:
        connection.rollback()
        flash(f'Owner transfer failed: {error}', 'error')
        return redirect(url_for('account_bp.accounts'))

    finally:
        cursor.close()
        connection.close()

@account_bp.route('/accounts/update-status/<user_id>', methods=['POST'])
@roles_required('OWNER')
def update_account_status(user_id):

    status = request.form.get('status')

    if status not in ('ACTIVE', 'INACTIVE'):
        flash('Invalid account status.', 'error')
        return redirect(url_for('account_bp.accounts'))

    try:
        execute_query(
            """
            UPDATE UserAccount
            SET status = %s
            WHERE user_id = %s
              AND account_role <> 'OWNER'
            """,
            (status, user_id)
        )

        flash('Account status updated successfully.', 'success')

    except Exception as error:
        flash(f'Unable to update account status: {error}', 'error')

    return redirect(url_for('account_bp.accounts'))