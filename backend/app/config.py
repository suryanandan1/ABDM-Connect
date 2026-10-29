"""Application settings, read from environment variables (or a local .env file)."""
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./abdm_connect.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me-before-any-deployment")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
# Base URL used inside FHIR fullUrl/reference values.
FHIR_BASE_URL = os.getenv("FHIR_BASE_URL", "http://localhost:8000/api/v1/fhir")
