
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from database import get_connection
from routes.inventory import get_authenticated_business_id

router = APIRouter()


def log_donation_stock_transaction(
    cursor,
    business_id,
    inventory_id,
    transaction_type,
    quantity_change,
    previous_quantity,
    new_quantity,
    unit,
    notes
):
    """Record a donation-related stock movement."""
    cursor.execute(
        """
        INSERT INTO inventory_transactions (
            business_id,
            inventory_id,
            transaction_type,
            quantity_change,
            previous_quantity,
            new_quantity,
            unit,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            business_id,
            inventory_id,
            transaction_type,
            quantity_change,
            previous_quantity,
            new_quantity,
            unit,
            notes
        )
    )


# API 1: Create a donation and reserve stock belonging to this business
@router.post("/donations")
def create_donation(
    inventory_id: int,
    ngo_id: int,
    quantity: float,
    pickup_notes: str = "",
    business_id: Annotated[
        int, Depends(get_authenticated_business_id)
    ] = None
):
    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Donation quantity must be greater than zero"
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()
        connection.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT inventory_id, business_id, product_name,
                   quantity, unit, expiry_date
            FROM inventory
            WHERE inventory_id = ? AND business_id = ?
            """,
            (inventory_id, business_id)
        )
        item = cursor.fetchone()

        if item is None:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found for this business"
            )

        cursor.execute(
            "SELECT ngo_id FROM ngos WHERE ngo_id = ?",
            (ngo_id,)
        )
        ngo = cursor.fetchone()

        if ngo is None:
            raise HTTPException(
                status_code=404,
                detail="NGO not found"
            )

        if item["expiry_date"]:
            try:
                expiry_date = date.fromisoformat(item["expiry_date"])
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid inventory expiry date"
                )

            if expiry_date < date.today():
                raise HTTPException(
                    status_code=400,
                    detail="Expired food cannot be donated"
                )

        previous_quantity = float(item["quantity"])

        if quantity > previous_quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Insufficient stock. Available quantity: "
                    f"{previous_quantity}"
                )
            )

        remaining_quantity = previous_quantity - quantity

        cursor.execute(
            """
            UPDATE inventory
            SET quantity = quantity - ?
            WHERE inventory_id = ?
              AND business_id = ?
              AND quantity >= ?
            """,
            (quantity, inventory_id, business_id, quantity)
        )

        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=400,
                detail="Unable to reserve the requested quantity"
            )

        cursor.execute(
            """
            INSERT INTO donations (
                inventory_id,
                ngo_id,
                quantity,
                status,
                pickup_notes
            )
            VALUES (?, ?, ?, 'Pending', ?)
            """,
            (inventory_id, ngo_id, quantity, pickup_notes)
        )

        donation_id = cursor.lastrowid

        log_donation_stock_transaction(
            cursor=cursor,
            business_id=business_id,
            inventory_id=inventory_id,
            transaction_type="STOCK_RESERVED_FOR_DONATION",
            quantity_change=-quantity,
            previous_quantity=previous_quantity,
            new_quantity=remaining_quantity,
            unit=item["unit"],
            notes=f"Donation ID {donation_id} created; stock reserved"
        )

        connection.commit()

        return {
            "message": "Donation request created and stock reserved",
            "donation_id": donation_id,
            "inventory_id": inventory_id,
            "ngo_id": ngo_id,
            "reserved_quantity": quantity,
            "previous_quantity": previous_quantity,
            "remaining_quantity": remaining_quantity,
            "status": "Pending",
            "transaction_logged": True
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# API 2: View only donations linked to this business's inventory
@router.get("/donations")
def get_donations(
    business_id: Annotated[
        int, Depends(get_authenticated_business_id)
    ] = None
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
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
            WHERE i.business_id = ?
            ORDER BY d.donation_id DESC
            """,
            (business_id,)
        )

        donations = [dict(row) for row in cursor.fetchall()]

        return {
            "total_donations": len(donations),
            "donations": donations
        }

    finally:
        connection.close()


# API 3: Update status only for a donation belonging to this business
@router.patch("/donations/{donation_id}/status")
def update_donation_status(
    donation_id: int,
    status: str,
    business_id: Annotated[
        int, Depends(get_authenticated_business_id)
    ] = None
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
        connection.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT
                d.donation_id,
                d.inventory_id,
                d.quantity,
                d.status
            FROM donations d
            JOIN inventory i
                ON d.inventory_id = i.inventory_id
            WHERE d.donation_id = ?
              AND i.business_id = ?
            """,
            (donation_id, business_id)
        )
        donation = cursor.fetchone()

        if donation is None:
            raise HTTPException(
                status_code=404,
                detail="Donation request not found for this business"
            )

        current_status = donation["status"]

        allowed_transitions = {
            "Pending": ["Accepted", "Rejected"],
            "Accepted": ["Collected", "Rejected"],
            "Collected": [],
            "Rejected": []
        }

        if status != current_status and status not in allowed_transitions.get(
            current_status, []
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot change status from {current_status} "
                    f"to {status}"
                )
            )

        if status == current_status:
            connection.commit()
            return {
                "message": "Donation already has this status",
                "donation_id": donation_id,
                "previous_status": current_status,
                "current_status": current_status,
                "stock_restored": False,
                "transaction_logged": False
            }

        stock_restored = False

        if status == "Rejected":
            cursor.execute(
                """
                SELECT business_id, quantity, unit
                FROM inventory
                WHERE inventory_id = ?
                  AND business_id = ?
                """,
                (donation["inventory_id"], business_id)
            )
            item = cursor.fetchone()

            if item is None:
                raise HTTPException(
                    status_code=404,
                    detail="Inventory item not found for this business"
                )

            previous_quantity = float(item["quantity"])
            restored_quantity = float(donation["quantity"])
            new_quantity = previous_quantity + restored_quantity

            cursor.execute(
                """
                UPDATE inventory
                SET quantity = quantity + ?
                WHERE inventory_id = ?
                  AND business_id = ?
                """,
                (
                    restored_quantity,
                    donation["inventory_id"],
                    business_id
                )
            )

            if cursor.rowcount != 1:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to restore inventory stock"
                )

            log_donation_stock_transaction(
                cursor=cursor,
                business_id=business_id,
                inventory_id=donation["inventory_id"],
                transaction_type="STOCK_RESTORED",
                quantity_change=restored_quantity,
                previous_quantity=previous_quantity,
                new_quantity=new_quantity,
                unit=item["unit"],
                notes=f"Donation ID {donation_id} rejected; stock restored"
            )

            stock_restored = True

        cursor.execute(
            """
            UPDATE donations
            SET status = ?
            WHERE donation_id = ?
            """,
            (status, donation_id)
        )

        connection.commit()

        return {
            "message": "Donation status updated successfully",
            "donation_id": donation_id,
            "previous_status": current_status,
            "current_status": status,
            "stock_restored": stock_restored,
            "transaction_logged": stock_restored
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

# API 4: View stock transaction history for this business
@router.get("/inventory-transactions")
def get_inventory_transactions(
    business_id: Annotated[
        int, Depends(get_authenticated_business_id)
    ] = None
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                transaction_id,
                business_id,
                inventory_id,
                transaction_type,
                quantity_change,
                previous_quantity,
                new_quantity,
                unit,
                notes
            FROM inventory_transactions
            WHERE business_id = ?
            ORDER BY transaction_id DESC
            """,
            (business_id,)
        )

        transactions = [
            dict(row) for row in cursor.fetchall()
        ]

        return {
            "total_transactions": len(transactions),
            "transactions": transactions
        }

    finally:
        connection.close()
