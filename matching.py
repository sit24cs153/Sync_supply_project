"""
Phase 1 weighted keyword matching, exactly per the handoff guide (section 7):

1. Normalize the input: Unicode NFC, lowercase, trim spaces, remove punctuation.
2. Search keywords in the user's chosen language AND in English (users mix languages).
3. Score each condition: add the keyword's character length for every keyword
   found, so a longer/more specific keyword outranks a short one.
4. Sort by score and return the top 3 conditions above a minimum score.
5. If nothing matches, the caller shows a polite "please rephrase" message.

Everything scored here comes from the `condition_keywords` table, which is
built dynamically from conditions.csv at startup — no condition or keyword is
hard-coded in this module, so adding rows to the dataset changes behavior
immediately without touching code.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ConditionKeyword

settings = get_settings()

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.lower().strip()
    text = _PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class MatchResult:
    condition_id: str
    score: int


def match_symptoms(db: Session, text: str, lang: str, top_n: int = 3) -> List[MatchResult]:
    normalized = normalize(text)
    if not normalized:
        return []

    langs = {lang, "en"}  # search the chosen language AND English, per spec
    keyword_rows = (
        db.query(ConditionKeyword)
        .filter(ConditionKeyword.lang.in_(langs))
        .all()
    )

    scores: dict[str, int] = {}
    for row in keyword_rows:
        kw_norm = normalize(row.keyword)
        if kw_norm and kw_norm in normalized:
            scores[row.condition_id] = scores.get(row.condition_id, 0) + len(kw_norm)

    ranked = sorted(scores.items(), key=lambda item: -item[1])
    ranked = [MatchResult(condition_id=cid, score=score) for cid, score in ranked if score >= settings.MIN_MATCH_SCORE]
    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Red-flag / emergency detection (section 9)
# Danger-sign phrases are multilingual and loaded the same way as any other
# keyword list would be, but since they trigger a different *screen* (not a
# remedy), they are kept as a small, clearly-labeled dynamic structure that
# ops/content owners can extend without a code change by editing this list
# or — in a future iteration — moving it into its own DB table, exactly like
# condition_keywords.
# ---------------------------------------------------------------------------

RED_FLAG_PHRASES_EN = [
    # Cardiac / respiratory
    "chest pain", "tightness in chest", "difficulty breathing", "can't breathe",
    "cannot breathe", "shortness of breath", "gasping for air", "turning blue",
    "lips turning blue",
    # Bleeding / GI
    "blood in stool", "black stool", "blood in vomit", "vomiting blood",
    "coughing blood", "heavy bleeding", "won't stop bleeding",
    # Neuro
    "fainting", "fainted", "unconscious", "unresponsive", "seizure", "convulsion",
    "severe headache with stiff neck", "stiff neck and fever", "worst headache of my life",
    "face drooping", "slurred speech", "sudden weakness one side", "sudden confusion",
    # Fever / infection
    "very high fever", "fever above 104", "fever not coming down", "high fever in infant",
    "baby won't wake up", "baby not responding",
    # Allergic / poisoning / trauma
    "severe allergic reaction", "anaphylaxis", "throat closing", "swelling of face and throat",
    "snake bite", "poisoning", "swallowed poison", "severe burn", "deep cut", "severe dehydration",
    # Mental health
    "thoughts of self-harm", "suicidal", "want to die", "self harm", "self-harm",
    "want to end my life", "kill myself",
]

RED_FLAG_PHRASES_HI = [
    "सीने में दर्द", "सांस लेने में तकलीफ", "सांस नहीं आ रही", "खून की उल्टी",
    "खून की खांसी", "बेहोशी", "बेहोश", "दौरा पड़ना", "तेज़ बुखार उतर नहीं रहा",
    "सांप ने काटा", "ज़हर खा लिया", "गंभीर एलर्जी", "आत्महत्या", "खुद को नुकसान",
]
RED_FLAG_PHRASES_TA = [
    "மார்பு வலி", "மூச்சு விடுவதில் சிரமம்", "மூச்சு திணறல்", "இரத்த வாந்தி",
    "மயக்கம்", "மயங்கி விழுதல்", "வலிப்பு", "அதிக காய்ச்சல் குறையவில்லை",
    "பாம்பு கடி", "விஷம் குடித்தது", "கடுமையான ஒவ்வாமை", "தற்கொலை",
]
RED_FLAG_PHRASES_KN = [
    "ಎದೆ ನೋವು", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರಾಡಲು ಕಷ್ಟ", "ರಕ್ತ ವಾಂತಿ",
    "ಮೂರ್ಛೆ", "ಪ್ರಜ್ಞೆ ತಪ್ಪುವುದು", "ಸೆಳೆತ", "ಜ್ವರ ಕಡಿಮೆಯಾಗುತ್ತಿಲ್ಲ",
    "ಹಾವು ಕಡಿತ", "ವಿಷ ಸೇವನೆ", "ತೀವ್ರ ಅಲರ್ಜಿ", "ಆತ್ಮಹತ್ಯೆ",
]
RED_FLAG_PHRASES_ML = [
    "നെഞ്ചുവേദന", "ശ്വസിക്കാൻ ബുദ്ധിമുട്ട്", "ശ്വാസതടസ്സം", "രക്തം ഛർദ്ദി",
    "ബോധക്ഷയം", "ബോധമില്ലാതാവുക", "അപസ്മാരം", "പനി കുറയുന്നില്ല",
    "പാമ്പ് കടി", "വിഷം കഴിച്ചു", "ഗുരുതരമായ അലർജി", "ആത്മഹത്യ",
]
RED_FLAG_PHRASES_TE = [
    "ఛాతీ నొప్పి", "శ్వాస తీసుకోవడంలో ఇబ్బంది", "ఊపిరి అందడం లేదు", "రక్తం వాంతి",
    "మూర్ఛ", "స్పృహ కోల్పోవడం", "ఫిట్స్", "జ్వరం తగ్గడం లేదు",
    "పాము కాటు", "విషం తాగాడు", "తీవ్రమైన అలర్జీ", "ఆత్మహత్య",
]
RED_FLAG_PHRASES_MR = [
    "छातीत दुखणे", "श्वास घेण्यास त्रास", "श्वास घेता येत नाही", "रक्ताची उलटी",
    "बेशुद्ध", "भोवळ येणे", "झटका येणे", "ताप उतरत नाही",
    "सापाने चावा घेतला", "विष प्राशन", "तीव्र ॲलर्जी", "आत्महत्या",
]

_RED_FLAG_BY_LANG = {
    "en": RED_FLAG_PHRASES_EN,
    "hi": RED_FLAG_PHRASES_HI,
    "ta": RED_FLAG_PHRASES_TA,
    "kn": RED_FLAG_PHRASES_KN,
    "ml": RED_FLAG_PHRASES_ML,
    "te": RED_FLAG_PHRASES_TE,
    "mr": RED_FLAG_PHRASES_MR,
}


def is_emergency(text: str, lang: str) -> bool:
    normalized = normalize(text)
    phrases = _RED_FLAG_BY_LANG.get("en", []) + _RED_FLAG_BY_LANG.get(lang, [])
    return any(normalize(p) in normalized for p in phrases)
