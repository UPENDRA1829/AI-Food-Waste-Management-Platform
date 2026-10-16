
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from database import get_connection
from routes.inventory import get_authenticated_business_id

router = APIRouter()


# API 1: Record a sale for the authenticated business
@router.post("/pos/sales")
def create_sale(
    inventory_id: int,
    quantity_sold: float,
    business_id: Annotated[
        int, Depends(get_authenticated_business_id)
    ],
    total_amount: float = 0,
    payment_method: str = "UPI"
):
    if quantity_sold <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity sold must be greater than zero"
        )

    if total_amount < 0:
        raise HTTPException(
            status_code=400,
            detail="Total amount cannot be negative"
        )

    allowed_methods = ["Cash", "UPI", "Card"]

    if payment_method not in allowed_methods:
        raise HTTPException(
            status_code=400,
            detail="Payment method must be Cash, UPI, or Card"
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()
        connection.execute("BEGIN IMMEDIATE")

        # Only find inventory belonging to the authenticated business.
        cursor.execute(
            """
            SELECT inventory_id, business_id, product_name, quantity, unit
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

        previous_quantity = float(item["quantity"])

        if quantity_sold > previous_quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Insufficient stock. Available quantity: "
                    f"{previous_quantity}"
                )
            )

        remaining_quantity = previous_quantity - quantity_sold

        cursor.execute(
            """
            UPDATE inventory
            SET quantity = ?
            WHERE inventory_id = ? AND business_id = ?
            """,
            (remaining_quantity, inventory_id, business_id)
        )

        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=400,
                detail="Unable to update inventory stock"
            )

        cursor.execute(
            """
            INSERT INTO sales (
                inventory_id,
                quantity_sold,
                unit,
                total_amount,
                payment_method
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                inventory_id,
                quantity_sold,
                item["unit"],
                total_amount,
                payment_method
            )
        )

        sale_id = cursor.lastrowid

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
                "STOCK_SOLD",
                -quantity_sold,
                previous_quantity,
                remaining_quantity,
                item["unit"],
                f"POS sale ID {sale_id}"
            )
        )

        connection.commit()

        return {
            "message": "Sale recorded successfully",
            "sale_id": sale_id,
            "inventory_id": inventory_id,
            "product_name": item["product_name"],
            "quantity_sold": quantity_sold,
            "unit": item["unit"],
            "previous_quantity": previous_quantity,
            "remaining_quantity": remaining_quantity,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "transaction_logged": True
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# API 2: View sales belonging only to the authenticated business
@router.get("/pos/sales")
def get_sales(
    business_id: Annotated[
        int, Depends(get_authenticated_business_id)
    ]
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                s.sale_id,
                s.inventory_id,
                i.product_name,
                s.quantity_sold,
                s.unit,
                s.total_amount,
                s.payment_method,
                s.sold_at
            FROM sales s
            JOIN inventory i
                ON s.inventory_id = i.inventory_id
            WHERE i.business_id = ?
            ORDER BY s.sale_id DESC
            """,
            (business_id,)
        )

        sales = [dict(row) for row in cursor.fetchall()]

        return {
            "total_sales": len(sales),
            "sales": sales
        }

    finally:
        connection.close()
