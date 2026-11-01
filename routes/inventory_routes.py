import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import fetch_all, fetch_one, execute_query
from services.inventory_service import calculate_expected_stock
from services.shrinkage_service import detect_shrinkage
from auth_utils import roles_required


inventory_bp = Blueprint("inventory_bp", __name__)


@inventory_bp.route("/movements", methods=["GET", "POST"])
@roles_required("OWNER", "MANAGER", "EMPLOYEE")
def movements():

    if request.method == "POST":

        try:

            movement_id = "MOV-" + uuid.uuid4().hex[:16]

            store_id = request.form.get("store_id")
            sku_id = request.form.get("sku_id")
            movement_type = request.form.get("movement_type")

            # InventoryMovement.quantity is an INT column, so only
            # positive whole-unit quantities are accepted.
            quantity_text = (request.form.get("quantity") or "").strip()
            try:
                quantity_decimal = Decimal(quantity_text)
            except (InvalidOperation, TypeError):
                raise ValueError(
                    "Enter a valid quantity using whole numbers, such as 1, 2, or 10."
                )

            if not quantity_decimal.is_finite():
                raise ValueError("Quantity must be a finite whole number.")

            if quantity_decimal != quantity_decimal.to_integral_value():
                raise ValueError(
                    "Quantity must be a whole number (1, 2, 3...). "
                    "Decimal quantities such as 0.01 are not supported."
                )

            quantity = int(quantity_decimal)
            reason = request.form.get("reason", "").strip()
            movement_date = request.form.get("movement_date")

            adjustment_direction = request.form.get(
                "adjustment_direction"
            ) or None

            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")

            if movement_type == "ADJUSTMENT":
                if adjustment_direction not in ("INCREASE", "DECREASE"):
                    raise ValueError(
                        "Select INCREASE or DECREASE for an adjustment."
                    )

            else:
                adjustment_direction = None

            if movement_type == "TRANSFER_IN":
                to_store_id = store_id
                from_store_id = request.form.get("from_store_id") or None

            elif movement_type == "TRANSFER_OUT":
                from_store_id = store_id
                to_store_id = request.form.get("to_store_id") or None

            else:
                from_store_id = None
                to_store_id = None

            if movement_type in ("TRANSFER_IN", "TRANSFER_OUT"):
                if not from_store_id or not to_store_id:
                    raise ValueError(
                        "Select both the source and destination stores for a transfer."
                    )

            execute_query(
                """
                INSERT INTO InventoryMovement
                (
                    movement_id,
                    store_id,
                    sku_id,
                    movement_type,
                    quantity,
                    reason,
                    from_store_id,
                    to_store_id,
                    adjustment_direction,
                    movement_date
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    movement_id,
                    store_id,
                    sku_id,
                    movement_type,
                    quantity,
                    reason,
                    from_store_id,
                    to_store_id,
                    adjustment_direction,
                    movement_date
                )
            )

            flash("Inventory movement recorded successfully.", "success")

        except Exception as error:
            flash(f"Unable to record movement: {error}", "error")

        return redirect(url_for("inventory_bp.movements"))

    stores = fetch_all(
        "SELECT store_id, store_name FROM Store WHERE status = 'ACTIVE'"
    )

    products = fetch_all(
        "SELECT sku_id, product_name FROM SKU WHERE status = 'ACTIVE'"
    )

    movements_list = fetch_all(
        """
        SELECT
            m.*,
            s.store_name,
            p.product_name
        FROM InventoryMovement m
        JOIN Store s ON m.store_id = s.store_id
        JOIN SKU p ON m.sku_id = p.sku_id
        ORDER BY m.movement_date DESC, m.created_at DESC
        LIMIT 100
        """
    )

    return render_template(
        "movements.html",
        stores=stores,
        products=products,
        movements=movements_list
    )


@inventory_bp.route("/cycle-counts", methods=["GET", "POST"])
@roles_required("OWNER", "MANAGER", "EMPLOYEE")
def cycle_counts():

    if request.method == "POST":

        try:

            count_id = "CNT-" + uuid.uuid4().hex[:16]

            store_id = request.form.get("store_id")
            sku_id = request.form.get("sku_id")
            physical_quantity = int(
                request.form.get("physical_quantity", 0)
            )
            count_date = request.form.get("count_date")

            if physical_quantity < 0:
                raise ValueError("Physical quantity cannot be negative.")

            expected_quantity = calculate_expected_stock(
                store_id,
                sku_id,
                count_date
            )

            execute_query(
                """
                INSERT INTO CycleCount
                (
                    count_id,
                    store_id,
                    sku_id,
                    system_quantity,
                    physical_quantity,
                    counted_by,
                    count_date,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING')
                """,
                (
                    count_id,
                    store_id,
                    sku_id,
                    expected_quantity,
                    physical_quantity,
                    None,
                    count_date
                )
            )

            # Run shrinkage detection immediately after saving the count.
            # This also processes older PENDING counts that have not yet been checked.
            created_alerts = detect_shrinkage()

            if created_alerts:
                flash(
                    f"Cycle count saved. Expected stock: {expected_quantity}. "
                    f"{created_alerts} new shrinkage alert(s) generated. "
                    "Open the Alerts page to review them.",
                    "success"
                )
            else:
                flash(
                    f"Cycle count saved. Expected stock: {expected_quantity}. "
                    "No new stock-shortage alert was generated.",
                    "success"
                )

        except Exception as error:
            flash(f"Unable to save cycle count: {error}", "error")

        return redirect(url_for("inventory_bp.cycle_counts"))

    stores = fetch_all(
        "SELECT store_id, store_name FROM Store WHERE status = 'ACTIVE'"
    )

    products = fetch_all(
        "SELECT sku_id, product_name FROM SKU WHERE status = 'ACTIVE'"
    )

    counts = fetch_all(
        """
        SELECT
            c.*,
            s.store_name,
            p.product_name
        FROM CycleCount c
        JOIN Store s ON c.store_id = s.store_id
        JOIN SKU p ON c.sku_id = p.sku_id
        ORDER BY c.count_date DESC
        """
    )

    return render_template(
        "cycle_counts.html",
        stores=stores,
        products=products,
        counts=counts
    )

@inventory_bp.route("/opening-stock", methods=["GET", "POST"])
@roles_required("OWNER", "MANAGER")
def opening_stock():
    """
    Configure the initial stock balance for a store/product combination.

    Opening stock is inserted only once. After inventory movements exist,
    stock changes should be recorded as inventory movements/adjustments
    rather than rewriting the opening balance.
    """

    if request.method == "POST":
        try:
            store_id = request.form.get("store_id", "").strip()
            sku_id = request.form.get("sku_id", "").strip()
            quantity_text = request.form.get("opening_quantity", "").strip()

            if not store_id or not sku_id:
                raise ValueError("Please select both a store and a product.")

            try:
                opening_quantity = int(quantity_text)
            except (TypeError, ValueError):
                raise ValueError("Opening quantity must be a whole number.")

            if opening_quantity < 0:
                raise ValueError("Opening quantity cannot be negative.")

            store = fetch_one(
                """
                SELECT store_id
                FROM Store
                WHERE store_id = %s AND status = 'ACTIVE'
                """,
                (store_id,)
            )
            if not store:
                raise ValueError("Selected store is inactive or does not exist.")

            product = fetch_one(
                """
                SELECT sku_id
                FROM SKU
                WHERE sku_id = %s AND status = 'ACTIVE'
                """,
                (sku_id,)
            )
            if not product:
                raise ValueError("Selected product is inactive or does not exist.")

            existing = fetch_one(
                """
                SELECT inventory_id
                FROM StoreInventory
                WHERE store_id = %s AND sku_id = %s
                """,
                (store_id, sku_id)
            )

            if existing:
                raise ValueError(
                    "Opening stock is already configured for this product "
                    "in this store. Use an inventory adjustment to change "
                    "the current stock; do not overwrite the opening balance."
                )

            execute_query(
                """
                INSERT INTO StoreInventory
                    (store_id, sku_id, opening_quantity)
                VALUES (%s, %s, %s)
                """,
                (store_id, sku_id, opening_quantity)
            )

            flash("Opening stock configured successfully.", "success")

        except Exception as error:
            flash(f"Unable to configure opening stock: {error}", "error")

        return redirect(url_for("inventory_bp.opening_stock"))

    stores = fetch_all(
        """
        SELECT store_id, store_name
        FROM Store
        WHERE status = 'ACTIVE'
        ORDER BY store_name
        """
    )

    products = fetch_all(
        """
        SELECT sku_id, product_name
        FROM SKU
        WHERE status = 'ACTIVE'
        ORDER BY product_name
        """
    )

    stock_rows = fetch_all(
        """
        SELECT
            st.store_id,
            st.store_name,
            p.sku_id,
            p.product_name,
            si.opening_quantity,
            si.created_at
        FROM Store st
        CROSS JOIN SKU p
        LEFT JOIN StoreInventory si
            ON si.store_id = st.store_id
           AND si.sku_id = p.sku_id
        WHERE st.status = 'ACTIVE'
          AND p.status = 'ACTIVE'
        ORDER BY st.store_name, p.product_name
        """
    )

    return render_template(
        "opening_stock.html",
        stores=stores,
        products=products,
        stock_rows=stock_rows
    )
