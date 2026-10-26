import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Dataset tables — populated dynamically from the CSV files at startup
# (see data_loader.py). Nothing about herbs/conditions/remedies is hard-coded
# in application logic; everything is read from these tables.
# ---------------------------------------------------------------------------

class Herb(Base):
    __tablename__ = "herbs"

    herb_id = Column(String(8), primary_key=True)
    latin_name = Column(String(255), nullable=False)
    name_en = Column(String(255), nullable=False)
    name_hi = Column(String(255))
    name_ta = Column(String(255))
    name_kn = Column(String(255))
    name_ml = Column(String(255))
    name_te = Column(String(255))
    name_mr = Column(String(255))

    def localized_name(self, lang: str) -> str:
        return getattr(self, f"name_{lang}", None) or self.name_en


class Condition(Base):
    __tablename__ = "conditions"

    condition_id = Column(String(8), primary_key=True)
    category = Column(String(100), nullable=False)
    symptoms_en = Column(Text)
    symptoms_hi = Column(Text)
    symptoms_ta = Column(Text)
    symptoms_kn = Column(Text)
    symptoms_ml = Column(Text)
    symptoms_te = Column(Text)
    symptoms_mr = Column(Text)

    keywords = relationship("ConditionKeyword", back_populates="condition", cascade="all, delete-orphan")


class ConditionKeyword(Base):
    """
    One row per (condition, language, keyword) — this is the
    `condition_keywords` table referenced by the matching spec (section 7).
    Built dynamically from the `|`-separated symptom columns in conditions.csv,
    never hard-coded in Python.
    """
    __tablename__ = "condition_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    condition_id = Column(String(8), ForeignKey("conditions.condition_id"), nullable=False, index=True)
    lang = Column(String(8), nullable=False, index=True)
    keyword = Column(String(255), nullable=False, index=True)

    condition = relationship("Condition", back_populates="keywords")


class Remedy(Base):
    __tablename__ = "remedies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    condition_id = Column(String(8), ForeignKey("conditions.condition_id"), nullable=False, index=True)
    herb_id = Column(String(8), ForeignKey("herbs.herb_id"), nullable=False, index=True)
    preparation_en = Column(Text, nullable=False)
    avoid_if_en = Column(Text)
    see_doctor_if_en = Column(Text)
    # Structured, machine-checkable contraindication tags (e.g. "pregnancy|diabetes").
    # The safety filter checks these FIRST and falls back to fuzzy text matching
    # on avoid_if_en only as a second layer — tags are the source of truth and
    # must be set/reviewed by a qualified practitioner alongside avoid_if_en.
    avoid_tags = Column(String(255), default="")
    # Clinical content governance (handoff guide, section A): who reviewed
    # this remedy, when, and on what evidence. Empty/null means "not yet
    # reviewed" — deliberately not defaulted to a fake reviewer, so the gap
    # is visible rather than hidden.
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    evidence_note = Column(Text, nullable=True)

    condition = relationship("Condition")
    herb = relationship("Herb")


class DatasetVersion(Base):
    """Tracks which dataset snapshot is loaded and who reviewed it (section 9: content review)."""
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_label = Column(String(64), nullable=False)
    row_counts = Column(JSON)
    reviewer_name = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    loaded_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# User / account tables
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(32), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=True)  # legacy/optional; OTP is the primary login path
    device_id = Column(String(64), unique=True, nullable=True, index=True)  # client-sent hint only; NOT trusted for identity
    trial_token = Column(String(64), unique=True, nullable=True, index=True)  # server-generated, set via HttpOnly cookie — the actual trial anchor
    trial_anchor_ip_hash = Column(String(64), nullable=True)  # hashed IP that started the trial, for abuse rate-limiting
    created_at = Column(DateTime, default=datetime.utcnow)
    trial_started_at = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)
    # Explicit, revocable consent to store raw symptom-query text for history/debugging.
    # Defaults to False: until a user opts in, queries are matched but not retained verbatim.
    consent_store_history = Column(Boolean, default=False)

    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    health = relationship("HealthProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def trial_active(self, trial_days: int) -> bool:
        if self.hashed_password or self.is_verified:
            return True  # logged-in users are never trial-limited
        return datetime.utcnow() < self.trial_started_at + timedelta(days=trial_days)


class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    name = Column(String(255))
    age = Column(Integer)
    weight_kg = Column(Float, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    preferred_language = Column(String(8), default="en")
    large_text_mode = Column(Boolean, default=False)

    user = relationship("User", back_populates="profile")


class HealthProfile(Base):
    """
    Drives the safety filter (section 9): allergies + condition flags such as
    pregnancy, blood thinners, thyroid medication, diabetes, age-based rules.
    """
    __tablename__ = "health_profiles"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    allergies = Column(JSON, default=list)          # e.g. ["H10", "H11"] or free-text herb/latin names
    is_pregnant = Column(Boolean, default=False)
    on_blood_thinners = Column(Boolean, default=False)
    on_thyroid_medication = Column(Boolean, default=False)
    has_diabetes = Column(Boolean, default=False)
    existing_conditions = Column(JSON, default=list)
    age_years = Column(Integer, nullable=True)       # mirrors profile.age for quick safety checks

    user = relationship("User", back_populates="health")


class SymptomQueryLog(Base):
    """
    History of symptom queries — only created when the user has given
    `consent_store_history`. Even then, raw text is never required for the
    app to function: matching happens in-request and nothing here is read
    back except by the user's own /history and /export endpoints.
    """
    __tablename__ = "symptom_query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    lang = Column(String(8), nullable=False)
    source = Column(String(16), default="text")  # "text" | "voice"
    emergency = Column(Boolean, default=False)
    matched_condition_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class OtpCode(Base):
    """
    One-time passcodes for email/phone login, per the handoff guide's
    specified auth flow. Codes are stored hashed and short-lived; a request
    invalidates any earlier unused code for the same identifier.
    """
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    identifier = Column(String(255), nullable=False, index=True)  # email or phone, normalized
    channel = Column(String(8), nullable=False)  # "email" | "phone"
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    request_ip_hash = Column(String(64), nullable=True)


class AuditLog(Base):
    """
    Security-relevant event log (handoff guide, section B: "record
    security-relevant events without unnecessarily logging sensitive symptom
    text"). Deliberately narrow: an event name, the acting user, outcome,
    and a hashed IP — never symptom text, never OTP codes.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event = Column(String(64), nullable=False, index=True)  # e.g. "otp_verify_success", "account_deleted"
    user_id = Column(String(36), nullable=True, index=True)
    outcome = Column(String(16), default="success")  # "success" | "failure"
    detail = Column(String(255), nullable=True)  # short, non-sensitive context only
    ip_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PlacesCache(Base):
    """Short-lived cache of Google Places results, keyed by rounded lat/lng (section 10)."""
    __tablename__ = "places_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(128), unique=True, index=True)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
