
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session
)

from database import fetch_all, get_db_connection
from auth_utils import roles_required


sales_bp = Blueprint("sales_bp", __name__)


def get_expected_stock(cursor, store_id, sku_id, sale_date):
    """Calculate current expected stock using the inventory movement ledger."""

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
            f"Opening stock is not configured for product {sku_id} "
            "in this store."
        )

    expected_stock = Decimal(str(inventory["opening_quantity"]))

    cursor.execute(
        """
        SELECT movement_type, quantity, adjustment_direction
        FROM InventoryMovement
        WHERE store_id = %s
          AND sku_id = %s
          AND movement_date <= %s
        ORDER BY movement_date, movement_id
        """,
        (store_id, sku_id, sale_date)
    )

    movements = cursor.fetchall()

    for movement in movements:
        movement_type = movement["movement_type"]
        quantity = Decimal(str(movement["quantity"]))

        if movement_type in ("RECEIPT", "TRANSFER_IN", "RETURN"):
            expected_stock += quantity

        elif movement_type in ("SALE", "TRANSFER_OUT", "DAMAGE"):
            expected_stock -= quantity

        elif movement_type == "ADJUSTMENT":
            if movement["adjustment_direction"] == "INCREASE":
                expected_stock += quantity
            elif movement["adjustment_direction"] == "DECREASE":
                expected_stock -= quantity

    if expected_stock < 0:
        raise ValueError(
            f"Calculated stock is negative for product {sku_id}. "
            "Please check the inventory movements."
        )

    return expected_stock


@sales_bp.route("/sales", methods=["GET", "POST"])
@roles_required("OWNER", "MANAGER", "EMPLOYEE")
def sales():

    if request.method == "POST":

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            connection.start_transaction()

            store_id = request.form.get("store_id", "").strip()
            customer_name = request.form.get("customer_name", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()

            sku_ids = request.form.getlist("sku_id")
            quantities = request.form.getlist("quantity")

            if not store_id:
                raise ValueError("Please select a store.")

            if len(sku_ids) == 0 or len(sku_ids) != len(quantities):
                raise ValueError("Please add at least one valid product.")

            # Combine repeated products into one cart item.
            cart = {}

            for sku_id, quantity_text in zip(sku_ids, quantities):
                sku_id = sku_id.strip()

                try:
                    quantity = int(quantity_text)
                except (ValueError, TypeError):
                    raise ValueError("Product quantity must be a whole number.")

                if not sku_id or quantity <= 0:
                    raise ValueError(
                        "Select a product and enter a quantity greater than zero."
                    )

                cart[sku_id] = cart.get(sku_id, 0) + quantity

            # Confirm that the selected store is active.
            cursor.execute(
                """
                SELECT store_id
                FROM Store
                WHERE store_id = %s AND status = 'ACTIVE'
                FOR UPDATE
                """,
                (store_id,)
            )

            if not cursor.fetchone():
                raise ValueError("Selected store is not active or does not exist.")

            # Find the employee record linked to the logged-in account.
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

            sale_date = datetime.now()
            sale_id = "SALE-" + uuid.uuid4().hex[:16]

            # Lock and validate stock for every product before saving the sale.
            products_for_sale = {}
            total_amount = Decimal("0.00")

            for sku_id in sorted(cart):

                cursor.execute(
                    """
                    SELECT sku_id, product_name, unit_price
                    FROM SKU
                    WHERE sku_id = %s AND status = 'ACTIVE'
                    """,
                    (sku_id,)
                )

                product = cursor.fetchone()

                if not product:
                    raise ValueError(
                        f"Product {sku_id} is inactive or does not exist."
                    )

                available_stock = get_expected_stock(
                    cursor, store_id, sku_id, sale_date
                )

                quantity = cart[sku_id]

                if Decimal(quantity) > available_stock:
                    raise ValueError(
                        f"Insufficient stock for {product['product_name']}. "
                        f"Available: {available_stock}, requested: {quantity}."
                    )

                selling_price = Decimal(str(product["unit_price"]))
                item_total = selling_price * quantity
                total_amount += item_total

                products_for_sale[sku_id] = {
                    "product": product,
                    "quantity": quantity,
                    "selling_price": selling_price
                }

            # Save customer details only when a customer name is provided.
            customer_id = None

            if customer_name:
                cursor.execute(
                    """
                    INSERT INTO Customer (customer_name, phone, email)
                    VALUES (%s, %s, %s)
                    """,
                    (customer_name, phone or None, email or None)
                )

                customer_id = cursor.lastrowid

            # Create one bill for all products in this sale.
            cursor.execute(
                """
                INSERT INTO CustomerSale
                (
                    sale_id, customer_id, store_id,
                    employee_role_id, sale_date, total_amount, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'COMPLETED')
                """,
                (
                    sale_id,
                    customer_id,
                    store_id,
                    employee_role_id,
                    sale_date,
                    total_amount
                )
            )

            # Save one SALE movement and one bill item per product.
            for sku_id, item in products_for_sale.items():

                movement_id = "MOV-" + uuid.uuid4().hex[:16]

                cursor.execute(
                    """
                    INSERT INTO InventoryMovement
                    (
                        movement_id,
                        store_id,
                        sku_id,
                        movement_type,
                        quantity,
                        reason,
                        employee_role_id,
                        movement_date
                    )
                    VALUES (%s, %s, %s, 'SALE', %s, %s, %s, %s)
                    """,
                    (
                        movement_id,
                        store_id,
                        sku_id,
                        item["quantity"],
                        f"Customer sale {sale_id}",
                        employee_role_id,
                        sale_date
                    )
                )

                cursor.execute(
                    """
                    INSERT INTO CustomerSaleItem
                    (
                        sale_id,
                        sku_id,
                        quantity,
                        selling_price,
                        movement_id
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id,
                        sku_id,
                        item["quantity"],
                        item["selling_price"],
                        movement_id
                    )
                )

            connection.commit()

            flash(
                f"Sale completed successfully! Bill ID: {sale_id}. "
                f"Total amount: ₹{total_amount:.2f}",
                "success"
            )

        except Exception as error:
            connection.rollback()
            flash(f"Unable to complete sale: {error}", "error")

        finally:
            cursor.close()
            connection.close()

        return redirect(url_for("sales_bp.sales"))

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
        SELECT sku_id, product_name, unit_price
        FROM SKU
        WHERE status = 'ACTIVE'
        ORDER BY product_name
        """
    )

    sales_list = fetch_all(
        """
        SELECT
            cs.sale_id,
            cs.sale_date,
            cs.total_amount,
            cs.status,
            COALESCE(c.customer_name, 'Walk-in Customer') AS customer_name,
            s.store_name
        FROM CustomerSale cs
        LEFT JOIN Customer c ON cs.customer_id = c.customer_id
        JOIN Store s ON cs.store_id = s.store_id
        ORDER BY cs.sale_date DESC
        LIMIT 50
        """
    )

    return render_template(
        "sales.html",
        stores=stores,
        products=products,
        sales_list=sales_list
    )
