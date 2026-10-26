from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.matching import match_symptoms, is_emergency
from app.models import User, Condition, Remedy, SymptomQueryLog
from app.rate_limit import limiter
from app.safety import filter_remedies
from app.schemas import SymptomMatchRequest, SymptomMatchResponse, ConditionMatchOut, RemedyOut

router = APIRouter(prefix="/api/symptoms", tags=["symptoms"])
settings = get_settings()

DISCLAIMER = (
    "SyncSupply gives traditional home-remedy information. It is not medical "
    "advice and does not replace a doctor."
)

NO_MATCH_MESSAGES = {
    "en": "We couldn't match that to a condition. Please try rephrasing, speak again, or contact a doctor.",
    "hi": "हम इसे किसी स्थिति से नहीं जोड़ पाए। कृपया दोबारा बताएं, फिर से बोलें, या डॉक्टर से संपर्क करें।",
}


def _log_query(db: Session, user: User, text: str, lang: str, source: str, emergency: bool, matched_ids: list) -> None:
    """
    Only persists raw symptom text when the user has opted in. This keeps
    matching fully functional for everyone (matching happens synchronously
    in this request regardless) while making "/history" and "/export"
    meaningful only for users who asked for it — per the guide's requirement
    to handle symptom data as sensitive and consent-aware.
    """
    if not user.consent_store_history:
        return
    db.add(SymptomQueryLog(
        user_id=user.id, text=text, lang=lang, source=source,
        emergency=emergency, matched_condition_ids=matched_ids,
    ))
    db.commit()


@router.post("/match", response_model=SymptomMatchResponse)
@limiter.limit(settings.RATE_LIMIT_SYMPTOMS)
def match(request: Request, payload: SymptomMatchRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail={"error": {"code": "empty_text", "message": "Symptom text is required."}})
    if len(text) > settings.MAX_SYMPTOM_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail={"error": {"code": "text_too_long", "message": "Symptom text is too long."}})

    lang = payload.lang if payload.lang in settings.supported_languages_list else "en"

    emergency = is_emergency(text, lang)

    if emergency:
        _log_query(db, user, text, lang, payload.source, True, [])
        return SymptomMatchResponse(
            emergency=True,
            emergency_number=settings.EMERGENCY_NUMBER_INDIA,
            disclaimer=DISCLAIMER,
            matches=[],
            message="This may be a medical emergency. Please seek immediate care.",
        )

    ranked = match_symptoms(db, text, lang)

    if not ranked:
        _log_query(db, user, text, lang, payload.source, False, [])
        return SymptomMatchResponse(
            emergency=False,
            disclaimer=DISCLAIMER,
            matches=[],
            message=NO_MATCH_MESSAGES.get(lang, NO_MATCH_MESSAGES["en"]),
        )

    health = user.health
    results = []
    for r in ranked:
        condition = db.query(Condition).filter(Condition.condition_id == r.condition_id).first()
        if not condition:
            continue

        # Fail-safe: if anything in safety evaluation raises, this condition
        # is withheld entirely rather than falling back to showing
        # unfiltered remedies. A withheld condition still surfaces (with
        # zero remedies) so the user sees *something* was found and isn't
        # left staring at an empty screen with no explanation, but nothing
        # unverified reaches them.
        remedies = []
        try:
            remedies = db.query(Remedy).filter(Remedy.condition_id == r.condition_id).all()
            safety = filter_remedies(remedies, health)

            # Invariant this endpoint guarantees: nothing in
            # `safety.hidden_reasons` is ever read into `remedy_out` below —
            # `visible_remedies` is the only source for what the client sees.
            remedy_out = []
            for rem in safety.visible_remedies:
                herb = rem.herb
                remedy_out.append(RemedyOut(
                    herb_id=herb.herb_id,
                    herb_name=herb.localized_name(lang),
                    latin_name=herb.latin_name,
                    preparation=rem.preparation_en,
                    avoid_if=rem.avoid_if_en or None,
                    warnings=[rem.avoid_if_en] if rem.avoid_if_en else [],
                    see_doctor_if=rem.see_doctor_if_en or None,
                    reviewed=bool(rem.reviewed_by and rem.reviewed_at),
                ))
            hidden_count = safety.hidden_count
        except Exception:
            remedy_out = []
            hidden_count = len(remedies)  # everything found is withheld, counted as hidden

        results.append(ConditionMatchOut(
            condition_id=condition.condition_id,
            category=condition.category,
            score=round(r.score / max(len(text), 1), 4),
            remedies=remedy_out,
            hidden_for_safety=hidden_count,
        ))

    _log_query(db, user, text, lang, payload.source, False, [m.condition_id for m in results])

    return SymptomMatchResponse(emergency=False, disclaimer=DISCLAIMER, matches=results)


@router.get("/history")
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 20):
    if not user.consent_store_history:
        return []
    rows = (
        db.query(SymptomQueryLog)
        .filter(SymptomQueryLog.user_id == user.id)
        .order_by(SymptomQueryLog.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "text": r.text, "lang": r.lang, "emergency": r.emergency,
            "matched_condition_ids": r.matched_condition_ids, "created_at": r.created_at,
        }
        for r in rows
    ]
