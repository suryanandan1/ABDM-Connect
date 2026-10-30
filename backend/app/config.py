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

# ABDM connection. Defaults point at the local mock server in ../mock_abdm (not real ABDM).
ABDM_BASE_URL = os.getenv("ABDM_BASE_URL", "http://localhost:9000").rstrip("/")
ABDM_CLIENT_ID = os.getenv("ABDM_CLIENT_ID", "SBX_MOCK_001")
ABDM_CLIENT_SECRET = os.getenv("ABDM_CLIENT_SECRET", "mock-secret-change-me")
ABDM_TIMEOUT_SECONDS = float(os.getenv("ABDM_TIMEOUT_SECONDS", "10"))
