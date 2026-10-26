from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

import logging

from app.config import get_settings
from app.database import Base, engine, SessionLocal
from app.data_loader import ensure_dataset_loaded
from app.rate_limit import limiter
from app.retention import purge_expired_otp_codes, purge_stale_places_cache
from app.routers import auth, profile, symptoms, places, reference

logger = logging.getLogger("syncsupply.startup")

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Multilingual, voice-enabled Ayurvedic home-remedy suggestion API.",
    version="1.1.0",
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limited", "message": "Too many requests. Please slow down and try again shortly."}},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """
    Every route in this app raises HTTPException(detail={"error": {"code", "message"}}).
    FastAPI's default handler would nest that under {"detail": {...}}; this
    unwraps it so the API's error shape is always exactly
    {"error": {"code": ..., "message": ...}} as documented in the API table.
    """
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": str(exc.detail)}})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    message = f"{field}: {first.get('msg', 'invalid value')}" if field else "Invalid request."
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": message}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Something went wrong. Please try again."}},
    )


_INSECURE_DEFAULTS = {"change-me-in-env", ""}


@app.on_event("startup")
def on_startup():
    # Secrets management guard: refuse to boot in production with a default
    # JWT secret. A misconfigured free-tier deploy failing loudly here is
    # far better than silently signing tokens with a secret anyone can read
    # out of this repo's .env.example.
    if settings.ENV.lower() == "production" and settings.JWT_SECRET in _INSECURE_DEFAULTS:
        raise RuntimeError(
            "Refusing to start in production with a default/empty JWT_SECRET. "
            "Set a real JWT_SECRET environment variable (Render's render.yaml "
            "already does this via generateValue: true)."
        )
    if settings.ENV.lower() == "production" and not settings.COOKIE_SECURE:
        logger.warning("COOKIE_SECURE=false in a production environment — trial cookies will not be set correctly over HTTPS.")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_dataset_loaded(db)
        purge_expired_otp_codes(db)
        purge_stale_places_cache(db)
    finally:
        db.close()


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(symptoms.router)
app.include_router(places.router)
app.include_router(reference.router)
