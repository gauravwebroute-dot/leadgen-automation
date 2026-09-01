import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import Base, engine
from app.routers import leads, search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Lead Generation Automation")

# Dev-only: wide open so the dashboard works whether it's served from this
# app or opened separately. Lock this down to a real origin list before
# this is exposed anywhere but localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dev-friendly: creates tables on startup if they don't exist. Switch to
# Alembic migrations before this touches a real production DB.
Base.metadata.create_all(bind=engine)

app.include_router(search.router)
app.include_router(leads.router)

# Demo dashboard — http://localhost:8000/dashboard/
app.mount("/dashboard", StaticFiles(directory="static", html=True), name="dashboard")


@app.get("/health")
def health():
    return {"status": "ok"}
