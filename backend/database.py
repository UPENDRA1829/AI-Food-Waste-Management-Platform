
import sqlite3
from pathlib import Path

# =====================================================
# FOODRESCUE DATABASE CONFIGURATION
# =====================================================

DB_PATH = Path(__file__).resolve().parent / "food_waste.db"


# =====================================================
# 1. DATABASE CONNECTION
# =====================================================

def get_connection():
    """
    Connect to the existing FoodRescue SQLite database.

    Used by:
    - Business management
    - Inventory management
    - Sales / POS
    - Expiry notifications
    - NGOs
    - Donations
    - Food matching
    """

    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"FoodRescue database not found: {DB_PATH}"
        )

    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=30,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    # Enable foreign key constraints
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# =====================================================
# 2. VERIFY EXISTING DATABASE TABLES
# =====================================================

def create_tables():
    """
    Verify existing FoodRescue tables.

    IMPORTANT:
    This function does NOT create, delete,
    or modify database tables.

    It replaces the missing startup function
    without changing the existing schema.
    """

    required_tables = {
        "businesses",
        "business_api_keys",
        "food_categories",
        "inventory",
        "inventory_transactions",
        "sales",
        "donations",
        "ngos",
        "expiry_notifications",
    }

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """)

        existing_tables = {
            row["name"]
            for row in cursor.fetchall()
        }

        missing_tables = required_tables - existing_tables

        if missing_tables:
            raise RuntimeError(
                "Missing database tables: "
                + ", ".join(sorted(missing_tables))
            )

        print("FoodRescue database tables verified successfully.")

    finally:
        connection.close()


# =====================================================
# 3. DATABASE INTEGRITY CHECK
# =====================================================

def check_database_integrity():
    """
    Check SQLite database integrity and
    foreign key violations.

    This function is read-only.
    """

    connection = get_connection()

    try:
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print("DATABASE INTEGRITY:", integrity)
        print("FOREIGN KEY VIOLATIONS:", len(violations))

        return integrity == "ok" and len(violations) == 0

    finally:
        connection.close()


# =====================================================
# 4. RUN CHECKS ONLY WHEN EXECUTED DIRECTLY
# =====================================================

if __name__ == "__main__":

    print("Checking FoodRescue database...")

    create_tables()

    if check_database_integrity():
        print("Database verification successful.")
    else:
        print("Database verification found issues.")
