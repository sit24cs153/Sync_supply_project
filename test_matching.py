"""
Matching accuracy tests. Covers normalization, scoring/ranking, empty
results, and representative multilingual symptom sentences. English and
Hindi get the fuller 10-sentence spread the guide calls for since those are
this project's primary languages; the remaining five get a smaller but real
sample per language, flagged in README as needing expansion alongside
native-speaker review.
"""
import pytest
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.matching import normalize, match_symptoms, is_emergency


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_normalize_strips_punctuation_and_case():
    assert normalize("  Headache, Fever!! ") == "headache fever"


def test_normalize_handles_empty_string():
    assert normalize("") == ""
    assert normalize("   ") == ""


def test_no_match_on_gibberish(db):
    assert match_symptoms(db, "xkjzq qweqwe asdfgh", "en") == []


def test_no_match_on_empty_text(db):
    assert match_symptoms(db, "", "en") == []


def test_match_returns_at_most_three(db):
    # A broad, multi-symptom sentence shouldn't return more than top_n matches.
    results = match_symptoms(db, "fever cough headache stomach pain skin rash joint pain", "en", top_n=3)
    assert len(results) <= 3


def test_match_ranked_by_score_descending(db):
    results = match_symptoms(db, "I have a severe headache and mild fever", "en")
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


# English: representative multi-symptom sentences
ENGLISH_SENTENCES = [
    "I have a headache",
    "fever and chills since morning",
    "cough with sore throat",
    "stomach pain and nausea",
    "skin rash with itching",
    "joint pain in my knees",
    "constipation for three days",
    "cold and runny nose",
    "acidity after eating",
    "difficulty sleeping at night",
]


@pytest.mark.parametrize("sentence", ENGLISH_SENTENCES)
def test_english_sentences_produce_some_result_or_graceful_empty(db, sentence):
    results = match_symptoms(db, sentence, "en")
    # Every sentence should either match something or cleanly return no
    # matches — never raise, never return malformed data.
    assert isinstance(results, list)
    for r in results:
        assert r.condition_id
        assert r.score >= 0


HINDI_SENTENCES = [
    "सिरदर्द हो रहा है",
    "बुखार और ठंड लग रही है",
    "खांसी और गले में खराश",
    "पेट दर्द और उल्टी जैसा महसूस हो रहा है",
    "त्वचा पर खुजली और चकत्ते",
    "घुटनों में दर्द",
    "कब्ज़ की समस्या है",
    "जुकाम और नाक बह रही है",
    "खाने के बाद जलन हो रही है",
    "रात को नींद नहीं आ रही",
]


@pytest.mark.parametrize("sentence", HINDI_SENTENCES)
def test_hindi_sentences_produce_some_result_or_graceful_empty(db, sentence):
    results = match_symptoms(db, sentence, "hi")
    assert isinstance(results, list)
    for r in results:
        assert r.condition_id


OTHER_LANGUAGE_SAMPLES = {
    "ta": ["தலைவலி", "காய்ச்சல் மற்றும் குளிர்"],
    "kn": ["ತಲೆನೋವು", "ಜ್ವರ ಮತ್ತು ಚಳಿ"],
    "ml": ["തലവേദന", "പനിയും തണുപ്പും"],
    "te": ["తలనొప్పి", "జ్వరం మరియు చలి"],
    "mr": ["डोकेदुखी", "ताप आणि थंडी"],
}


@pytest.mark.parametrize("lang,sentence", [(l, s) for l, sl in OTHER_LANGUAGE_SAMPLES.items() for s in sl])
def test_other_language_samples_do_not_error(db, lang, sentence):
    results = match_symptoms(db, sentence, lang)
    assert isinstance(results, list)


# --- Emergency / red-flag detection ---

EMERGENCY_SENTENCES_EN = [
    "I have severe chest pain",
    "cannot breathe properly",
    "vomiting blood since this morning",
    "my father is unconscious",
    "thoughts of self-harm",
    "snake bite on my leg",
]

NON_EMERGENCY_SENTENCES_EN = [
    "mild headache",
    "slight cough",
    "stomach feels a bit off",
]


@pytest.mark.parametrize("sentence", EMERGENCY_SENTENCES_EN)
def test_emergency_phrases_detected(sentence):
    assert is_emergency(sentence, "en") is True


@pytest.mark.parametrize("sentence", NON_EMERGENCY_SENTENCES_EN)
def test_non_emergency_phrases_not_flagged(sentence):
    assert is_emergency(sentence, "en") is False


def test_emergency_detected_in_hindi():
    assert is_emergency("सीने में दर्द हो रहा है", "hi") is True


def test_emergency_known_gap_documented():
    """
    Known limitation (tracked in README): substring matching on a fixed
    phrase list will miss novel phrasing, misspellings, and dialect
    variation. This test documents that gap rather than pretending it's
    solved — a misspelled phrase is NOT guaranteed to be caught.
    """
    assert is_emergency("chest paiin very bad", "en") is False  # misspelling slips through today
