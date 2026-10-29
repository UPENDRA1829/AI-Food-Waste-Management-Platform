import sqlite3

db_path = r"D:\Food_Redistribute_Project\backend\food_waste.db"
connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row

try:
    print("1. DATABASE INTEGRITY")
    print([tuple(r) for r in connection.execute("PRAGMA integrity_check")])

    print("\n2. FOREIGN KEY VIOLATIONS")
    print([tuple(r) for r in connection.execute("PRAGMA foreign_key_check")])

    print("\n3. FOREIGN KEY ENFORCEMENT")
    print(tuple(connection.execute("PRAGMA foreign_keys").fetchone()))

    print("\n4. DATABASE TABLES")
    tables = connection.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' ORDER BY name
    """).fetchall()

    for table in tables:
        print(table["name"])

    for table_name in ("inventory", "sales", "inventory_transactions"):
        print(f"\nCOLUMNS IN {table_name}")
        columns = connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

        if not columns:
            print("Table not found")
        else:
            for column in columns:
                print(f'{column["name"]} ({column["type"]})')
finally:
    connection.close()
