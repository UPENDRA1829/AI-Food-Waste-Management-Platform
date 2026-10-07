from fastapi import APIRouter
from database import get_connection

router = APIRouter()


@router.post("/inventory")
def add_inventory(
    business_id: int,
    product_name: str,
    category: str,
    quantity: float,
    unit: str,
    purchase_date: str,
    expiry_date: str,
    storage_type: str,
    barcode: str = "",
    qr_code: str = ""
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO inventory
        (
            business_id,
            product_name,
            category,
            quantity,
            unit,
            purchase_date,
            expiry_date,
            storage_type,
            barcode,
            qr_code
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        business_id,
        product_name,
        category,
        quantity,
        unit,
        purchase_date,
        expiry_date,
        storage_type,
        barcode,
        qr_code
    ))

    connection.commit()

    inventory_id = cursor.lastrowid

    connection.close()

    return {
        "message": "Inventory added successfully",
        "inventory_id": inventory_id
    }
