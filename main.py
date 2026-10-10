from fastapi import FastAPI

from database import create_tables

from routes.inventory import router as inventory_router
from routes.business import router as business_router
from routes.expiry import router as expiry_router
from routes.category import router as category_router
from routes.ngo import router as ngo_router
from routes.matching import router as matching_router
from routes.donations import router as donations_router


app = FastAPI(
    title="AI-Powered Food Waste Management Platform",
    description=(
        "Manage food inventory, expiry alerts, surplus identification, "
        "NGO registration, surplus food matching, and donation management."
    ),
    version="1.0.0"
)


# Create database tables
create_tables()


# Connect all API routers
app.include_router(inventory_router)
app.include_router(business_router)
app.include_router(expiry_router)
app.include_router(category_router)
app.include_router(ngo_router)
app.include_router(matching_router)
app.include_router(donations_router)


# Home API
@app.get("/")
def home():
    return {
        "message": "Food Waste Management API is working!"
    }
