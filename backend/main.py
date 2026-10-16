
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from database import create_tables
from fastapi.middleware.cors import CORSMiddleware
from routes.inventory import router as inventory_router
from routes.business import router as business_router
from routes.expiry import router as expiry_router
from routes.category import router as category_router
from routes.ngo import router as ngo_router
from routes.matching import router as matching_router
from routes.donations import router as donations_router
from routes.pos import router as pos_router
from contextlib import asynccontextmanager
from expiry_scheduler import (
    start_expiry_scheduler,
    stop_expiry_scheduler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_expiry_scheduler()
    try:
        yield
    finally:
        stop_expiry_scheduler()


app = FastAPI(
    title="AI-Powered Food Waste Management Platform",
    description=(
        "Manage food inventory, expiry alerts, surplus identification, "
        "NGO registration, surplus food matching, donation management, "
        "and mock POS sales."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(pos_router)


# Add API-key authentication scheme to Swagger documentation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema.setdefault("components", {})
    openapi_schema["components"].setdefault("securitySchemes", {})

    openapi_schema["components"]["securitySchemes"]["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Enter your active business API key."
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Home API
@app.get("/")
def home():
    return {
        "message": "Food Waste Management API is working!"
    }
