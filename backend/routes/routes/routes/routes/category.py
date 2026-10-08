from fastapi import APIRouter
from database import get_connection

router = APIRouter()


@router.post("/category")
def add_category(
    category_name: str,
    perishability_risk: str,
    storage_requirement: str
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO food_categories
        (
            category_name,
            perishability_risk,
            storage_requirement
        )
        VALUES (?, ?, ?)
    """, (
        category_name,
        perishability_risk,
        storage_requirement
    ))

    connection.commit()

    category_id = cursor.lastrowid

    connection.close()

    return {
        "message": "Category added successfully",
        "category_id": category_id
    }


@router.get("/categories")
def get_categories():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM food_categories")

    categories = cursor.fetchall()

    connection.close()

    return [dict(row) for row in categories]
