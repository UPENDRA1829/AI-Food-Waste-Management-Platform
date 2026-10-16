
from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter()

ALLOWED_RISKS = [
    "Low",
    "Medium",
    "High",
    "Very High"
]

ALLOWED_STORAGE = [
    "Room Temperature",
    "Refrigerated",
    "Frozen",
    "Dry Storage",
    "Cold and Dry"
]


# API 1: Add a food category
@router.post("/category")
def add_category(
    category_name: str,
    perishability_risk: str,
    storage_requirement: str
):
    category_name = category_name.strip()

    # Normalize input to match the allowed values
    risk_lookup = {
        value.lower(): value for value in ALLOWED_RISKS
    }
    storage_lookup = {
        value.lower(): value for value in ALLOWED_STORAGE
    }

    if not category_name:
        raise HTTPException(
            status_code=400,
            detail="Category name cannot be empty"
        )

    normalized_risk = risk_lookup.get(
        perishability_risk.strip().lower()
    )
    if normalized_risk is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Risk must be Low, Medium, High, or Very High"
            )
        )

    normalized_storage = storage_lookup.get(
        storage_requirement.strip().lower()
    )
    if normalized_storage is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Storage must be Room Temperature, "
                "Refrigerated, Frozen, Dry Storage, "
                "or Cold and Dry"
            )
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT category_id
            FROM food_categories
            WHERE LOWER(category_name) = LOWER(?)
            """,
            (category_name,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="Category already exists"
            )

        cursor.execute(
            """
            INSERT INTO food_categories
            (
                category_name,
                perishability_risk,
                storage_requirement
            )
            VALUES (?, ?, ?)
            """,
            (
                category_name,
                normalized_risk,
                normalized_storage
            )
        )

        category_id = cursor.lastrowid
        connection.commit()

        return {
            "message": "Category added successfully",
            "category_id": category_id,
            "category_name": category_name,
            "perishability_risk": normalized_risk,
            "storage_requirement": normalized_storage
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# API 2: View all food categories
@router.get("/categories")
def get_categories():
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                category_id,
                category_name,
                perishability_risk,
                storage_requirement
            FROM food_categories
            ORDER BY category_id
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    finally:
        connection.close()
