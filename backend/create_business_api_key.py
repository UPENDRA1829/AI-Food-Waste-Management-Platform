
import hashlib
import secrets

from database import get_connection


def create_business_api_key():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT business_id, business_name
            FROM businesses
            ORDER BY business_id
        """)
        businesses = cursor.fetchall()

        if not businesses:
            print("No businesses found.")
            return

        print("\nRegistered businesses:")
        for business in businesses:
            print(
                f"ID: {business['business_id']} | "
                f"Name: {business['business_name']}"
            )

        try:
            business_id = int(
                input("\nEnter business ID to rotate: ").strip()
            )
        except ValueError:
            print("Invalid business ID. No changes made.")
            return

        cursor.execute("""
            SELECT business_id, business_name
            FROM businesses
            WHERE business_id = ?
        """, (business_id,))
        business = cursor.fetchone()

        if business is None:
            print("Business not found. No changes made.")
            return

        confirmation = input(
            f"Deactivate old keys and create one new key for "
            f"{business['business_name']}? Type ROTATE: "
        ).strip()

        if confirmation != "ROTATE":
            print("Cancelled. No changes made.")
            return

        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

        # Deactivate every existing key for this business.
        cursor.execute("""
            UPDATE business_api_keys
            SET is_active = 0
            WHERE business_id = ?
        """, (business_id,))

        # Create one replacement key.
        cursor.execute("""
            INSERT INTO business_api_keys (
                business_id, key_hash, is_active
            )
            VALUES (?, ?, 1)
        """, (business_id, key_hash))

        connection.commit()

        print("\nAPI key rotated successfully.")
        print(f"Business: {business['business_name']}")
        print("Store this key privately. It will not be shown again:")
        print(raw_key)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_business_api_key()
