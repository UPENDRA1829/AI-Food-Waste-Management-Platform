
import sqlite3

db_path = r"D:\Food_Redistribute_Project\backend\food_waste.db"

connection = sqlite3.connect(
    f"file:{db_path}?mode=ro",
    uri=True
)

try:
    print("1. DATABASE INTEGRITY")
    print(connection.execute("PRAGMA integrity_check").fetchall())

    print("\n2. FOREIGN KEY VIOLATIONS")
    print(connection.execute("PRAGMA foreign_key_check").fetchall())

    print("\n3. FOREIGN KEY ENFORCEMENT")
    print(connection.execute("PRAGMA foreign_keys").fetchone())

finally:
    connection.close()
