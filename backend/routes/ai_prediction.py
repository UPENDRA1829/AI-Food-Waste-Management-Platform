
import os
import json
import urllib.request
import urllib.error
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from database import get_connection
from routes.inventory import get_authenticated_business_id

router = APIRouter(prefix="/ai", tags=["AI Waste Prediction"])

AI_URL = "http://127.0.0.1:8001"


@router.get("/waste-risk")
def get_waste_risk(
    business_id: int = Depends(get_authenticated_business_id)
):
    # Read inventory belonging only to this business
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT inventory_id, product_name, category,
                   quantity, purchase_date, expiry_date
            FROM inventory
            WHERE business_id = ?
            ORDER BY inventory_id
            """,
            (business_id,)
        ).fetchall()

        inventory = [dict(row) for row in rows]

    finally:
        connection.close()

    items = []

    for item in inventory:
        try:
            expiry = date.fromisoformat(
                str(item["expiry_date"])[:10]
            )
        except (ValueError, TypeError):
            continue

        purchase = None

        try:
            purchase = date.fromisoformat(
                str(item["purchase_date"])[:10]
            )
        except (ValueError, TypeError):
            pass

        shelf_life = max(
            1,
            (expiry - purchase).days
        ) if purchase else 7

        inventory_id = item["inventory_id"]

        items.append({
            "product_id": f"inventory-{inventory_id}",
            "batch_id": f"batch-{inventory_id}",
            "name": item["product_name"],
            "category": item["category"] or "unknown",
            "current_stock": max(
                0.0, float(item["quantity"] or 0)
            ),
            "expiry_date": expiry.isoformat(),
            "shelf_life_days": shelf_life,
            "perishability": "medium",
            "unit_cost": 0.0
        })

    if not items:
        return {
            "count": 0,
            "results": [],
            "warning": "No inventory with valid expiry dates."
        }

    ai_key = os.environ.get("FOODRESCUE_AI_API_KEY")

    if not ai_key:
        raise HTTPException(
            status_code=503,
            detail="AI engine API key is not configured."
        )

    # The AI engine accepts a maximum of 2000 items per request.
    all_results = []

    for start in range(0, len(items), 2000):
        payload = json.dumps({
            "items": items[start:start + 2000]
        }).encode("utf-8")

        request = urllib.request.Request(
            f"{AI_URL}/v1/foodrescue-business-{business_id}/risk/score",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": ai_key
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(
                request, timeout=30
            ) as response:
                data = json.load(response)

            all_results.extend(data.get("results", []))

        except (urllib.error.URLError, TimeoutError):
            raise HTTPException(
                status_code=503,
                detail="AI engine is unavailable or rejected the request."
            )

        except (ValueError, TypeError):
            raise HTTPException(
                status_code=502,
                detail="AI engine returned an invalid response."
            )

    # Map AI results back to inventory records
    names = {
        f"inventory-{i['inventory_id']}": i["product_name"]
        for i in inventory
    }

    for result in all_results:
        result["name"] = names.get(
            result.get("product_id"),
            "Unknown product"
        )

    return {
        "count": len(all_results),
        "results": all_results,
        "prediction_status": "preliminary",
        "saved_to_foodrescue_database": False,
        "warning": (
            "Risk estimates may be preliminary. "
            "Reliable AI forecasts require sufficient "
            "historical sales and waste data."
        )
    }

@router.get("/demo/forecast")
def get_demo_forecast(
    category: str = "bakery",
    horizon: int = 7,
    business_id: int = Depends(get_authenticated_business_id)
):
    # This endpoint uses synthetic demonstration data only.
    # It does not read or modify FoodRescue inventory.
    allowed_categories = {
        "bakery", "dairy", "frozen",
        "meat", "packaged", "produce"
    }

    if category not in allowed_categories:
        raise HTTPException(
            status_code=400,
            detail="Invalid demonstration category."
        )

    if not 1 <= horizon <= 30:
        raise HTTPException(
            status_code=400,
            detail="Horizon must be between 1 and 30 days."
        )

    ai_key = os.environ.get("FOODRESCUE_AI_API_KEY")

    if not ai_key:
        raise HTTPException(
            status_code=503,
            detail="AI engine API key is not configured."
        )

    url = (
        f"{AI_URL}/v1/demo_store_a/forecast/"
        f"{category}?horizon={horizon}"
    )

    request = urllib.request.Request(
        url,
        headers={"X-API-Key": ai_key},
        method="GET"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            forecast = json.load(response)

    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(
            status_code=503,
            detail="AI forecasting engine is unavailable."
        )

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="Invalid AI forecast response."
        )

    return {
        "data_source": "synthetic_demo",
        "demo_tenant": "demo_store_a",
        "is_real_business_forecast": False,
        "category": category,
        "forecast": forecast
    }

@router.get("/demo/reorder")
def get_demo_reorder(
    business_id: int = Depends(get_authenticated_business_id)
):
    # Synthetic demonstration recommendations only.
    # No changes to the real FoodRescue database.

    ai_key = os.environ.get("FOODRESCUE_AI_API_KEY")

    if not ai_key:
        raise HTTPException(
            status_code=503,
            detail="AI engine API key is not configured."
        )

    request = urllib.request.Request(
        f"{AI_URL}/v1/demo_store_a/reorder?only_orders=false",
        headers={"X-API-Key": ai_key},
        method="GET"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            recommendations = json.load(response)

    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(
            status_code=503,
            detail="AI reorder engine is unavailable."
        )

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=502,
            detail="Invalid AI reorder response."
        )

    return {
        "data_source": "synthetic_demo",
        "demo_tenant": "demo_store_a",
        "is_real_business_recommendation": False,
        "reorder": recommendations
    }
