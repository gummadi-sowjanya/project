import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from database import fetch_all, execute_query
from auth_utils import roles_required, current_role

employee_bp = Blueprint('employee_bp', __name__)


@employee_bp.route('/employees', methods=['GET', 'POST'])
@roles_required('OWNER', 'MANAGER')
def employees():
    if request.method == 'POST':
        if current_role() != 'OWNER':
            abort(403)
        name = request.form.get('employee_name', '').strip()
        code = request.form.get('employee_code', '').strip()
        role_name = request.form.get('role_name', '')
        store_id = request.form.get('store_id') or None
        allowed = ('STORE_OPERATOR', 'WAREHOUSE_OPERATOR', 'ANALYST', 'MANAGER', 'ADMIN')
        try:
            if not name or not code or role_name not in allowed:
                raise ValueError('Enter employee name, employee code, and a valid role.')
            execute_query(
                """INSERT INTO EmployeeRole
                   (employee_name, employee_code, role_name, store_id, effective_from, status)
                   VALUES (%s, %s, %s, %s, %s, 'ACTIVE')""",
                (name, code, role_name, store_id, datetime.date.today())
            )
            flash('Employee added successfully. Create their login from Manage Accounts.', 'success')
        except Exception as error:
            flash(f'Unable to add employee: {error}', 'error')
        return redirect(url_for('employee_bp.employees'))

    employees_list = fetch_all(
        """SELECT e.*, s.store_name FROM EmployeeRole e
           LEFT JOIN Store s ON e.store_id = s.store_id
           ORDER BY e.employee_name"""
    )
    stores = fetch_all("SELECT store_id, store_name FROM Store WHERE status = 'ACTIVE'")
    return render_template('employees.html', employees=employees_list, stores=stores)


@employee_bp.route('/employees/status/<int:employee_id>', methods=['POST'])
@roles_required('OWNER')
def update_employee_status(employee_id):
    status = request.form.get('status')
    if status not in ('ACTIVE', 'INACTIVE'):
        flash('Invalid employee status.', 'error')
    else:
        execute_query('UPDATE EmployeeRole SET status = %s WHERE employee_role_id = %s',
                      (status, employee_id))
        execute_query('UPDATE UserAccount SET status = %s WHERE employee_role_id = %s',
                      (status, employee_id))
        flash('Employee status updated.', 'success')
    return redirect(url_for('employee_bp.employees'))

@employee_bp.route('/employees/delete/<int:employee_id>', methods=['POST'])
@roles_required('OWNER')
def delete_employee(employee_id):

    try:
        # Check whether employee has existing records
        records = fetch_all("""
            SELECT
                (SELECT COUNT(*) FROM InventoryMovement
                 WHERE employee_role_id = %s) AS movements,

                (SELECT COUNT(*) FROM CycleCount
                 WHERE counted_by = %s) AS cycle_counts,

                (SELECT COUNT(*) FROM Investigation
                 WHERE assigned_employee_id = %s) AS investigations,

                (SELECT COUNT(*) FROM EmployeeShift
                 WHERE employee_role_id = %s) AS shifts
        """, (employee_id, employee_id, employee_id, employee_id))

        employee_records = records[0]

        if any(employee_records[key] > 0 for key in
               ('movements', 'cycle_counts', 'investigations', 'shifts')):

            flash(
                'Cannot delete employee because historical records exist. '
                'Please deactivate the employee instead.',
                'error'
            )
            return redirect(url_for('employee_bp.employees'))

        # Delete linked login account first
        execute_query(
            "DELETE FROM UserAccount WHERE employee_role_id = %s",
            (employee_id,)
        )

        # Delete employee
        execute_query(
            "DELETE FROM EmployeeRole WHERE employee_role_id = %s",
            (employee_id,)
        )

        flash('Employee deleted successfully.', 'success')

    except Exception as error:
        flash(f'Unable to delete employee: {error}', 'error')

    return redirect(url_for('employee_bp.employees'))

