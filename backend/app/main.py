from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .database import Base, engine
from .migrations import upgrade
from .routes import admin, auth, consent, consultations, fhir_routes, patients, reports


@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(engine)  # creates any missing tables; never drops data
    upgrade()  # in-place upgrades of older databases (backs the file up first)
    yield


app = FastAPI(
    title="ABDM Connect API",
    description="Educational simulation of consent-based FHIR R4 lab report exchange and doctor consultations. "
                "Not connected to, or certified by, ABDM.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"],
)
for module in (auth, patients, reports, consultations, consent, fhir_routes, admin):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}
