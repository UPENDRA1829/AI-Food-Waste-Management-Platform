
from datetime import date

from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter()


def normalize_unit(unit):
    """Return 'kg' for recognized kilogram units."""
    if not unit:
        return None

    normalized = unit.strip().lower()

    kilogram_units = {
        "kg",
        "kgs",
        "kilogram",
        "kilograms"
    }

    if normalized in kilogram_units:
        return "kg"

    return normalized


# API: Match surplus food with suitable NGOs
@router.get("/match-surplus")
def match_surplus(days: int = 3):

    if days < 0:
        raise HTTPException(
            status_code=400,
            detail="Days cannot be negative"
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Get inventory and donor business locations
        cursor.execute("""
            SELECT
                inventory.*,
                businesses.address AS business_address
            FROM inventory
            JOIN businesses
                ON inventory.business_id = businesses.business_id
            WHERE inventory.quantity > 0
        """)

        inventory_items = cursor.fetchall()

        # Get all registered NGOs
        cursor.execute("SELECT * FROM ngos")
        ngos = cursor.fetchall()

        # Get pending and accepted donations with their inventory units
        cursor.execute("""
            SELECT
                d.ngo_id,
                d.quantity,
                i.unit
            FROM donations d
            JOIN inventory i
                ON d.inventory_id = i.inventory_id
            WHERE d.status IN ('Pending', 'Accepted')
        """)

        committed_rows = cursor.fetchall()

        # NGO capacity is measured in kilograms.
        # Count only committed donations whose inventory unit is kg.
        committed_capacity = {}

        for row in committed_rows:
            if normalize_unit(row["unit"]) != "kg":
                continue

            ngo_id = row["ngo_id"]

            committed_capacity[ngo_id] = (
                committed_capacity.get(ngo_id, 0.0)
                + float(row["quantity"])
            )

        today = date.today()
        matches = []

        for item in inventory_items:

            # Only kilogram-based products can use this capacity.
            if normalize_unit(item["unit"]) != "kg":
                continue

            # Skip missing or invalid expiry dates
            if not item["expiry_date"]:
                continue

            try:
                expiry_date = date.fromisoformat(
                    item["expiry_date"]
                )
            except (ValueError, TypeError):
                continue

            days_left = (expiry_date - today).days

            # Only include unexpired food within the time window
            if not (0 <= days_left <= days):
                continue

            food_type = (item["food_type"] or "").strip()

            business_location = (
                item["business_address"] or ""
            ).strip().lower()

            for ngo in ngos:

                # Match accepted food type
                ngo_food_type = (
                    ngo["accepted_food_type"] or ""
                ).strip().lower()

                food_match = (
                    ngo_food_type == "both"
                    or ngo_food_type == food_type.lower()
                )

                # Match NGO city against donor address
                ngo_city = (
                    ngo["city"] or ""
                ).strip().lower()

                location_match = (
                    bool(ngo_city)
                    and ngo_city in business_location
                )

                # Calculate remaining NGO capacity in kilograms
                capacity = float(ngo["capacity"] or 0)

                committed = committed_capacity.get(
                    ngo["ngo_id"], 0.0
                )

                remaining_capacity = max(
                    0.0, capacity - committed
                )

                # Compare kg only with kg
                capacity_match = (
                    remaining_capacity > 0
                    and float(item["quantity"]) <= remaining_capacity
                )

                if food_match and location_match and capacity_match:
                    matches.append({
                        "inventory_id": item["inventory_id"],
                        "product_name": item["product_name"],
                        "available_quantity": item["quantity"],
                        "unit": item["unit"],
                        "food_type": food_type,
                        "expiry_date": item["expiry_date"],
                        "days_left": days_left,
                        "ngo_id": ngo["ngo_id"],
                        "ngo_name": ngo["ngo_name"],
                        "ngo_city": ngo["city"],
                        "ngo_capacity": capacity,
                        "capacity_unit": "kg",
                        "committed_quantity": committed,
                        "remaining_capacity": remaining_capacity,
                        "match_reason": (
                            "Food type, location, expiry, "
                            "kilogram unit, and NGO capacity match"
                        ),
                        "next_step": (
                            "Verify food safety and confirm "
                            "pickup arrangements before donation"
                        )
                    })

        return {
            "message": "Kilogram-based surplus matching completed",
            "days_threshold": days,
            "capacity_unit": "kg",
            "total_matches": len(matches),
            "matches": matches
        }

    finally:
        connection.close()
