
import json
import urllib.request
from datetime import date, timedelta

from database import get_connection

TEST_97KG = "TEMP_MATCH_TEST_97KG"
TEST_PIECES = "TEMP_MATCH_TEST_PIECES"

connection = get_connection()
test_inventory_ids = []
test_donation_ids = []

try:
    cursor = connection.cursor()

    # Use existing NGO 1 and business 1.
    cursor.execute(
        "SELECT ngo_id FROM ngos WHERE ngo_id = 1"
    )
    assert cursor.fetchone(), "Test NGO 1 does not exist"

    cursor.execute(
        "SELECT business_id FROM businesses WHERE business_id = 1"
    )
    assert cursor.fetchone(), "Test business 1 does not exist"

    # Temporary expiry date within the next 3 days.
    expiry = (date.today() + timedelta(days=1)).isoformat()
    purchase = date.today().isoformat()

    # Test product: 97 kg, exceeding the 96 kg remaining capacity.
    cursor.execute("""
        INSERT INTO inventory (
            business_id, product_name, category, quantity, unit,
            purchase_date, expiry_date, storage_type,
            barcode, qr_code, food_type
        )
        VALUES (1, ?, 'Vegetables', 97, 'kg', ?, ?, 'Cold',
                NULL, NULL, 'Veg')
    """, (TEST_97KG, purchase, expiry))
    test_inventory_ids.append(cursor.lastrowid)

    # Temporary inventory measured in pieces.
    cursor.execute("""
        INSERT INTO inventory (
            business_id, product_name, category, quantity, unit,
            purchase_date, expiry_date, storage_type,
            barcode, qr_code, food_type
        )
        VALUES (1, ?, 'Other', 10, 'piece', ?, ?, 'Dry',
                NULL, NULL, 'Veg')
    """, (TEST_PIECES, purchase, expiry))
    pieces_inventory_id = cursor.lastrowid
    test_inventory_ids.append(pieces_inventory_id)

    # Temporary pending donation: 5 pieces, not 5 kg.
    cursor.execute("""
        INSERT INTO donations (
            inventory_id, ngo_id, quantity, status, pickup_notes
        )
        VALUES (?, 1, 5, 'Pending', 'Temporary unit validation test')
    """, (pieces_inventory_id,))
    test_donation_ids.append(cursor.lastrowid)

    connection.commit()

    # Call the actual API.
    request = urllib.request.Request(
        "http://127.0.0.1:8000/match-surplus?days=3",
        headers={"accept": "application/json"}
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))

    matches = result["matches"]

    # Test 1: 97 kg must not match when only 96 kg remains.
    test_1_pass = not any(
        item["product_name"] == TEST_97KG
        for item in matches
    )

    # Test 2: the 5-piece donation must not count as 5 kg.
    test_2_pass = all(
        item["committed_quantity"] == 4
        for item in matches
        if item["ngo_id"] == 1
    )

    print("TEST 1 - 97 kg exceeds remaining capacity:",
          "PASS" if test_1_pass else "FAIL")
    print("TEST 2 - 5 pieces do not count as 5 kg:",
          "PASS" if test_2_pass else "FAIL")

    if not test_1_pass or not test_2_pass:
        print("Review the matching logic before proceeding.")
    else:
        print("Both matching validation tests passed.")

finally:
    # Delete only the temporary test donation and inventory rows.
    cursor = connection.cursor()

    for donation_id in test_donation_ids:
        cursor.execute(
            "DELETE FROM donations WHERE donation_id = ?",
            (donation_id,)
        )

    for inventory_id in test_inventory_ids:
        cursor.execute(
            "DELETE FROM inventory WHERE inventory_id = ?",
            (inventory_id,)
        )

    connection.commit()
    connection.close()
    print("Temporary test records cleaned up.")
