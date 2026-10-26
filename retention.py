"""
Minimal data-retention housekeeping (handoff guide, section B: "data
minimization, retention limits"). Run at startup — cheap enough for a
free-tier instance that restarts fairly often anyway; a dedicated scheduled
job is the production upgrade path if restarts become infrequent.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import OtpCode, PlacesCache


def purge_expired_otp_codes(db: Session, older_than_hours: int = 24) -> int:
    """OTP codes are useless after they expire or are consumed — don't keep them around."""
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    deleted = (
        db.query(OtpCode)
        .filter((OtpCode.expires_at < cutoff) | (OtpCode.consumed_at.isnot(None) & (OtpCode.created_at < cutoff)))
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def purge_stale_places_cache(db: Session, older_than_days: int = 7) -> int:
    """Cached map results beyond any plausible cache-hit window — just dead rows."""
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    deleted = db.query(PlacesCache).filter(PlacesCache.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return deleted
