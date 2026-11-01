import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import fetch_all, execute_query
from auth_utils import roles_required

investigation_bp = Blueprint('investigation_bp', __name__)


@investigation_bp.route('/investigations', methods=['GET', 'POST'])
@roles_required('OWNER', 'MANAGER')
def investigations():
    if request.method == 'POST':
        try:
            investigation_id = 'INV-' + uuid.uuid4().hex[:16]
            alert_id = request.form.get('alert_id')
            notes = request.form.get('notes', '').strip()
            assigned_employee_id = request.form.get('assigned_employee_id') or None
            if not alert_id or not notes:
                raise ValueError('Select an alert and enter investigation notes.')
            execute_query(
                """INSERT INTO Investigation
                   (investigation_id, alert_id, assigned_employee_id, investigation_notes, status, finding, started_at)
                   VALUES (%s, %s, %s, %s, 'ASSIGNED', 'UNRESOLVED', NOW())""",
                (investigation_id, alert_id, assigned_employee_id, notes)
            )
            execute_query("UPDATE ShrinkageAlert SET status = 'UNDER_INVESTIGATION' WHERE alert_id = %s",
                          (alert_id,))
            flash('Investigation created successfully.', 'success')
        except Exception as error:
            flash(f'Unable to create investigation: {error}', 'error')
        return redirect(url_for('investigation_bp.investigations'))

    open_alerts = fetch_all("SELECT alert_id FROM ShrinkageAlert WHERE status = 'OPEN'")
    employees = fetch_all("SELECT employee_role_id, employee_name FROM EmployeeRole WHERE status = 'ACTIVE' ORDER BY employee_name")
    investigation_list = fetch_all(
        """SELECT i.*, a.loss_quantity, a.risk_score, a.alert_reason
           FROM Investigation i JOIN ShrinkageAlert a ON i.alert_id = a.alert_id
           ORDER BY i.started_at DESC"""
    )
    return render_template('investigations.html', alerts=open_alerts,
                           investigations=investigation_list, employees=employees)


@investigation_bp.route('/investigations/update/<investigation_id>', methods=['POST'])
@roles_required('OWNER', 'MANAGER')
def update_investigation(investigation_id):
    try:
        finding = request.form.get('finding')
        resolution = request.form.get('resolution', '').strip()
        allowed_findings = ('THEFT_SUSPECTED', 'DATA_ENTRY_ERROR', 'LEGITIMATE_DAMAGE',
                            'RETURN_MISMATCH', 'TRANSFER_ERROR', 'UNRESOLVED')
        if finding not in allowed_findings or not resolution:
            raise ValueError('Select a valid finding and enter resolution details.')
        existing = fetch_all('SELECT alert_id FROM Investigation WHERE investigation_id = %s',
                             (investigation_id,))
        if not existing:
            raise ValueError('Investigation not found.')
        execute_query(
            """UPDATE Investigation SET finding = %s, resolution = %s,
                      status = 'COMPLETED', completed_at = NOW()
               WHERE investigation_id = %s""",
            (finding, resolution, investigation_id)
        )
        alert_status = 'FALSE_POSITIVE' if finding in (
            'DATA_ENTRY_ERROR', 'LEGITIMATE_DAMAGE', 'RETURN_MISMATCH', 'TRANSFER_ERROR'
        ) else ('RESOLVED' if finding == 'THEFT_SUSPECTED' else 'UNDER_INVESTIGATION')
        execute_query('UPDATE ShrinkageAlert SET status = %s WHERE alert_id = %s',
                      (alert_status, existing[0]['alert_id']))
        flash('Investigation updated successfully.', 'success')
    except Exception as error:
        flash(f'Unable to update investigation: {error}', 'error')
    return redirect(url_for('investigation_bp.investigations'))
