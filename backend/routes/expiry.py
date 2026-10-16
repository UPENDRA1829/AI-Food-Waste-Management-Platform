
from fastapi import APIRouter, Depends, Query
from database import get_connection
from business_api_keys import get_authenticated_business_id
from datetime import date

router = APIRouter()


def get_expiry_status(days_left: int):
    """Return the expiry status, priority, and recommended action."""

    if days_left < 0:
        return {
            "status": "Expired",
            "priority": "Critical",
            "notification": "Remove from available stock"
        }

    if days_left == 0:
        return {
            "status": "Expires Today",
            "priority": "High",
            "notification": "Use or redistribute today"
        }

    if days_left <= 2:
        return {
            "status": "Expiring Soon",
            "priority": "High",
            "notification": "Prioritize use or redistribution"
        }

    return {
        "status": "Fresh",
        "priority": "Normal",
        "notification": "No immediate action needed"
    }


def get_business_inventory(business_id: int):
    """Fetch inventory belonging only to the authenticated business."""

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM inventory
            WHERE business_id = ?
        """, (business_id,))

        return cursor.fetchall()

    finally:
        connection.close()


def build_expiry_record(item, alert_days: int):
    """Calculate expiry information for one inventory item."""

    raw_expiry_date = item["expiry_date"]

    if not raw_expiry_date:
        return None

    try:
        expiry_date = date.fromisoformat(raw_expiry_date)
    except (ValueError, TypeError):
        return None

    days_left = (expiry_date - date.today()).days
    expiry_info = get_expiry_status(days_left)

    return {
        "inventory_id": item["inventory_id"],
        "product_name": item["product_name"],
        "quantity": item["quantity"],
        "unit": item["unit"],
        "food_type": item["food_type"],
        "expiry_date": raw_expiry_date,
        "days_left": days_left,
        "status": expiry_info["status"],
        "priority": expiry_info["priority"],
        "notification": expiry_info["notification"],
        "needs_attention": days_left <= alert_days
    }


def save_expiry_notification(business_id: int, record: dict):
    """Save an alert once for a given item, expiry date, and status."""

    if not record["needs_attention"]:
        return False

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO expiry_notifications (
                business_id,
                inventory_id,
                product_name,
                expiry_date,
                days_left,
                status,
                priority,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_id,
            record["inventory_id"],
            record["product_name"],
            record["expiry_date"],
            record["days_left"],
            record["status"],
            record["priority"],
            record["notification"]
        ))

        connection.commit()
        return cursor.rowcount == 1

    finally:
        connection.close()


# API 1: Check expiry status and record alerts
@router.get("/expiry-check")
def check_expiry(
    business_id: int = Depends(get_authenticated_business_id),
    alert_days: int = Query(default=2, ge=0, le=30)
):
    inventory = get_business_inventory(business_id)
    result = []
    skipped_items = 0
    new_notifications = 0

    for item in inventory:
        record = build_expiry_record(item, alert_days)

        if record is None:
            skipped_items += 1
            continue

        result.append(record)

        if save_expiry_notification(business_id, record):
            new_notifications += 1

    return {
        "business_id": business_id,
        "total_items_checked": len(result),
        "alert_days": alert_days,
        "new_notifications_saved": new_notifications,
        "skipped_items_invalid_expiry": skipped_items,
        "items": result
    }


# API 2: Show items needing expiry attention
@router.get("/expiry-alerts")
def get_expiry_alerts(
    business_id: int = Depends(get_authenticated_business_id),
    alert_days: int = Query(default=2, ge=0, le=30)
):
    inventory = get_business_inventory(business_id)
    alerts = []
    skipped_items = 0
    new_notifications = 0

    for item in inventory:
        record = build_expiry_record(item, alert_days)

        if record is None:
            skipped_items += 1
            continue

        if record["needs_attention"]:
            alerts.append(record)

            if save_expiry_notification(business_id, record):
                new_notifications += 1

    return {
        "business_id": business_id,
        "total_alerts": len(alerts),
        "alert_days": alert_days,
        "new_notifications_saved": new_notifications,
        "skipped_items_invalid_expiry": skipped_items,
        "alerts": alerts
    }


# API 3: Retrieve saved notification history
@router.get("/expiry-notifications")
def get_expiry_notifications(
    business_id: int = Depends(get_authenticated_business_id),
    unread_only: bool = False
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                notification_id,
                inventory_id,
                product_name,
                expiry_date,
                days_left,
                status,
                priority,
                message,
                created_at,
                is_read
            FROM expiry_notifications
            WHERE business_id = ?
        """

        parameters = [business_id]

        if unread_only:
            query += " AND is_read = 0"

        query += " ORDER BY created_at DESC, notification_id DESC"

        cursor.execute(query, parameters)
        notifications = [dict(row) for row in cursor.fetchall()]

        return {
            "business_id": business_id,
            "total_notifications": len(notifications),
            "unread_only": unread_only,
            "notifications": notifications
        }

    finally:
        connection.close()


# API 4: Mark a saved notification as read
@router.patch("/expiry-notifications/{notification_id}/read")
def mark_expiry_notification_read(
    notification_id: int,
    business_id: int = Depends(get_authenticated_business_id)
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE expiry_notifications
            SET is_read = 1
            WHERE notification_id = ?
              AND business_id = ?
        """, (notification_id, business_id))

        connection.commit()

        if cursor.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail="Notification not found for this business"
            )

        return {
            "message": "Notification marked as read",
            "notification_id": notification_id
        }

    finally:
        connection.close()
