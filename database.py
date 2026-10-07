import sqlite3

DATABASE_NAME = "food_waste.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            business_id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT
        )
    """)

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
            FOREIGN KEY (business_id) REFERENCES businesses(business_id)
        )
    """)

    connection.commit()
    connection.close()