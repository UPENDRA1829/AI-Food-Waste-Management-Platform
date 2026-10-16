import csv

import io

import hashlib

from datetime import date

from typing import Annotated

from fastapi import (

    APIRouter,

    UploadFile,

    File,

    HTTPException,

    Header,

    Depends,

    Response,

)

from database import get_connection

from code_generator import generate_codes, generate_barcode_image, generate_qr_image

router = APIRouter()

# Helper: Authenticate a business using its API key

def get_authenticated_business_id(

    x_api_key: str | None = Header(

        default=None,

        alias="X-API-Key"

    )

) -> int:

    # Missing or empty API key must return 401, not 422

    if x_api_key is None or not x_api_key.strip():

        raise HTTPException(

            status_code=401,

            detail="Missing API key"

        )

    key_hash = hashlib.sha256(

        x_api_key.encode("utf-8")

    ).hexdigest()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT business_id

            FROM business_api_keys

            WHERE key_hash = ? AND is_active = 1

            """,

            (key_hash,)

        )

        row = cursor.fetchone()

        if row is None:

            raise HTTPException(

                status_code=401,

                detail="Invalid or inactive API key"

            )

        return row["business_id"]

    finally:

        connection.close()

# Helper: Validate and standardize a food category

def validate_category(cursor, category_name):

    category_name = category_name.strip()

    if not category_name:

        raise HTTPException(

            status_code=400,

            detail="Category name cannot be empty"

        )

    cursor.execute(

        """

        SELECT category_name

        FROM food_categories

        WHERE LOWER(category_name) = LOWER(?)

        """,

        (category_name,)

    )

    category = cursor.fetchone()

    if category is None:

        raise HTTPException(

            status_code=400,

            detail="Category does not exist. Create it first."

        )

    return category["category_name"]


# Helper: Record inventory stock movements in transaction history

def log_inventory_transaction(
    cursor,
    business_id,
    inventory_id,
    transaction_type,
    quantity_change,
    previous_quantity,
    new_quantity,
    unit,
    notes=None,
):
    """Record a stock movement in the current database transaction."""
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
            notes,
        ),
    )

# API 1: Add one inventory item

@router.post("/inventory")

def add_inventory(

    product_name: str,

    category: str,

    quantity: float,

    unit: str,

    purchase_date: str,

    expiry_date: str,

    storage_type: str,

    business_id: Annotated[

        int, Depends(get_authenticated_business_id)

    ],

    food_type: str = "Veg",

    barcode: str = "",

    qr_code: str = ""

):

    if not product_name.strip():

        raise HTTPException(

            status_code=400,

            detail="Product name cannot be empty"

        )

    if quantity <= 0:

        raise HTTPException(

            status_code=400,

            detail="Quantity must be greater than zero"

        )

    if food_type not in ["Veg", "Non-Veg"]:

        raise HTTPException(

            status_code=400,

            detail="food_type must be Veg or Non-Veg"

        )

    try:

        purchase = date.fromisoformat(purchase_date)

        expiry = date.fromisoformat(expiry_date)

    except (ValueError, TypeError):

        raise HTTPException(

            status_code=400,

            detail="Dates must use YYYY-MM-DD format"

        )

    if expiry < purchase:

        raise HTTPException(

            status_code=400,

            detail="Expiry date cannot be before purchase date"

        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        category = validate_category(cursor, category)

        barcode = barcode.strip()

        qr_code = qr_code.strip()

        # Prevent duplicate barcodes across businesses

        if barcode:

            cursor.execute(

                """

                SELECT inventory_id

                FROM inventory

                WHERE barcode = ?

                LIMIT 1

                """,

                (barcode,)

            )

            if cursor.fetchone() is not None:

                raise HTTPException(

                    status_code=400,

                    detail="Barcode already exists."

                )

        # Prevent duplicate QR codes across businesses

        if qr_code:

            cursor.execute(

                """

                SELECT inventory_id

                FROM inventory

                WHERE qr_code = ?

                LIMIT 1

                """,

                (qr_code,)

            )

            if cursor.fetchone() is not None:

                raise HTTPException(

                    status_code=400,

                    detail="QR code already exists."

                )

        cursor.execute(

            """

            INSERT INTO inventory (

                business_id, product_name, category, quantity,

                unit, purchase_date, expiry_date, storage_type,

                food_type, barcode, qr_code

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            """,

            (

                business_id,

                product_name.strip(),

                category,

                quantity,

                unit.strip(),

                purchase_date,

                expiry_date,

                storage_type.strip(),

                food_type,

                barcode,

                qr_code

            )

        )

        inventory_id = cursor.lastrowid

        log_inventory_transaction(
            cursor=cursor,
            business_id=business_id,
            inventory_id=inventory_id,
            transaction_type="STOCK_ADDED",
            quantity_change=quantity,
            previous_quantity=0,
            new_quantity=quantity,
            unit=unit.strip(),
            notes="Initial inventory entry",
        )

        # Generate internal codes when the caller did not supply them.

        generated_codes = generate_codes(inventory_id)

        if not barcode:

            barcode = generated_codes["barcode"]

        if not qr_code:

            qr_code = generated_codes["qr_code"]

        cursor.execute(

            """

            UPDATE inventory

            SET barcode = ?, qr_code = ?

            WHERE inventory_id = ? AND business_id = ?

            """,

            (barcode, qr_code, inventory_id, business_id)

        )

        connection.commit()

        return {

            "message": "Inventory added successfully",

            "inventory_id": inventory_id,

            "category": category,

            "food_type": food_type,

            "barcode": barcode,

            "qr_code": qr_code,

            "barcode_image_url": f"/inventory/{inventory_id}/barcode.png",

            "qr_image_url": f"/inventory/{inventory_id}/qr.png"

        }

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()

# API 2: View only the authenticated business's inventory

@router.get("/inventory")

def get_inventory(

    

    business_id: Annotated[

        int, Depends(get_authenticated_business_id)

    ]

):


    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT *

            FROM inventory

            WHERE business_id = ?

            ORDER BY inventory_id

            """,

            (business_id,)

        )

        return [dict(row) for row in cursor.fetchall()]

    finally:

        connection.close()

# API 3: Upload inventory using CSV

@router.post("/inventory/upload-csv")

async def upload_inventory_csv(

    file: UploadFile = File(...),

    business_id: int = Depends(get_authenticated_business_id)

):

    if not file.filename or not file.filename.lower().endswith(".csv"):

        raise HTTPException(

            status_code=400,

            detail="Please upload a .csv file"

        )

    connection = None

    try:

        content_bytes = await file.read()

        if not content_bytes:

            raise HTTPException(

                status_code=400,

                detail="Uploaded file is empty"

            )

        content = content_bytes.decode("utf-8-sig")

        content = content.lstrip("\r\n\t ")

        reader = csv.DictReader(io.StringIO(content))

        if not reader.fieldnames:

            raise HTTPException(

                status_code=400,

                detail="CSV file is empty or has no header row"

            )

        reader.fieldnames = [

            name.strip().lstrip("\ufeff")

            for name in reader.fieldnames

        ]

        required_columns = {

            "product_name",

            "category",

            "quantity",

            "unit",

            "purchase_date",

            "expiry_date",

            "storage_type",

            "food_type"

        }

        missing = required_columns - set(reader.fieldnames)

        if missing:

            raise HTTPException(

                status_code=400,

                detail=f"Missing CSV columns: {', '.join(sorted(missing))}"

            )

        rows = list(reader)

        if not rows:

            raise HTTPException(

                status_code=400,

                detail="CSV file contains no inventory records"

            )

        connection = get_connection()

        cursor = connection.cursor()

        uploaded_count = 0

        try:

            for line_number, row in enumerate(rows, start=2):

                try:

                    # A supplied business_id must match authentication

                    csv_business_id = (

                        row.get("business_id") or ""

                    ).strip()

                    if csv_business_id:

                        try:

                            supplied_business_id = int(csv_business_id)

                        except ValueError:

                            raise ValueError(

                                "CSV business_id must be an integer"

                            )

                        if supplied_business_id != business_id:

                            raise ValueError(

                                "CSV business_id does not match "

                                "the authenticated business"

                            )

                    product_name = (

                        row.get("product_name") or ""

                    ).strip()

                    category = (

                        row.get("category") or ""

                    ).strip()

                    quantity = float(row.get("quantity", ""))

                    unit = (row.get("unit") or "").strip()

                    purchase_date = (

                        row.get("purchase_date") or ""

                    ).strip()

                    expiry_date = (

                        row.get("expiry_date") or ""

                    ).strip()

                    storage_type = (

                        row.get("storage_type") or ""

                    ).strip()

                    food_type = (

                        row.get("food_type") or ""

                    ).strip()

                    barcode = (row.get("barcode") or "").strip()

                    qr_code = (row.get("qr_code") or "").strip()

                    if not product_name or not category or not unit:

                        raise ValueError(

                            "Product name, category and unit are required"

                        )

                    if quantity <= 0:

                        raise ValueError(

                            "Quantity must be greater than zero"

                        )

                    if food_type not in ["Veg", "Non-Veg"]:

                        raise ValueError(

                            "food_type must be Veg or Non-Veg"

                        )

                    purchase = date.fromisoformat(purchase_date)

                    expiry = date.fromisoformat(expiry_date)

                    if expiry < purchase:

                        raise ValueError(

                            "Expiry date cannot be before purchase date"

                        )

                    category = validate_category(cursor, category)

                    if barcode:

                        cursor.execute(

                            """

                            SELECT inventory_id

                            FROM inventory

                            WHERE barcode = ?

                            LIMIT 1

                            """,

                            (barcode,)

                        )

                        if cursor.fetchone() is not None:

                            raise ValueError(

                                f"Barcode '{barcode}' already exists"

                            )

                    if qr_code:

                        cursor.execute(

                            """

                            SELECT inventory_id

                            FROM inventory

                            WHERE qr_code = ?

                            LIMIT 1

                            """,

                            (qr_code,)

                        )

                        if cursor.fetchone() is not None:

                            raise ValueError(

                                f"QR code '{qr_code}' already exists"

                            )

                    cursor.execute(

                        """

                        INSERT INTO inventory (

                            business_id, product_name, category, quantity,

                            unit, purchase_date, expiry_date, storage_type,

                            food_type, barcode, qr_code

                        )

                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                        """,

                        (

                            business_id,

                            product_name,

                            category,

                            quantity,

                            unit,

                            purchase_date,

                            expiry_date,

                            storage_type,

                            food_type,

                            barcode,

                            qr_code

                        )

                    )

                    inventory_id = cursor.lastrowid

                    log_inventory_transaction(
                        cursor=cursor,
                        business_id=business_id,
                        inventory_id=inventory_id,
                        transaction_type="STOCK_ADDED",
                        quantity_change=quantity,
                        previous_quantity=0,
                        new_quantity=quantity,
                        unit=unit,
                        notes=f"Initial inventory entry via CSV line {line_number}",
                    )

                    # Generate codes for CSV rows that do not provide them.

                    generated_codes = generate_codes(inventory_id)

                    if not barcode:

                        barcode = generated_codes["barcode"]

                    if not qr_code:

                        qr_code = generated_codes["qr_code"]

                    cursor.execute(

                        """

                        UPDATE inventory

                        SET barcode = ?, qr_code = ?

                        WHERE inventory_id = ? AND business_id = ?

                        """,

                        (barcode, qr_code, inventory_id, business_id)

                    )

                    uploaded_count += 1

                except HTTPException:

                    raise

                except (

                    ValueError,

                    TypeError,

                    AttributeError,

                    KeyError

                ) as exc:

                    raise HTTPException(

                        status_code=400,

                        detail=(

                            f"Invalid data on CSV line {line_number}: "

                            f"{exc}. No rows were uploaded."

                        )

                    ) from exc

            connection.commit()

        except Exception:

            connection.rollback()

            raise

        return {

            "message": "CSV inventory uploaded successfully",

            "uploaded_count": uploaded_count

        }

    except UnicodeDecodeError:

        raise HTTPException(

            status_code=400,

            detail="Save your CSV using UTF-8 encoding and try again."

        )

    finally:

        if connection is not None:

            connection.close()

        await file.close()

# API 4: Filter inventory by category

@router.get("/inventory/category/{category_name}")

def get_inventory_by_category(

    category_name: str,

    business_id: Annotated[

        int, Depends(get_authenticated_business_id)

    ]

):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT *

            FROM inventory

            WHERE business_id = ?

              AND LOWER(category) = LOWER(?)

            ORDER BY inventory_id

            """,

            (business_id, category_name.strip())

        )

        items = [dict(row) for row in cursor.fetchall()]

        return {

            "category": category_name,

            "total_items": len(items),

            "items": items

        }

    finally:

        connection.close()

# API 5: Identify low-stock food items

@router.get("/inventory/low-stock")

def get_low_stock(

    threshold: float = 10,

    business_id: int = Depends(get_authenticated_business_id)

):

    if threshold < 0:

        raise HTTPException(

            status_code=400,

            detail="Threshold cannot be negative"

        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT *

            FROM inventory

            WHERE business_id = ? AND quantity <= ?

            ORDER BY quantity ASC

            """,

            (business_id, threshold)

        )

        items = [dict(row) for row in cursor.fetchall()]

        return {

            "threshold": threshold,

            "total_low_stock_items": len(items),

            "items": items

        }

    finally:

        connection.close()

# API 6: Identify potential surplus food for redistribution

@router.get("/inventory/surplus")

def identify_surplus_food(

    days: int = 3,

    business_id: int = Depends(get_authenticated_business_id)

):

    if days < 0:

        raise HTTPException(

            status_code=400,

            detail="Days cannot be negative"

        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT *

            FROM inventory

            WHERE business_id = ? AND quantity > 0

            """,

            (business_id,)

        )

        inventory = cursor.fetchall()

        today = date.today()

        surplus_items = []

        for item in inventory:

            if not item["expiry_date"]:

                continue

            try:

                expiry_date = date.fromisoformat(item["expiry_date"])

            except (ValueError, TypeError):

                continue

            days_left = (expiry_date - today).days

            if 0 <= days_left <= days:

                surplus_items.append({

                    "inventory_id": item["inventory_id"],

                    "product_name": item["product_name"],

                    "category": item["category"],

                    "quantity": item["quantity"],

                    "unit": item["unit"],

                    "food_type": item["food_type"],

                    "expiry_date": item["expiry_date"],

                    "days_left": days_left,

                    "suggestion": (

                        "Assess availability and food safety "

                        "for possible redistribution"

                    )

                })

        return {

            "message": "Potential surplus items identified",

            "days_threshold": days,

            "total_items": len(surplus_items),

            "items": surplus_items

        }

    finally:

        connection.close()

# API 7: Find inventory using barcode or QR code

@router.get("/inventory/scan/{code}")

def get_inventory_by_scan_code(

    code: str,

    business_id: Annotated[

        int, Depends(get_authenticated_business_id)

    ]

):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT *

            FROM inventory

            WHERE business_id = ?

              AND (barcode = ? OR qr_code = ?)

            """,

            (business_id, code.strip(), code.strip())

        )

        items = [dict(row) for row in cursor.fetchall()]

        if not items:

            raise HTTPException(

                status_code=404,

                detail=(

                    "No inventory item found for this barcode or QR code"

                )

            )

        return {

            "message": "Inventory item found",

            "total_items": len(items),

            "items": items

        }

    finally:

        connection.close()

# API 8: Display the barcode image for an inventory item

@router.get("/inventory/{inventory_id}/barcode.png")

def get_inventory_barcode_image(

    inventory_id: int,

    business_id: Annotated[

        int, Depends(get_authenticated_business_id)

    ]

):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT barcode

            FROM inventory

            WHERE inventory_id = ? AND business_id = ?

            """,

            (inventory_id, business_id)

        )

        item = cursor.fetchone()

        if item is None:

            raise HTTPException(

                status_code=404,

                detail="Inventory item not found"

            )

        if not item["barcode"]:

            raise HTTPException(

                status_code=404,

                detail="This inventory item has no barcode value"

            )

        image_bytes = generate_barcode_image(item["barcode"])

        return Response(content=image_bytes, media_type="image/png")

    finally:

        connection.close()

# API 9: Display the QR code image for an inventory item

@router.get("/inventory/{inventory_id}/qr.png")

def get_inventory_qr_image(

    inventory_id: int,

    business_id: Annotated[

        int, Depends(get_authenticated_business_id)

    ]

):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(

            """

            SELECT qr_code

            FROM inventory

            WHERE inventory_id = ? AND business_id = ?

            """,

            (inventory_id, business_id)

        )

        item = cursor.fetchone()

        if item is None:

            raise HTTPException(

                status_code=404,

                detail="Inventory item not found"

            )

        if not item["qr_code"]:

            raise HTTPException(

                status_code=404,

                detail="This inventory item has no QR code value"

            )

        image_bytes = generate_qr_image(item["qr_code"])

        return Response(content=image_bytes, media_type="image/png")

    finally:

        connection.close()

# API 10: View transaction history for the authenticated business

@router.get("/inventory/transactions/history")
def get_inventory_transaction_history(
    business_id: Annotated[
        int, Depends(get_authenticated_business_id)
    ],
    inventory_id: int | None = None,
    limit: int = 100,
):
    """Return stock movements belonging only to the authenticated business."""
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 500",
        )

    connection = get_connection()
    try:
        cursor = connection.cursor()

        query = """
            SELECT
                transaction_id,
                business_id,
                inventory_id,
                transaction_type,
                quantity_change,
                previous_quantity,
                new_quantity,
                unit,
                notes,
                created_at
            FROM inventory_transactions
            WHERE business_id = ?
        """
        parameters = [business_id]

        if inventory_id is not None:
            query += " AND inventory_id = ?"
            parameters.append(inventory_id)

        query += " ORDER BY transaction_id DESC LIMIT ?"
        parameters.append(limit)

        cursor.execute(query, tuple(parameters))
        transactions = [dict(row) for row in cursor.fetchall()]

        return {
            "message": "Inventory transaction history retrieved",
            "total_transactions": len(transactions),
            "transactions": transactions,
        }
    finally:
        connection.close()

