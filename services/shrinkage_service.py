import uuid
from database import get_db_connection


def detect_shrinkage():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    created_alerts = 0

    try:

        cursor.execute(
            """
            SELECT *
            FROM CycleCount
            WHERE status = 'PENDING'
            """
        )

        counts = cursor.fetchall()

        for count in counts:

            system_quantity = float(count["system_quantity"])
            physical_quantity = float(count["physical_quantity"])

            loss_quantity = system_quantity - physical_quantity

            # This project detects inventory loss (shortage). When the
            # physical quantity is equal to or greater than system stock,
            # there is no shrinkage alert to create. Mark the count APPROVED
            # because APPROVED is a valid CycleCount status in schema.sql.
            if loss_quantity <= 0:
                cursor.execute(
                    """
                    UPDATE CycleCount
                    SET status = 'APPROVED'
                    WHERE count_id = %s
                    """,
                    (count["count_id"],)
                )
                continue

            # Check whether there were repeated adjustments
            # during the 30 days before the cycle count.
            cursor.execute(
                """
                SELECT COUNT(*) AS adjustment_count
                FROM InventoryMovement
                WHERE store_id = %s
                  AND sku_id = %s
                  AND movement_type = 'ADJUSTMENT'
                  AND movement_date >= DATE_SUB(%s, INTERVAL 30 DAY)
                  AND movement_date <= %s
                """,
                (
                    count["store_id"],
                    count["sku_id"],
                    count["count_date"],
                    count["count_date"]
                )
            )

            adjustment_result = cursor.fetchone()
            adjustment_count = adjustment_result["adjustment_count"]

            if adjustment_count >= 3:
                issue_type = "REPEATED_ADJUSTMENT"
                risk_score = 90
                reason = (
                    "Inventory shortage detected with repeated adjustments."
                )
            else:
                issue_type = "UNEXPLAINED_LOSS"
                risk_score = min(100, 40 + int(loss_quantity * 2))
                reason = "Physical stock is less than expected stock."

            alert_id = "SHR-" + uuid.uuid4().hex[:20]

            cursor.execute(
                """
                INSERT INTO ShrinkageAlert
                (
                    alert_id,
                    store_id,
                    sku_id,
                    count_id,
                    expected_quantity,
                    actual_quantity,
                    loss_quantity,
                    risk_score,
                    alert_reason,
                    issue_type,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    alert_id,
                    count["store_id"],
                    count["sku_id"],
                    count["count_id"],
                    system_quantity,
                    physical_quantity,
                    loss_quantity,
                    risk_score,
                    reason,
                    issue_type,
                    "OPEN"
                )
            )

            cursor.execute(
                """
                UPDATE CycleCount
                SET status = 'REVIEW_REQUIRED'
                WHERE count_id = %s
                """,
                (count["count_id"],)
            )

            created_alerts += 1

        connection.commit()

        return created_alerts

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()