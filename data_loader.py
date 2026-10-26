"""
Loads herbs.csv, conditions.csv and remedies.csv into the database, per
section 6 of the handoff guide. Hardened for production use:

- Validates required columns are present before touching the database.
- Validates referential integrity (every remedy's condition_id/herb_id
  must exist in the other two files) before writing anything.
- Loads inside a single transaction: any failure rolls back completely,
  so a bad CSV never leaves the database half-updated.
- Records a content hash per load so `ensure_dataset_loaded` can detect a
  changed dataset on restart, not just an empty table.
"""
import hashlib
import os
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Herb, Condition, ConditionKeyword, Remedy, DatasetVersion

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

LANG_CODES = ["en", "hi", "ta", "kn", "ml", "te", "mr"]

HERB_REQUIRED_COLS = {"herb_id", "latin_name", "name_en"}
CONDITION_REQUIRED_COLS = {"condition_id", "category", "symptoms_en"}
REMEDY_REQUIRED_COLS = {"condition_id", "herb_id", "preparation_en"}


class DatasetValidationError(Exception):
    pass


def _read_csv(name: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        raise DatasetValidationError(f"Missing dataset file: {name}")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    return df


def _dataset_hash(herbs_df, conditions_df, remedies_df) -> str:
    combined = (
        herbs_df.to_csv(index=False) + conditions_df.to_csv(index=False) + remedies_df.to_csv(index=False)
    )
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _validate(herbs_df: pd.DataFrame, conditions_df: pd.DataFrame, remedies_df: pd.DataFrame) -> None:
    missing_herb_cols = HERB_REQUIRED_COLS - set(herbs_df.columns)
    missing_cond_cols = CONDITION_REQUIRED_COLS - set(conditions_df.columns)
    missing_rem_cols = REMEDY_REQUIRED_COLS - set(remedies_df.columns)
    if missing_herb_cols:
        raise DatasetValidationError(f"herbs.csv is missing required columns: {sorted(missing_herb_cols)}")
    if missing_cond_cols:
        raise DatasetValidationError(f"conditions.csv is missing required columns: {sorted(missing_cond_cols)}")
    if missing_rem_cols:
        raise DatasetValidationError(f"remedies.csv is missing required columns: {sorted(missing_rem_cols)}")

    if herbs_df["herb_id"].duplicated().any():
        dupes = herbs_df[herbs_df["herb_id"].duplicated()]["herb_id"].tolist()
        raise DatasetValidationError(f"herbs.csv has duplicate herb_id values: {dupes}")
    if conditions_df["condition_id"].duplicated().any():
        dupes = conditions_df[conditions_df["condition_id"].duplicated()]["condition_id"].tolist()
        raise DatasetValidationError(f"conditions.csv has duplicate condition_id values: {dupes}")

    herb_ids = set(herbs_df["herb_id"])
    condition_ids = set(conditions_df["condition_id"])

    bad_condition_refs = set(remedies_df["condition_id"]) - condition_ids
    bad_herb_refs = set(remedies_df["herb_id"]) - herb_ids
    if bad_condition_refs:
        raise DatasetValidationError(f"remedies.csv references unknown condition_id values: {sorted(bad_condition_refs)}")
    if bad_herb_refs:
        raise DatasetValidationError(f"remedies.csv references unknown herb_id values: {sorted(bad_herb_refs)}")

    for _, row in herbs_df.iterrows():
        if not row["herb_id"].strip() or not row["name_en"].strip():
            raise DatasetValidationError(f"herbs.csv row has empty herb_id or name_en: {row.to_dict()}")
    for _, row in remedies_df.iterrows():
        if not row["preparation_en"].strip():
            raise DatasetValidationError(f"remedies.csv row has empty preparation_en: {row.to_dict()}")


def load_dataset(db: Session, version_label: str = "seed-v1") -> dict:
    herbs_df = _read_csv("herbs.csv")
    conditions_df = _read_csv("conditions.csv")
    remedies_df = _read_csv("remedies.csv")

    _validate(herbs_df, conditions_df, remedies_df)
    content_hash = _dataset_hash(herbs_df, conditions_df, remedies_df)

    try:
        # --- Herbs ---
        for _, row in herbs_df.iterrows():
            herb = db.query(Herb).filter(Herb.herb_id == row["herb_id"]).first()
            if not herb:
                herb = Herb(herb_id=row["herb_id"])
                db.add(herb)
            herb.latin_name = row.get("latin_name", "")
            for code in LANG_CODES:
                setattr(herb, f"name_{code}", row.get(f"name_{code}", ""))

        # --- Conditions + keywords ---
        db.query(ConditionKeyword).delete()
        for _, row in conditions_df.iterrows():
            condition = db.query(Condition).filter(Condition.condition_id == row["condition_id"]).first()
            if not condition:
                condition = Condition(condition_id=row["condition_id"])
                db.add(condition)
            condition.category = row.get("category", "")
            for code in LANG_CODES:
                col = f"symptoms_{code}"
                value = row.get(col, "")
                setattr(condition, col, value)
                for keyword in [k.strip() for k in value.split("|") if k.strip()]:
                    db.add(ConditionKeyword(condition_id=row["condition_id"], lang=code, keyword=keyword))

        db.flush()

        # --- Remedies ---
        db.query(Remedy).delete()
        for _, row in remedies_df.iterrows():
            reviewed_at_raw = row.get("reviewed_at", "").strip()
            reviewed_at = None
            if reviewed_at_raw:
                try:
                    reviewed_at = datetime.fromisoformat(reviewed_at_raw)
                except ValueError:
                    reviewed_at = None  # malformed date in CSV — treat as unreviewed rather than guessing
            db.add(Remedy(
                condition_id=row["condition_id"],
                herb_id=row["herb_id"],
                preparation_en=row.get("preparation_en", ""),
                avoid_if_en=row.get("avoid_if_en", ""),
                see_doctor_if_en=row.get("see_doctor_if_en", ""),
                avoid_tags=row.get("avoid_tags", ""),
                reviewed_by=row.get("reviewed_by", "").strip() or None,
                reviewed_at=reviewed_at,
                evidence_note=row.get("evidence_note", "").strip() or None,
            ))

        counts = {"herbs": len(herbs_df), "conditions": len(conditions_df), "remedies": len(remedies_df)}
        db.add(DatasetVersion(version_label=f"{version_label}:{content_hash[:12]}", row_counts=counts, loaded_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
        raise

    return counts


def ensure_dataset_loaded(db: Session) -> None:
    """
    Loads the dataset if the herbs table is empty, OR if the CSV content has
    changed since the last recorded load (detected via content hash) — so a
    redeploy with updated data is picked up automatically, while an
    unchanged dataset doesn't pay the reload cost on every restart.
    """
    if db.query(Herb).first() is None:
        load_dataset(db)
        return

    herbs_df = _read_csv("herbs.csv")
    conditions_df = _read_csv("conditions.csv")
    remedies_df = _read_csv("remedies.csv")
    current_hash = _dataset_hash(herbs_df, conditions_df, remedies_df)[:12]

    last_version = db.query(DatasetVersion).order_by(DatasetVersion.loaded_at.desc()).first()
    if last_version and current_hash in (last_version.version_label or ""):
        return  # unchanged — skip reload

    load_dataset(db)
