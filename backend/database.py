
import sqlite3

DATABASE_NAME = "food_waste.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row

    # Enable foreign-key enforcement for this connection.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Table 1: Businesses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                business_id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT
            )
        """)

        # Table 2: Food categories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS food_categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL,
                perishability_risk TEXT NOT NULL,
                storage_requirement TEXT
            )
        """)

        # Table 3: Inventory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT,
                quantity REAL NOT NULL,
                unit TEXT,
                purchase_date TEXT,
                expiry_date TEXT,
                storage_type TEXT,
                barcode TEXT,
                qr_code TEXT,
                FOREIGN KEY (business_id)
                    REFERENCES businesses(business_id)
            )
        """)

        # Safely add food_type to an existing inventory table.
        cursor.execute("PRAGMA table_info(inventory)")
        columns = [row["name"] for row in cursor.fetchall()]

        if "food_type" not in columns:
            cursor.execute("""
                ALTER TABLE inventory
                ADD COLUMN food_type TEXT NOT NULL DEFAULT 'Veg'
            """)

        # Table 4: NGOs and community kitchens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ngos (
                ngo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ngo_name TEXT NOT NULL,
                contact_person TEXT,
                email TEXT,
                phone TEXT,
                address TEXT NOT NULL,
                city TEXT,
                accepted_food_type TEXT NOT NULL DEFAULT 'Both',
                capacity REAL DEFAULT 0,
                operating_hours TEXT
            )
        """)

        # Table 5: Donation management
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS donations (
                donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_id INTEGER NOT NULL,
                ngo_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                pickup_notes TEXT,
                FOREIGN KEY (inventory_id)
                    REFERENCES inventory(inventory_id),
                FOREIGN KEY (ngo_id)
                    REFERENCES ngos(ngo_id)
            )
        """)

        # Table 6: Mock POS sales records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_id INTEGER NOT NULL,
                quantity_sold REAL NOT NULL,
                unit TEXT,
                total_amount REAL DEFAULT 0,
                payment_method TEXT,
                sold_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (inventory_id)
                    REFERENCES inventory(inventory_id)
            )
        """)

        # Table 7: Business API-key hashes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_api_keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (business_id)
                    REFERENCES businesses(business_id)
            )
        """)

        # Table 8: Expiry notification history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expiry_notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                inventory_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                expiry_date TEXT,
                days_left INTEGER NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (business_id)
                    REFERENCES businesses(business_id),
                FOREIGN KEY (inventory_id)
                    REFERENCES inventory(inventory_id)
            )
        """)

        # Prevent duplicate expiry notifications for the same
        # business, item, expiry date, and status.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_expiry_notification_unique
            ON expiry_notifications (
                business_id,
                inventory_id,
                expiry_date,
                status
            )
        """)

        # Table 9: Inventory transaction history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                inventory_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity_change REAL NOT NULL,
                previous_quantity REAL,
                new_quantity REAL NOT NULL,
                unit TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id)
                    REFERENCES businesses(business_id),
                FOREIGN KEY (inventory_id)
                    REFERENCES inventory(inventory_id)
            )
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
