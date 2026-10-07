from fastapi import FastAPI
from database import create_tables
from routes.inventory import router as inventory_router

app = FastAPI()

# Create database tables
create_tables()

# Connect inventory routes
app.include_router(inventory_router)


@app.get("/")
def home():
    return {"message": "Food Waste API is working!"}