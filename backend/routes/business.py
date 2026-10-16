
import hashlib
import secrets

from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter()


# API 1: Register a business and generate its API key
@router.post("/business")
def add_business(
    business_name: str,
    email: str = "",
    phone: str = "",
    address: str = ""
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Step 1: Register the business
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

        business_id = cursor.lastrowid

        # Step 2: Generate a unique secret API key
        raw_key = secrets.token_urlsafe(32)

        # Step 3: Store only the hash of the API key
        key_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

        cursor.execute("""
            INSERT INTO business_api_keys
            (business_id, key_hash, is_active)
            VALUES (?, ?, 1)
        """, (business_id, key_hash))

        # Save the business and its key together
        connection.commit()

        return {
            "message": "Business registered successfully",
            "business_id": business_id,
            "business_name": business_name,
            "api_key": raw_key,
            "warning": "Save this API key securely. It will not be shown again."
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# API 2: Get all registered businesses
@router.get("/businesses")
def get_businesses():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT business_id, business_name, email, phone, address
            FROM businesses
            ORDER BY business_id
        """)

        businesses = cursor.fetchall()

        return {
            "total_businesses": len(businesses),
            "businesses": [dict(row) for row in businesses]
        }

    finally:
        connection.close()

# API 3: Regenerate an API key for an existing business
@router.post("/business/{business_id}/regenerate-api-key")
def regenerate_api_key(business_id: int):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Check whether the business exists
        cursor.execute(
            "SELECT business_id FROM businesses WHERE business_id = ?",
            (business_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Business not found"
            )

        # Deactivate existing API keys
        cursor.execute("""
            UPDATE business_api_keys
            SET is_active = 0
            WHERE business_id = ?
        """, (business_id,))

        # Generate a new API key
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

        # Store only the hash of the new key
        cursor.execute("""
            INSERT INTO business_api_keys
            (business_id, key_hash, is_active)
            VALUES (?, ?, 1)
        """, (business_id, key_hash))

        connection.commit()

        return {
            "message": "API key regenerated successfully",
            "business_id": business_id,
            "api_key": raw_key,
            "warning": "Save this API key securely. It will not be shown again."
        }

    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
