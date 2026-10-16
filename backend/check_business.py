
import sqlite3
import os

db_path = os.path.abspath("food_waste.db")
connection = sqlite3.connect(db_path)

print("DATABASE PATH:", db_path)

cursor = connection.cursor()

print("\nTABLES:")
cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)
print(cursor.fetchall())

print("\nBUSINESS 8:")
cursor.execute(
    "SELECT business_id, business_name, email FROM businesses WHERE business_id = ?",
    (8,)
)
print(cursor.fetchall())

print("\nBUSINESS 8 API KEY RECORDS:")
cursor.execute(
    "SELECT key_id, business_id, is_active, created_at FROM business_api_keys WHERE business_id = ?",
    (8,)
)
print(cursor.fetchall())

connection.close()
