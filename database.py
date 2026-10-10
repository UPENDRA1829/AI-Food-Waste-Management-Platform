
import sqlite3

DATABASE_NAME = "food_waste.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_connection()
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

    # Safely add food_type to existing inventory tables
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

    # Save database changes and close connection
    connection.commit()
    connection.close()
