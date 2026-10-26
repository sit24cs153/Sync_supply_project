from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Herb, Condition, Remedy

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/herbs")
def list_herbs(db: Session = Depends(get_db)):
    herbs = db.query(Herb).all()
    return [
        {"herb_id": h.herb_id, "latin_name": h.latin_name, "name_en": h.name_en,
         "name_hi": h.name_hi, "name_ta": h.name_ta, "name_kn": h.name_kn,
         "name_ml": h.name_ml, "name_te": h.name_te, "name_mr": h.name_mr}
        for h in herbs
    ]


@router.get("/conditions")
def list_conditions(db: Session = Depends(get_db)):
    conditions = db.query(Condition).all()
    return [{"condition_id": c.condition_id, "category": c.category} for c in conditions]


@router.get("/review-status")
def review_status(db: Session = Depends(get_db)):
    """
    Clinical content governance visibility (handoff guide, section A): how
    much of the remedy dataset has an actual recorded reviewer, rather than
    leaving that fact buried. Honest by construction — reviewed_by/at are
    only set when a CSV row actually carries them; nothing here is inferred.
    """
    total = db.query(Remedy).count()
    reviewed = db.query(Remedy).filter(Remedy.reviewed_by.isnot(None), Remedy.reviewed_at.isnot(None)).count()
    return {
        "total_remedies": total,
        "reviewed_remedies": reviewed,
        "unreviewed_remedies": total - reviewed,
        "reviewed_fraction": round(reviewed / total, 3) if total else 0,
    }
