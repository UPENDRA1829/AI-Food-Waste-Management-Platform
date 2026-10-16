
from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter()


# API 1: Register a new NGO or community kitchen
@router.post("/ngos")
def register_ngo(
    ngo_name: str,
    address: str,
    contact_person: str = "",
    email: str = "",
    phone: str = "",
    city: str = "",
    accepted_food_type: str = "Both",
    capacity: float = 0,
    operating_hours: str = ""
):
    if not ngo_name.strip():
        raise HTTPException(
            status_code=400,
            detail="NGO name is required"
        )

    if not address.strip():
        raise HTTPException(
            status_code=400,
            detail="NGO address is required"
        )

    if accepted_food_type not in ["Veg", "Non-Veg", "Both"]:
        raise HTTPException(
            status_code=400,
            detail="accepted_food_type must be Veg, Non-Veg, or Both"
        )

    if capacity < 0:
        raise HTTPException(
            status_code=400,
            detail="Capacity cannot be negative"
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO ngos (
                ngo_name, contact_person, email, phone,
                address, city, accepted_food_type,
                capacity, operating_hours
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ngo_name.strip(),
            contact_person.strip(),
            email.strip(),
            phone.strip(),
            address.strip(),
            city.strip(),
            accepted_food_type,
            capacity,
            operating_hours.strip()
        ))

        connection.commit()

        return {
            "message": "NGO registered successfully",
            "ngo_id": cursor.lastrowid,
            "ngo_name": ngo_name
        }

    finally:
        connection.close()


# API 2: View all registered NGOs
@router.get("/ngos")
def get_ngos():
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM ngos ORDER BY ngo_id")

        ngos = [dict(row) for row in cursor.fetchall()]

        return {
            "total_ngos": len(ngos),
            "ngos": ngos
        }

    finally:
        connection.close()
