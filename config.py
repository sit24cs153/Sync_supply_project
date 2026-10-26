"""
Central configuration for SyncSupply backend.
All values are read from environment variables (.env) — nothing is hard-coded,
so the same code runs locally, on free-tier hosting, or in production
just by changing environment variables.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "SyncSupply API"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    # Falls back to a local SQLite file so the project runs with zero setup,
    # but any Postgres URL (Supabase / Railway / Render free tier) works unchanged.
    DATABASE_URL: str = "sqlite:///./syncsupply.db"

    # --- Auth ---
    JWT_SECRET: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    TRIAL_PERIOD_DAYS: int = 7

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # --- Google Maps / Places (used by the nearby-care module) ---
    GOOGLE_MAPS_API_KEY: str = ""
    PLACES_CACHE_SECONDS: int = 300

    # --- Supported languages (ISO-ish codes used across dataset + locales) ---
    SUPPORTED_LANGUAGES: str = "en,hi,ta,kn,ml,te,mr"

    # --- Safety ---
    MIN_MATCH_SCORE: int = 3
    MAX_SYMPTOM_TEXT_LENGTH: int = 500
    EMERGENCY_NUMBER_INDIA: str = "112"

    # --- OTP auth (email/phone), per the handoff guide's specified flow ---
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_REQUEST_COOLDOWN_SECONDS: int = 60
    # "console" prints the code to server logs (dev/demo on free tier with no
    # SMS/email budget). Set to "smtp" or "twilio" and fill the matching
    # credentials below to actually deliver codes in production.
    OTP_PROVIDER: str = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@syncsupply.app"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # --- Trial abuse mitigation ---
    TRIAL_STARTS_PER_IP_PER_DAY: int = 5
    # Server-managed trial identity: a random token set via an HttpOnly
    # cookie the client cannot read or forge, replacing reliance on the
    # client-supplied device_id for trust decisions. The cookie persists
    # well past the 7-day trial so it also recognizes a returning OTP login.
    TRIAL_COOKIE_NAME: str = "ss_trial"
    TRIAL_COOKIE_MAX_AGE_DAYS: int = 365
    # Secure cookies require HTTPS; disable only for local http:// dev.
    COOKIE_SECURE: bool = True

    # --- Rate limiting (in-memory; fine for a single free-tier instance) ---
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_SYMPTOMS: str = "20/minute"
    RATE_LIMIT_PLACES: str = "15/minute"  # stricter: each call can cost real Google Maps quota

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def supported_languages_list(self) -> list[str]:
        return [l.strip() for l in self.SUPPORTED_LANGUAGES.split(",") if l.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
