import os
from datetime import date
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="FoodRescue AI Engine", version="1.0")

class FoodItem(BaseModel):
    product_id: str
    batch_id: str
    name: str
    category: str
    current_stock: float = Field(ge=0)
    expiry_date: date
    shelf_life_days: int = Field(ge=1)
    perishability: str = "medium"
    unit_cost: float = 0.0

class RiskRequest(BaseModel):
    items: list[FoodItem]

@app.get("/health")
def health():
    return {"status": "ok", "engine": "FoodRescue"}

@app.post("/v1/{tenant_id}/risk/score")
def score_risk(
    tenant_id: str,
    payload: RiskRequest,
    x_api_key: str | None = Header(default=None)
):
    expected_key = os.getenv("FOODRESCUE_AI_API_KEY")

    if not expected_key or x_api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing AI engine API key"
        )

    results = []

    for item in payload.items:
        days_left = (item.expiry_date - date.today()).days

        if days_left <= 2:
            risk_score = 90
            risk_level = "high"
        elif days_left <= 5:
            risk_score = 60
            risk_level = "medium"
        else:
            risk_score = 20
            risk_level = "low"

        results.append({
            "product_id": item.product_id,
            "batch_id": item.batch_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "days_until_expiry": days_left,
            "method": "rule_based_expiry_v1"
        })

    return {"tenant_id": tenant_id, "results": results}
