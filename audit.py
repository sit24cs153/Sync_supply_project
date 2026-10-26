"""Narrow, append-only security event logging. Never pass symptom text or OTP codes here."""
from sqlalchemy.orm import Session

from app.models import AuditLog


def log_event(db: Session, event: str, user_id: str | None = None, outcome: str = "success",
              detail: str | None = None, ip_hash: str | None = None) -> None:
    db.add(AuditLog(event=event, user_id=user_id, outcome=outcome, detail=detail, ip_hash=ip_hash))
    db.commit()
