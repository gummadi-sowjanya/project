from database import fetch_all, fetch_one

def calculate_expected_stock(store_id, sku_id, count_date):

    opening = fetch_one(
        """
        SELECT opening_quantity
        FROM StoreInventory
        WHERE store_id = %s AND sku_id = %s
        """,
        (store_id, sku_id)
    )

    if not opening:
        raise ValueError(
            "Opening stock is not configured for this store and product."
        )

    expected_stock = float(opening["opening_quantity"])

    movements = fetch_all(
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

    for movement in movements:

        movement_type = movement["movement_type"]
        quantity = float(movement["quantity"])

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
            "Calculated stock is negative. Please check inventory movements."
        )

    return expected_stock