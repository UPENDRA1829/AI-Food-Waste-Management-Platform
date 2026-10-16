
from apscheduler.schedulers.background import BackgroundScheduler

from database import get_connection
from routes.expiry import (
    get_business_inventory,
    build_expiry_record,
    save_expiry_notification,
)

scheduler = BackgroundScheduler()


def check_all_business_expiry():
    """Check expiry dates and save in-app alerts for every business."""


    from datetime import datetime
    print(f"[Expiry Scheduler] Check started at {datetime.now()}")
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT business_id FROM businesses")
        businesses = [row["business_id"] for row in cursor.fetchall()]
    finally:
        connection.close()

    for business_id in businesses:
        try:
            inventory_items = get_business_inventory(business_id)

            for item in inventory_items:
                record = build_expiry_record(item, alert_days=2)

                # Skip items with missing or invalid expiry dates.
                if record is None:
                    continue

                if record["needs_attention"]:
                    save_expiry_notification(business_id, record)

        except Exception as error:
            print(
                f"Expiry scheduler error for business "
                f"{business_id}: {error}"
            )


def start_expiry_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            check_all_business_expiry,
            trigger="interval",
            hours=6,
            id="expiry_check",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.start()
        print("Expiry scheduler started. Checks run every 6 hours.")


def stop_expiry_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
