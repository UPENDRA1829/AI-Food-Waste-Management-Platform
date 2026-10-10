
from datetime import date

from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter()


# API 1: Create a donation request
@router.post("/donations")
def create_donation(
    inventory_id: int,
    ngo_id: int,
    quantity: float,
    pickup_notes: str = ""
):
    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Donation quantity must be greater than zero"
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Check that the inventory item exists
        cursor.execute(
            "SELECT * FROM inventory WHERE inventory_id = ?",
            (inventory_id,)
        )
        item = cursor.fetchone()

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found"
            )

        # Check that the NGO exists
        cursor.execute(
            "SELECT * FROM ngos WHERE ngo_id = ?",
            (ngo_id,)
        )
        ngo = cursor.fetchone()

        if ngo is None:
            raise HTTPException(
                status_code=404,
                detail="NGO not found"
            )

        # Do not create a request for expired food
        if item["expiry_date"]:
            expiry_date = date.fromisoformat(item["expiry_date"])

            if expiry_date < date.today():
                raise HTTPException(
                    status_code=400,
                    detail="Expired food cannot be donated"
                )

        if quantity > item["quantity"]:
            raise HTTPException(
                status_code=400,
                detail="Donation quantity exceeds available inventory"
            )

        cursor.execute("""
            INSERT INTO donations (
                inventory_id, ngo_id, quantity,
                status, pickup_notes
            )
            VALUES (?, ?, ?, 'Pending', ?)
        """, (
            inventory_id,
            ngo_id,
            quantity,
            pickup_notes
        ))

        connection.commit()

        return {
            "message": "Donation request created successfully",
            "donation_id": cursor.lastrowid,
            "inventory_id": inventory_id,
            "ngo_id": ngo_id,
            "quantity": quantity,
            "status": "Pending"
        }

    finally:
        connection.close()


# API 2: View all donation requests
@router.get("/donations")
def get_donations():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                d.donation_id,
                d.inventory_id,
                i.product_name,
                d.ngo_id,
                n.ngo_name,
                d.quantity,
                i.unit,
                d.status,
                d.created_at,
                d.pickup_notes
            FROM donations d
            JOIN inventory i
                ON d.inventory_id = i.inventory_id
            JOIN ngos n
                ON d.ngo_id = n.ngo_id
            ORDER BY d.donation_id DESC
        """)

        donations = [
            dict(row) for row in cursor.fetchall()
        ]

        return {
            "total_donations": len(donations),
            "donations": donations
        }

    finally:
        connection.close()


# API 3: Update donation status
@router.patch("/donations/{donation_id}/status")
def update_donation_status(
    donation_id: int,
    status: str
):
    allowed_statuses = [
        "Pending",
        "Accepted",
        "Collected",
        "Rejected"
    ]

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {allowed_statuses}"
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT donation_id, status FROM donations WHERE donation_id = ?",
            (donation_id,)
        )

        donation = cursor.fetchone()

        if donation is None:
            raise HTTPException(
                status_code=404,
                detail="Donation request not found"
            )

        current_status = donation["status"]

        # Enforce sensible status transitions
        allowed_transitions = {
            "Pending": ["Accepted", "Rejected"],
            "Accepted": ["Collected", "Rejected"],
            "Collected": [],
            "Rejected": []
        }

        if status != current_status and status not in allowed_transitions[current_status]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot change status from {current_status} to {status}"
            )

        cursor.execute(
            "UPDATE donations SET status = ? WHERE donation_id = ?",
            (status, donation_id)
        )

        connection.commit()

        return {
            "message": "Donation status updated successfully",
            "donation_id": donation_id,
            "previous_status": current_status,
            "current_status": status
        }

    finally:
        connection.close()
