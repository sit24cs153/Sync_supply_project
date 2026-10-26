from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth import get_current_user
from app.database import get_db
from app.models import User, Profile, HealthProfile, SymptomQueryLog
from app.schemas import ProfileIn, ProfileOut, HealthProfileIn, HealthProfileOut, ConsentIn, ConsentOut

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user)):
    p = user.profile
    if not p:
        return ProfileOut(name="", age=None, weight_kg=None, date_of_birth=None, preferred_language="en", large_text_mode=False)
    return ProfileOut(
        name=p.name or "", age=p.age, weight_kg=p.weight_kg, date_of_birth=p.date_of_birth,
        preferred_language=p.preferred_language, large_text_mode=p.large_text_mode,
    )


@router.put("", response_model=ProfileOut)
def upsert_profile(payload: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = user.profile
    if not p:
        p = Profile(user_id=user.id)
        db.add(p)
    p.name = payload.name
    p.age = payload.age
    p.weight_kg = payload.weight_kg
    p.date_of_birth = payload.date_of_birth
    p.preferred_language = payload.preferred_language
    p.large_text_mode = payload.large_text_mode
    db.commit()
    return payload


@router.get("/health", response_model=HealthProfileOut)
def get_health(user: User = Depends(get_current_user)):
    h = user.health
    if not h:
        return HealthProfileOut()
    return HealthProfileOut(
        allergies=h.allergies or [], is_pregnant=h.is_pregnant, on_blood_thinners=h.on_blood_thinners,
        on_thyroid_medication=h.on_thyroid_medication, has_diabetes=h.has_diabetes,
        existing_conditions=h.existing_conditions or [], age_years=h.age_years,
    )


@router.put("/health", response_model=HealthProfileOut)
def upsert_health(payload: HealthProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    h = user.health
    if not h:
        h = HealthProfile(user_id=user.id)
        db.add(h)
    h.allergies = payload.allergies
    h.is_pregnant = payload.is_pregnant
    h.on_blood_thinners = payload.on_blood_thinners
    h.on_thyroid_medication = payload.on_thyroid_medication
    h.has_diabetes = payload.has_diabetes
    h.existing_conditions = payload.existing_conditions
    h.age_years = payload.age_years
    db.commit()
    return payload


# ---------------------------------------------------------------------------
# Privacy controls — consent, history deletion, data export, account deletion.
# Raw symptom text (SymptomQueryLog.text) is only ever written when
# consent_store_history is True; see routers/symptoms.py. These endpoints
# let a user change that consent and act on data already stored.
# ---------------------------------------------------------------------------

@router.get("/consent", response_model=ConsentOut)
def get_consent(user: User = Depends(get_current_user)):
    return ConsentOut(consent_store_history=user.consent_store_history)


@router.put("/consent", response_model=ConsentOut)
def set_consent(payload: ConsentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.consent_store_history = payload.consent_store_history
    db.commit()
    log_event(db, "consent_changed", user_id=user.id, detail=str(payload.consent_store_history))
    return payload


@router.delete("/history")
def delete_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = db.query(SymptomQueryLog).filter(SymptomQueryLog.user_id == user.id).delete()
    db.commit()
    return {"deleted": deleted}


@router.get("/export")
def export_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Machine-readable export of everything stored about this user (data portability)."""
    history = db.query(SymptomQueryLog).filter(SymptomQueryLog.user_id == user.id).all()
    return {
        "account": {"id": user.id, "email": user.email, "phone": user.phone, "created_at": user.created_at},
        "profile": {
            "name": user.profile.name if user.profile else None,
            "age": user.profile.age if user.profile else None,
            "weight_kg": user.profile.weight_kg if user.profile else None,
            "preferred_language": user.profile.preferred_language if user.profile else None,
        } if user.profile else None,
        "health": {
            "allergies": user.health.allergies if user.health else [],
            "is_pregnant": user.health.is_pregnant if user.health else None,
            "on_blood_thinners": user.health.on_blood_thinners if user.health else None,
            "on_thyroid_medication": user.health.on_thyroid_medication if user.health else None,
            "has_diabetes": user.health.has_diabetes if user.health else None,
        } if user.health else None,
        "consent_store_history": user.consent_store_history,
        "symptom_history": [
            {"text": h.text, "lang": h.lang, "emergency": h.emergency, "created_at": h.created_at}
            for h in history
        ],
    }


@router.delete("/account")
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently deletes the account and all associated data (right to erasure)."""
    user_id = user.id
    db.query(SymptomQueryLog).filter(SymptomQueryLog.user_id == user.id).delete()
    if user.profile:
        db.delete(user.profile)
    if user.health:
        db.delete(user.health)
    db.delete(user)
    db.commit()
    log_event(db, "account_deleted", user_id=user_id)
    return {"deleted": True}
