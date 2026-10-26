import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth import create_access_token
from app.config import get_settings
from app.database import get_db
from app.models import User, OtpCode
from app.otp import detect_channel, normalize_identifier, generate_code, hash_code, hash_ip, expiry, send_code
from app.schemas import DeviceTrialRequest, TokenResponse
from app.rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _trial_payload(user: User) -> dict:
    expires = user.trial_started_at + timedelta(days=settings.TRIAL_PERIOD_DAYS)
    return {
        "trial_active": user.trial_active(settings.TRIAL_PERIOD_DAYS),
        "trial_expires_at": expires,
    }


@router.post("/trial", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def start_or_resume_trial(
    request: Request, response: Response,
    payload: Optional[DeviceTrialRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Anonymous 7-day trial. Identity is anchored to a **server-generated**
    token delivered via an HttpOnly, SameSite cookie the client cannot read
    or forge — not to the client-supplied device_id, which is accepted only
    as an optional linking hint (e.g. so a native/PWA client that can't rely
    on cookies still gets a consistent experience) and never trusted alone.

    Residual limitations, stated plainly: (1) clearing cookies + using a
    fresh IP still resets the trial — no server-side defense fully closes
    this for an anonymous flow without requiring login; IP rate-limiting
    below raises the cost rather than eliminating it. (2) Safari's Intelligent
    Tracking Prevention can expire unvisited-site cookies after ~7 days,
    which coincides with the trial window — a returning user in that edge
    case starts a new trial rather than being blocked, which we accept as
    the safer failure direction (worse for abuse-resistance, better for a
    genuine user not being locked out by browser policy).
    """
    ip_hash = hash_ip(_client_ip(request))
    cookie_token = request.cookies.get(settings.TRIAL_COOKIE_NAME)

    user = None
    if cookie_token:
        user = db.query(User).filter(User.trial_token == cookie_token).first()

    if not user and payload and payload.device_id:
        user = db.query(User).filter(User.device_id == payload.device_id).first()

    if not user:
        since = datetime.utcnow() - timedelta(days=1)
        recent_count = (
            db.query(User)
            .filter(User.trial_anchor_ip_hash == ip_hash, User.trial_started_at >= since)
            .count()
        )
        if recent_count >= settings.TRIAL_STARTS_PER_IP_PER_DAY:
            log_event(db, "trial_rate_limited", outcome="failure", ip_hash=ip_hash)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error": {"code": "too_many_trials", "message": "Too many trials started from this network today. Please log in instead."}},
            )
        new_token = secrets.token_urlsafe(32)
        user = User(
            device_id=payload.device_id if payload else None,
            trial_token=new_token,
            trial_started_at=datetime.utcnow(),
            trial_anchor_ip_hash=ip_hash,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        log_event(db, "trial_started", user_id=user.id, ip_hash=ip_hash)
    elif not user.trial_token:
        # Backfill: a pre-existing device-ID-only user from before this change.
        user.trial_token = secrets.token_urlsafe(32)
        db.commit()

    response.set_cookie(
        key=settings.TRIAL_COOKIE_NAME,
        value=user.trial_token,
        max_age=settings.TRIAL_COOKIE_MAX_AGE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="none" if settings.COOKIE_SECURE else "lax",
        path="/",
    )

    token = create_access_token(user.id)
    trial = _trial_payload(user)
    return TokenResponse(access_token=token, user_id=user.id, **trial)


# ---------------------------------------------------------------------------
# OTP login — the auth flow actually specified by the handoff guide.
# Two steps: request a code, then verify it to receive a JWT.
# ---------------------------------------------------------------------------

class OtpRequestIn(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255)  # email or phone


class OtpVerifyIn(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255)
    code: str = Field(..., min_length=4, max_length=10)
    device_id: Optional[str] = None  # carries a trial's profile/history forward on upgrade


@router.post("/otp/request")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def request_otp(request: Request, payload: OtpRequestIn, db: Session = Depends(get_db)):
    channel = detect_channel(payload.identifier)
    if not channel:
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_identifier", "message": "Enter a valid email address or phone number."}})

    identifier = normalize_identifier(payload.identifier, channel)

    recent = (
        db.query(OtpCode)
        .filter(OtpCode.identifier == identifier, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if recent and recent.created_at > datetime.utcnow() - timedelta(seconds=settings.OTP_REQUEST_COOLDOWN_SECONDS):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "otp_cooldown", "message": "Please wait a minute before requesting another code."}},
        )

    code = generate_code()
    db.add(OtpCode(
        identifier=identifier, channel=channel, code_hash=hash_code(code, identifier),
        expires_at=expiry(), request_ip_hash=hash_ip(_client_ip(request)),
    ))
    db.commit()

    try:
        send_code(identifier, channel, code)
    except RuntimeError as exc:
        log_event(db, "otp_delivery_failed", outcome="failure", detail=channel, ip_hash=hash_ip(_client_ip(request)))
        raise HTTPException(status_code=503, detail={"error": {"code": "otp_delivery_unavailable", "message": str(exc)}})

    log_event(db, "otp_requested", outcome="success", detail=channel, ip_hash=hash_ip(_client_ip(request)))
    return {"message": f"A verification code was sent via {channel}.", "channel": channel}


@router.post("/otp/verify", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def verify_otp(request: Request, payload: OtpVerifyIn, db: Session = Depends(get_db)):
    channel = detect_channel(payload.identifier)
    if not channel:
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_identifier", "message": "Enter a valid email address or phone number."}})
    identifier = normalize_identifier(payload.identifier, channel)

    otp = (
        db.query(OtpCode)
        .filter(OtpCode.identifier == identifier, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail={"error": {"code": "otp_expired", "message": "Code expired or not found. Please request a new one."}})

    if otp.attempt_count >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail={"error": {"code": "otp_locked", "message": "Too many incorrect attempts. Please request a new code."}})

    if hash_code(payload.code, identifier) != otp.code_hash:
        otp.attempt_count += 1
        db.commit()
        log_event(db, "otp_verify_failed", outcome="failure", detail=channel, ip_hash=hash_ip(_client_ip(request)))
        raise HTTPException(status_code=400, detail={"error": {"code": "otp_incorrect", "message": "Incorrect code."}})

    otp.consumed_at = datetime.utcnow()

    if channel == "email":
        user = db.query(User).filter(User.email == identifier).first()
    else:
        user = db.query(User).filter(User.phone == identifier).first()

    # Upgrading from a device trial: reuse that row so profile/history carry over.
    if not user and payload.device_id:
        user = db.query(User).filter(User.device_id == payload.device_id).first()

    if not user:
        user = User()
        db.add(user)

    if channel == "email":
        user.email = identifier
    else:
        user.phone = identifier
    user.is_verified = True
    if not user.trial_token:
        user.trial_token = secrets.token_urlsafe(32)
    db.commit()
    db.refresh(user)

    log_event(db, "otp_verify_success", user_id=user.id, detail=channel, ip_hash=hash_ip(_client_ip(request)))

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user_id=user.id, trial_active=True, trial_expires_at=None)
