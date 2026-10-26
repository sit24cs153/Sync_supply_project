"""
Safety filter — section 9 of the handoff guide. Runs after matching and
before any remedy reaches the client.

Two layers, checked in order:
  1. `avoid_tags` — a structured, practitioner-reviewable tag list on each
     remedy (e.g. "pregnancy|diabetes"), matched directly against the
     user's boolean health flags. This is the source of truth.
  2. `avoid_if_en` free text — a fuzzy fallback for any tag the dataset
     hasn't been annotated with yet, so older/unreviewed rows aren't
     silently treated as safe.

Both layers are DATA (CSV content), not hard-coded per-herb logic in
Python, so extending coverage is a dataset change, not a code change.
"""
from dataclasses import dataclass
from typing import List, Optional

from app.matching import normalize
from app.models import HealthProfile, Herb, Remedy

# flag name -> (structured tag, fallback text phrases)
_FLAG_RULES = {
    "is_pregnant": ("pregnancy", ["pregnancy", "pregnant"]),
    "on_blood_thinners": ("blood_thinners", ["blood-thinner", "blood thinner", "bleeding disorder", "anticoagul"]),
    "on_thyroid_medication": ("thyroid", ["thyroid"]),
    "has_diabetes": ("diabetes", ["diabetic", "diabetes", "blood sugar"]),
}

HONEY_LATIN_MARKER = "honey"  # herbs.csv marks honey's latin_name as "Honey (not a plant)"


@dataclass
class SafetyResult:
    visible_remedies: List[Remedy]
    hidden_count: int
    hidden_reasons: dict  # remedy.id -> reason string, for audit/debug


def _tag_set(remedy: Remedy) -> set:
    return {t.strip() for t in (remedy.avoid_tags or "").split("|") if t.strip()}


def _is_honey(herb: Herb) -> bool:
    return HONEY_LATIN_MARKER in (herb.latin_name or "").lower() or "honey" in (herb.name_en or "").lower()


def _age_years(health: Optional[HealthProfile]) -> Optional[int]:
    return health.age_years if health else None


def filter_remedies(remedies: List[Remedy], health: Optional[HealthProfile]) -> SafetyResult:
    visible = []
    hidden_reasons = {}

    allergy_set = {a.strip().upper() for a in (health.allergies if health else []) or []}
    age = _age_years(health)

    for remedy in remedies:
        herb = remedy.herb
        tags = _tag_set(remedy)
        avoid_text_norm = normalize(remedy.avoid_if_en or "")

        # 1. Allergy check — remove any remedy whose herb matches saved allergies.
        if herb.herb_id.upper() in allergy_set or (herb.name_en or "").upper() in allergy_set:
            hidden_reasons[remedy.id] = "allergy"
            continue

        # 2. Honey for infants under 1 year — never show, regardless of other flags.
        if _is_honey(herb) and age is not None and age < 1:
            hidden_reasons[remedy.id] = "honey_under_1"
            continue

        # 3. Structured tags + text fallback against profile flags.
        if health:
            flagged = False
            for flag_name, (tag, phrases) in _FLAG_RULES.items():
                if not getattr(health, flag_name, False):
                    continue
                if tag in tags or any(p in avoid_text_norm for p in phrases):
                    flagged = True
                    break

            if not flagged and age is not None:
                if age < 1 and ("infant" in tags or "infant" in avoid_text_norm):
                    flagged = True
                elif age < 5 and (
                    "young_children" in tags or "children" in avoid_text_norm or "young children" in avoid_text_norm
                ):
                    flagged = True
                elif age > 65 and ("elderly" in tags or "elderly" in avoid_text_norm):
                    flagged = True

            if flagged:
                hidden_reasons[remedy.id] = "avoid_if_profile_match"
                continue

        visible.append(remedy)

    return SafetyResult(visible_remedies=visible, hidden_count=len(hidden_reasons), hidden_reasons=hidden_reasons)
