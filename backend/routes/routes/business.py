from fastapi import APIRouter
from database import get_connection

router = APIRouter()


@router.post("/business")
def add_business(
    business_name: str,
    email: str = "",
    phone: str = "",
    address: str = ""
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO businesses
        (business_name, email, phone, address)
        VALUES (?, ?, ?, ?)
    """, (
        business_name,
        email,
        phone,
        address
    ))

    connection.commit()

    business_id = cursor.lastrowid

    connection.close()

    return {
        "message": "Business added successfully",
        "business_id": business_id
    }
