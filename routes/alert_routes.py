from flask import Blueprint, render_template, redirect, url_for, flash
from database import fetch_all
from services.shrinkage_service import detect_shrinkage
from auth_utils import roles_required


alert_bp = Blueprint("alert_bp", __name__)


@alert_bp.route("/alerts")
@roles_required("OWNER", "MANAGER")
def alerts():

    alerts_list = fetch_all(
        """
        SELECT
            a.*,
            s.store_name,
            p.product_name
        FROM ShrinkageAlert a
        JOIN Store s ON a.store_id = s.store_id
        JOIN SKU p ON a.sku_id = p.sku_id
        ORDER BY a.created_at DESC
        """
    )

    return render_template(
        "alerts.html",
        alerts=alerts_list
    )


@alert_bp.route("/detect-shrinkage", methods=["POST"])
@roles_required("OWNER", "MANAGER")
def run_detection():

    try:

        number_of_alerts = detect_shrinkage()

        flash(
            f"Detection completed. {number_of_alerts} new alert(s) created.",
            "success"
        )

    except Exception as error:

        flash(f"Detection failed: {error}", "error")

    return redirect(url_for("alert_bp.alerts"))