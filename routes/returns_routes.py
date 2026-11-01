import uuid
from datetime import datetime
from decimal import Decimal

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)

from database import fetch_all, get_db_connection
from auth_utils import roles_required

returns_bp = Blueprint("returns_bp", __name__)


def get_expected_stock(cursor, store_id, sku_id, count_date):
    """Calculate current stock using the inventory movement ledger."""

    cursor.execute(
        """
        SELECT opening_quantity
        FROM StoreInventory
        WHERE store_id = %s AND sku_id = %s
        FOR UPDATE
        """,
        (store_id, sku_id)
    )

    inventory = cursor.fetchone()

    if not inventory:
        raise ValueError(
            f"Opening stock is not configured for product {sku_id}."
        )

    stock = Decimal(str(inventory["opening_quantity"]))

    cursor.execute(
        """
        SELECT movement_type, quantity, adjustment_direction
        FROM InventoryMovement
        WHERE store_id = %s
          AND sku_id = %s
          AND movement_date <= %s
        ORDER BY movement_date, created_at, movement_id
        """,
        (store_id, sku_id, count_date)
    )

    for movement in cursor.fetchall():
        quantity = Decimal(str(movement["quantity"]))
        movement_type = movement["movement_type"]

        if movement_type in ("RECEIPT", "TRANSFER_IN", "RETURN"):
            stock += quantity

        elif movement_type in ("SALE", "TRANSFER_OUT", "DAMAGE"):
            stock -= quantity

        elif movement_type == "ADJUSTMENT":
            if movement["adjustment_direction"] == "INCREASE":
                stock += quantity
            elif movement["adjustment_direction"] == "DECREASE":
                stock -= quantity

    if stock < 0:
        raise ValueError(
            f"Calculated stock is negative for product {sku_id}. "
            "Please check the inventory movements."
        )

    return stock


def get_sale_items(sale_id):
    """Get products from a completed sale and their remaining returnable quantities."""

    return fetch_all(
        """
        SELECT
            cs.sale_id,
            cs.store_id,
            cs.customer_id,
            csi.movement_id AS original_sale_movement_id,
            csi.sku_id,
            sku.product_name,
            csi.quantity AS sold_quantity,
            csi.selling_price,
            COALESCE(r.returned_quantity, 0) AS returned_quantity,
            (
                csi.quantity - COALESCE(r.returned_quantity, 0)
            ) AS available_quantity

        FROM CustomerSale cs

        JOIN CustomerSaleItem csi
            ON cs.sale_id = csi.sale_id

        JOIN InventoryMovement im
            ON csi.movement_id = im.movement_id
           AND im.movement_type = 'SALE'

        JOIN SKU sku
            ON csi.sku_id = sku.sku_id

        LEFT JOIN (
            SELECT
                original_sale_movement_id,
                SUM(return_quantity) AS returned_quantity
            FROM `Return`
            WHERE status <> 'REJECTED'
            GROUP BY original_sale_movement_id
        ) r
            ON r.original_sale_movement_id = csi.movement_id

        WHERE cs.sale_id = %s
          AND cs.status = 'COMPLETED'
          AND im.store_id = cs.store_id

        ORDER BY sku.product_name
        """,
        (sale_id,)
    )


@returns_bp.route("/returns", methods=["GET", "POST"])
@roles_required("OWNER", "MANAGER", "EMPLOYEE")
def returns():

    if request.method == "POST":

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            connection.start_transaction()

            sale_id = request.form.get("sale_id", "").strip()
            original_movement_id = request.form.get(
                "original_sale_movement_id", ""
            ).strip()

            replacement_sku_id = request.form.get(
                "replacement_sku_id", ""
            ).strip()

            return_reason = request.form.get("return_reason", "")
            return_condition = request.form.get(
                "return_condition", ""
            )

            try:
                return_quantity = int(
                    request.form.get("return_quantity", "0")
                )
            except (ValueError, TypeError):
                raise ValueError("Enter a valid return quantity.")

            if not sale_id or not original_movement_id:
                raise ValueError("Original sale information is missing.")

            if return_quantity <= 0:
                raise ValueError("Return quantity must be greater than zero.")

            allowed_reasons = {
                "DEFECTIVE",
                "CUSTOMER_CHANGED_MIND",
                "WRONG_PRODUCT",
                "OTHER"
            }

            if return_reason not in allowed_reasons:
                raise ValueError("Select a valid return reason.")

            if return_condition not in {"SELLABLE", "DAMAGED"}:
                raise ValueError("Select a valid returned product condition.")

            if not replacement_sku_id:
                raise ValueError("Select a replacement product.")

            # Lock the original sale and product row.
            cursor.execute(
                """
                SELECT
                    cs.sale_id,
                    cs.customer_id,
                    cs.store_id,
                    cs.status,
                    csi.movement_id,
                    csi.sku_id,
                    csi.quantity,
                    csi.selling_price,
                    sku.product_name

                FROM CustomerSale cs

                JOIN CustomerSaleItem csi
                    ON cs.sale_id = csi.sale_id

                JOIN InventoryMovement im
                    ON csi.movement_id = im.movement_id

                JOIN SKU sku
                    ON csi.sku_id = sku.sku_id

                WHERE cs.sale_id = %s
                  AND csi.movement_id = %s
                  AND im.movement_type = 'SALE'
                  AND im.store_id = cs.store_id
                  AND cs.status = 'COMPLETED'

                FOR UPDATE
                """,
                (sale_id, original_movement_id)
            )

            original = cursor.fetchone()

            if not original:
                raise ValueError(
                    "Original sale or product was not found."
                )

            # Check how much quantity has already been returned.
            cursor.execute(
                """
                SELECT COALESCE(SUM(return_quantity), 0) AS returned_quantity
                FROM `Return`
                WHERE original_sale_movement_id = %s
                  AND status <> 'REJECTED'
                """,
                (original_movement_id,)
            )

            returned = cursor.fetchone()["returned_quantity"]

            available_quantity = (
                int(original["quantity"]) - int(returned)
            )

            if return_quantity > available_quantity:
                raise ValueError(
                    f"Only {available_quantity} units can be returned."
                )

            # Get replacement product.
            cursor.execute(
                """
                SELECT sku_id, product_name, unit_price
                FROM SKU
                WHERE sku_id = %s AND status = 'ACTIVE'
                """,
                (replacement_sku_id,)
            )

            replacement = cursor.fetchone()

            if not replacement:
                raise ValueError(
                    "Replacement product is inactive or does not exist."
                )

            original_price = Decimal(str(original["selling_price"]))
            replacement_price = Decimal(str(replacement["unit_price"]))

            # No refund or additional payment functionality.
            if original_price != replacement_price:
                raise ValueError(
                    "Only products with the same selling price "
                    "can be exchanged."
                )

            sale_date = datetime.now()

            # Check replacement stock.
            available_stock = get_expected_stock(
                cursor,
                original["store_id"],
                replacement_sku_id,
                sale_date
            )

            # A sellable returned product can be reused in this exchange.
            if (
                replacement_sku_id == original["sku_id"]
                and return_condition == "SELLABLE"
            ):
                available_stock += Decimal(return_quantity)

            if available_stock < Decimal(return_quantity):
                raise ValueError(
                    f"Insufficient replacement stock. "
                    f"Available: {available_stock}."
                )

            # Get employee role ID linked to the logged-in account.
            cursor.execute(
                """
                SELECT employee_role_id
                FROM UserAccount
                WHERE user_id = %s
                """,
                (session.get("user_id"),)
            )

            account = cursor.fetchone()
            employee_role_id = (
                account["employee_role_id"] if account else None
            )

            return_id = "RET-" + uuid.uuid4().hex[:16]
            exchange_sale_id = "SALE-" + uuid.uuid4().hex[:16]

            return_movement_id = "MOV-" + uuid.uuid4().hex[:16]
            replacement_movement_id = "MOV-" + uuid.uuid4().hex[:16]

            # Create the replacement sale.
            total_amount = replacement_price * return_quantity

            cursor.execute(
                """
                INSERT INTO CustomerSale
                (
                    sale_id, customer_id, store_id,
                    employee_role_id, sale_date,
                    total_amount, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'COMPLETED')
                """,
                (
                    exchange_sale_id,
                    original["customer_id"],
                    original["store_id"],
                    employee_role_id,
                    sale_date,
                    total_amount
                )
            )

            # Record the returned product as received.
            cursor.execute(
                """
                INSERT INTO InventoryMovement
                (
                    movement_id, store_id, sku_id,
                    movement_type, quantity, reason,
                    employee_role_id, movement_date, reference_id
                )
                VALUES (%s, %s, %s, 'RETURN', %s, %s, %s, %s, %s)
                """,
                (
                    return_movement_id,
                    original["store_id"],
                    original["sku_id"],
                    return_quantity,
                    f"Product exchange return {return_id}",
                    employee_role_id,
                    sale_date,
                    return_id
                )
            )

            # If damaged, remove the received quantity from sellable stock.
            if return_condition == "DAMAGED":

                damage_movement_id = "MOV-" + uuid.uuid4().hex[:16]

                cursor.execute(
                    """
                    INSERT INTO InventoryMovement
                    (
                        movement_id, store_id, sku_id,
                        movement_type, quantity, reason,
                        employee_role_id, movement_date, reference_id
                    )
                    VALUES (%s, %s, %s, 'DAMAGE', %s, %s, %s, %s, %s)
                    """,
                    (
                        damage_movement_id,
                        original["store_id"],
                        original["sku_id"],
                        return_quantity,
                        f"Damaged exchange product {return_id}",
                        employee_role_id,
                        sale_date,
                        return_id
                    )
                )

            # Record the replacement product leaving inventory.
            cursor.execute(
                """
                INSERT INTO InventoryMovement
                (
                    movement_id, store_id, sku_id,
                    movement_type, quantity, reason,
                    employee_role_id, movement_date, reference_id
                )
                VALUES (%s, %s, %s, 'SALE', %s, %s, %s, %s, %s)
                """,
                (
                    replacement_movement_id,
                    original["store_id"],
                    replacement_sku_id,
                    return_quantity,
                    f"Replacement for exchange {return_id}",
                    employee_role_id,
                    sale_date,
                    exchange_sale_id
                )
            )

            # Add replacement product to the new sale.
            cursor.execute(
                """
                INSERT INTO CustomerSaleItem
                (
                    sale_id, sku_id, quantity,
                    selling_price, movement_id
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    exchange_sale_id,
                    replacement_sku_id,
                    return_quantity,
                    replacement_price,
                    replacement_movement_id
                )
            )

            # Save the exchange record.
            cursor.execute(
                """
                INSERT INTO `Return`
                (
                    return_id,
                    original_sale_movement_id,
                    return_movement_id,
                    store_id,
                    sku_id,
                    return_quantity,
                    return_reason,
                    return_date,
                    status,
                    return_condition,
                    exchange_sale_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                        'COMPLETED', %s, %s)
                """,
                (
                    return_id,
                    original_movement_id,
                    return_movement_id,
                    original["store_id"],
                    original["sku_id"],
                    return_quantity,
                    return_reason,
                    sale_date,
                    return_condition,
                    exchange_sale_id
                )
            )

            connection.commit()

            flash(
                f"Exchange completed successfully! "
                f"Return ID: {return_id}. "
                f"New Sale ID: {exchange_sale_id}",
                "success"
            )

        except Exception as error:
            connection.rollback()
            flash(f"Exchange failed: {error}", "error")

        finally:
            cursor.close()
            connection.close()

        return redirect(
            url_for("returns_bp.returns", sale_id=sale_id)
        )

    # GET request: search for an original sale.
    sale_id = request.args.get("sale_id", "").strip()
    sale_items = []

    if sale_id:
        sale_items = get_sale_items(sale_id)

    products = fetch_all(
        """
        SELECT sku_id, product_name, unit_price
        FROM SKU
        WHERE status = 'ACTIVE'
        ORDER BY product_name
        """
    )

    # Only Owner and Manager can see the complete exchange history.
    exchange_history = []

    if session.get("account_role") in ("OWNER", "MANAGER"):
        exchange_history = fetch_all(
            """
            SELECT
                r.return_id,
                r.return_date,
                r.sku_id,
                sku.product_name,
                r.return_quantity,
                r.return_reason,
                r.return_condition,
                r.exchange_sale_id,
                s.store_name

            FROM `Return` r

            JOIN SKU sku
                ON r.sku_id = sku.sku_id

            JOIN Store s
                ON r.store_id = s.store_id

            ORDER BY r.return_date DESC
            LIMIT 50
            """
        )

    return render_template(
        "returns.html",
        sale_id=sale_id,
        sale_items=sale_items,
        products=products,
        exchange_history=exchange_history
    )
