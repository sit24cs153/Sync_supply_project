import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator

_HERB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
_LANG_CODE_RE = re.compile(r"^[a-z]{2}$")


# ---------- Auth ----------

class DeviceTrialRequest(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    trial_active: bool
    trial_expires_at: Optional[datetime] = None


# ---------- Profile / health ----------

class ProfileIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    age: Optional[int] = Field(None, ge=0, le=120)
    weight_kg: Optional[float] = Field(None, ge=0, le=400)
    date_of_birth: Optional[datetime] = None
    preferred_language: str = "en"
    large_text_mode: bool = False


class ProfileOut(BaseModel):
    # No min_length here: an account with no profile saved yet legitimately
    # returns name="" — ProfileIn (above) is what enforces a real name on
    # the way in. Keeping these separate avoids a validation error on a
    # perfectly normal "no profile yet" response.
    name: str = ""
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    date_of_birth: Optional[datetime] = None
    preferred_language: str = "en"
    large_text_mode: bool = False


class HealthProfileIn(BaseModel):
    allergies: List[str] = []           # herb_id values, e.g. ["H10"]
    is_pregnant: bool = False
    on_blood_thinners: bool = False
    on_thyroid_medication: bool = False
    has_diabetes: bool = False
    existing_conditions: List[str] = []
    age_years: Optional[int] = Field(None, ge=0, le=120)

    @field_validator("allergies")
    @classmethod
    def _validate_allergy_ids(cls, values: List[str]) -> List[str]:
        # Reject anything that isn't a plausible herb_id shape up front —
        # the safety filter also normalizes/ignores unmatched values, but
        # malformed input shouldn't silently pass through unvalidated.
        for v in values:
            if not _HERB_ID_RE.match(v.strip()):
                raise ValueError(f"'{v}' is not a valid herb identifier")
        return [v.strip().upper() for v in values]


class HealthProfileOut(HealthProfileIn):
    pass


class ConsentIn(BaseModel):
    consent_store_history: bool


class ConsentOut(BaseModel):
    consent_store_history: bool


# ---------- Symptom matching ----------

class SymptomMatchRequest(BaseModel):
    # Deliberately loose at the schema layer (max_length well above the real
    # limit) so empty/too-long text reaches the route handler and produces
    # the documented {"error": {"code": "empty_text"/"text_too_long", ...}}
    # response instead of a generic 422 validation error.
    text: str = Field(..., max_length=5000)
    lang: str = "en"
    source: str = "text"  # "text" | "voice"

    @field_validator("lang")
    @classmethod
    def _validate_lang_shape(cls, v: str) -> str:
        # Shape-validate only (e.g. reject "english" or injected junk); an
        # unsupported-but-well-formed code (say "fr") is still accepted here
        # and gracefully falls back to English in the route handler, since
        # a voice-recognition locale mismatch shouldn't hard-fail the request.
        if not _LANG_CODE_RE.match(v.strip().lower()):
            raise ValueError("lang must be a 2-letter language code, e.g. 'en'")
        return v.strip().lower()

    @field_validator("source")
    @classmethod
    def _validate_source(cls, v: str) -> str:
        if v not in ("text", "voice"):
            raise ValueError("source must be 'text' or 'voice'")
        return v


class RemedyOut(BaseModel):
    herb_id: str
    herb_name: str
    latin_name: str
    preparation: str
    avoid_if: Optional[str] = None
    warnings: List[str] = []
    see_doctor_if: Optional[str] = None
    hidden_reason: Optional[str] = None  # set only when debug-level visibility is needed
    reviewed: bool = False  # True once a qualified practitioner has signed off (clinical content governance)


class ConditionMatchOut(BaseModel):
    condition_id: str
    category: str
    score: float
    remedies: List[RemedyOut]
    hidden_for_safety: int = 0


class SymptomMatchResponse(BaseModel):
    emergency: bool
    emergency_number: Optional[str] = None
    disclaimer: str
    matches: List[ConditionMatchOut] = []
    message: Optional[str] = None  # shown when nothing matched


# ---------- Nearby care ----------

class NearbyRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_text: Optional[str] = None  # town / pin code fallback
    lang: str = "en"
    kind: str = "ayurvedic"  # "ayurvedic" | "hospital" | "homeopathy"


class PlaceOut(BaseModel):
    name: str
    address: Optional[str] = None
    distance_meters: Optional[float] = None
    open_now: Optional[bool] = None
    maps_url: str
    phone: Optional[str] = None


class NearbyResponse(BaseModel):
    places: List[PlaceOut]
    message: Optional[str] = None


# ---------- Errors ----------

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
