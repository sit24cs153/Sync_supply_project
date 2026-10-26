"""
OTP generation, hashing and delivery — implements the authentication flow
specified in the handoff guide (email/phone OTP) rather than passwords.

Delivery is pluggable via OTP_PROVIDER so the app runs on a free tier with
no SMS/email budget (console provider logs the code) and can be switched to
a real provider in production by setting env vars only — no code change.
"""
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("syncsupply.otp")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9]{8,15}$")


def detect_channel(identifier: str) -> str | None:
    identifier = identifier.strip()
    if _EMAIL_RE.match(identifier):
        return "email"
    if _PHONE_RE.match(identifier):
        return "phone"
    return None


def normalize_identifier(identifier: str, channel: str) -> str:
    identifier = identifier.strip()
    return identifier.lower() if channel == "email" else identifier


def generate_code() -> str:
    # Numeric code, cryptographically random — not reconstructible from timing.
    return "".join(secrets.choice("0123456789") for _ in range(settings.OTP_LENGTH))


def hash_code(code: str, identifier: str) -> str:
    # Salted with the identifier so a leaked hash can't be replayed cross-account.
    return hashlib.sha256(f"{identifier}:{code}:{settings.JWT_SECRET}".encode()).hexdigest()


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"ip:{ip}:{settings.JWT_SECRET}".encode()).hexdigest()


def expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)


def send_code(identifier: str, channel: str, code: str) -> None:
    """
    Dispatches the code via the configured provider. The console provider is
    the only one wired up end-to-end here (no paid SMS/email account exists
    for this project); smtp/twilio branches show exactly what production
    wiring looks like and raise clearly if credentials are missing, instead
    of silently pretending to send.
    """
    provider = settings.OTP_PROVIDER.lower()

    if provider == "console":
        logger.warning("OTP for %s (%s): %s — valid %s minutes", identifier, channel, code, settings.OTP_EXPIRE_MINUTES)
        return

    if provider == "smtp" and channel == "email":
        import smtplib
        from email.mime.text import MIMEText

        if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
            raise RuntimeError("SMTP_HOST/SMTP_USER/SMTP_PASSWORD must be set when OTP_PROVIDER=smtp")

        msg = MIMEText(f"Your SyncSupply login code is {code}. It expires in {settings.OTP_EXPIRE_MINUTES} minutes.")
        msg["Subject"] = "Your SyncSupply login code"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = identifier
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return

    if provider == "twilio" and channel == "phone":
        import httpx

        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
            raise RuntimeError("TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER must be set when OTP_PROVIDER=twilio")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        httpx.post(
            url,
            data={
                "From": settings.TWILIO_FROM_NUMBER,
                "To": identifier,
                "Body": f"Your SyncSupply login code is {code}. It expires in {settings.OTP_EXPIRE_MINUTES} minutes.",
            },
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            timeout=10,
        )
        return

    raise RuntimeError(f"No OTP delivery configured for provider={provider!r} channel={channel!r}")
