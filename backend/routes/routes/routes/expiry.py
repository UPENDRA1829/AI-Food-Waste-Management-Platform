from fastapi import APIRouter
from database import get_connection
from datetime import date

router = APIRouter()


@router.get("/expiry-check")
def check_expiry():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM inventory")

    inventory = cursor.fetchall()

    connection.close()

    today = date.today()
    result = []

    for item in inventory:
        expiry_date = date.fromisoformat(item["expiry_date"])
        days_left = (expiry_date - today).days

        if days_left < 0:
            status = "Expired"
        elif days_left <= 2:
            status = "Expiring Soon"
        else:
            status = "Fresh"

        result.append({
            "inventory_id": item["inventory_id"],
            "product_name": item["product_name"],
            "expiry_date": item["expiry_date"],
            "days_left": days_left,
            "status": status
        })

    return result
