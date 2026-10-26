"""
Negative tests proving unsafe remedies are excluded — the most important
tests in this suite, since a false negative here is a patient-safety bug.
"""
import pytest

from app.database import SessionLocal
from app.models import Remedy, Herb, HealthProfile
from app.safety import filter_remedies


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def _remedies_for(db, condition_id):
    return db.query(Remedy).filter(Remedy.condition_id == condition_id).all()


def test_allergy_hides_matching_herb(db):
    remedies = db.query(Remedy).limit(5).all()
    assert remedies, "fixture dataset must have remedies loaded"
    target_herb_id = remedies[0].herb_id

    health = HealthProfile(allergies=[target_herb_id])
    result = filter_remedies(remedies, health)

    assert all(r.herb_id != target_herb_id for r in result.visible_remedies)
    assert result.hidden_count >= 1


def test_no_health_profile_shows_everything_without_crashing(db):
    remedies = db.query(Remedy).limit(5).all()
    result = filter_remedies(remedies, None)
    assert len(result.visible_remedies) == len(remedies)
    assert result.hidden_count == 0


def test_pregnancy_tag_hides_pregnancy_contraindicated_remedy(db):
    tagged = db.query(Remedy).filter(Remedy.avoid_tags.contains("pregnancy")).first()
    assert tagged is not None, "dataset must contain at least one pregnancy-tagged remedy"

    health = HealthProfile(is_pregnant=True, allergies=[])
    result = filter_remedies([tagged], health)

    assert tagged not in result.visible_remedies
    assert result.hidden_reasons[tagged.id] == "avoid_if_profile_match"


def test_pregnancy_false_does_not_hide_pregnancy_tagged_remedy(db):
    tagged = db.query(Remedy).filter(Remedy.avoid_tags.contains("pregnancy")).first()
    assert tagged is not None

    health = HealthProfile(is_pregnant=False, allergies=[])
    result = filter_remedies([tagged], health)

    assert tagged in result.visible_remedies


def test_diabetes_tag_hides_diabetes_contraindicated_remedy(db):
    tagged = db.query(Remedy).filter(Remedy.avoid_tags.contains("diabetes")).first()
    assert tagged is not None, "dataset must contain at least one diabetes-tagged remedy"

    health = HealthProfile(has_diabetes=True, allergies=[])
    result = filter_remedies([tagged], health)

    assert tagged not in result.visible_remedies


def test_blood_thinner_tag_hides_contraindicated_remedy(db):
    tagged = db.query(Remedy).filter(Remedy.avoid_tags.contains("blood_thinners")).first()
    assert tagged is not None

    health = HealthProfile(on_blood_thinners=True, allergies=[])
    result = filter_remedies([tagged], health)

    assert tagged not in result.visible_remedies


def _honey_remedy(db):
    for r in db.query(Remedy).all():
        if "honey" in (r.herb.name_en or "").lower():
            return r
    return None


def test_honey_hidden_for_infants_under_one(db):
    honey_remedy = _honey_remedy(db)
    assert honey_remedy is not None, "dataset must contain a remedy using the Honey herb"

    health = HealthProfile(allergies=[], age_years=0, is_pregnant=False, on_blood_thinners=False, on_thyroid_medication=False, has_diabetes=False)
    result = filter_remedies([honey_remedy], health)
    assert honey_remedy not in result.visible_remedies
    assert result.hidden_reasons[honey_remedy.id] == "honey_under_1"


def test_honey_shown_for_adult(db):
    honey_remedy = _honey_remedy(db)
    if honey_remedy is None:
        pytest.skip("dataset has no honey-based remedy to test against")

    health = HealthProfile(allergies=[], age_years=30, is_pregnant=False, on_blood_thinners=False, on_thyroid_medication=False, has_diabetes=False)
    result = filter_remedies([honey_remedy], health)
    assert honey_remedy in result.visible_remedies


def test_hidden_remedies_never_leak_into_visible_list(db):
    """
    Guards the invariant the API layer depends on: visible_remedies must
    never contain anything whose id also appears in hidden_reasons.
    """
    all_remedies = db.query(Remedy).all()
    health = HealthProfile(
        allergies=[all_remedies[0].herb_id] if all_remedies else [],
        is_pregnant=True, on_blood_thinners=True, on_thyroid_medication=True,
        has_diabetes=True, age_years=0,
    )
    result = filter_remedies(all_remedies, health)
    visible_ids = {r.id for r in result.visible_remedies}
    hidden_ids = set(result.hidden_reasons.keys())
    assert visible_ids.isdisjoint(hidden_ids)
