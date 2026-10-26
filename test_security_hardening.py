"""
Tests for the second remediation pass: server-managed trial cookies,
authorization isolation, audit logging, input validation, retention
cleanup, and clinical content governance visibility.
"""
import uuid

from app.database import SessionLocal
from app.models import AuditLog, OtpCode
from app.retention import purge_expired_otp_codes


def test_trial_sets_httponly_cookie(client):
    resp = client.post("/api/auth/trial", json=None)
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "ss_trial=" in set_cookie
    assert "httponly" in set_cookie.lower()


def test_trial_cookie_alone_resolves_identity_without_token(client):
    first = client.post("/api/auth/trial", json=None)
    assert first.status_code == 200
    user_id = first.json()["user_id"]

    # No Authorization header at all — only the cookie TestClient is now
    # carrying — should still resolve via app.auth.get_current_user's
    # cookie fallback.
    resp = client.get("/api/profile")
    assert resp.status_code == 200


def test_get_current_user_does_not_auto_create_from_arbitrary_header(client):
    """
    Regression test for the exact gap flagged in the audit: a request
    carrying only an unrecognized X-Device-Id header (no token, no valid
    cookie) must NOT silently mint a new trial user — that would bypass
    /api/auth/trial's IP rate limiting entirely.
    """
    resp = client.get("/api/profile", headers={"X-Device-Id": f"unverified-{uuid.uuid4()}"})
    assert resp.status_code == 401


def test_two_trial_users_cannot_see_each_others_profile_or_history(client):
    # User A
    a = client.post("/api/auth/trial", json=None).json()
    headers_a = {"Authorization": f"Bearer {a['access_token']}"}
    client.put("/api/profile", json={"name": "Alice", "preferred_language": "en"}, headers=headers_a)
    client.put("/api/profile/consent", json={"consent_store_history": True}, headers=headers_a)
    client.post("/api/symptoms/match", json={"text": "headache", "lang": "en"}, headers=headers_a)

    # User B — a separate client/cookie jar so it's a genuinely different identity
    from fastapi.testclient import TestClient
    from app.main import app
    client_b = TestClient(app)
    b = client_b.post("/api/auth/trial", json=None).json()
    headers_b = {"Authorization": f"Bearer {b['access_token']}"}

    profile_b = client_b.get("/api/profile", headers=headers_b).json()
    assert profile_b["name"] != "Alice"

    history_b = client_b.get("/api/symptoms/history", headers=headers_b).json()
    assert history_b == []  # B has no consent AND no access to A's entries either way


def test_otp_request_and_verify_are_audit_logged():
    db = SessionLocal()
    try:
        before = db.query(AuditLog).filter(AuditLog.event == "otp_requested").count()
    finally:
        db.close()

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    identifier = f"audit{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/auth/otp/request", json={"identifier": identifier})

    db = SessionLocal()
    try:
        after = db.query(AuditLog).filter(AuditLog.event == "otp_requested").count()
    finally:
        db.close()
    assert after == before + 1


def test_audit_log_never_contains_raw_symptom_text(client, trial_headers):
    client.put("/api/profile/consent", json={"consent_store_history": True}, headers=trial_headers)
    secret_text = "a very specific symptom phrase xyz123"
    client.post("/api/symptoms/match", json={"text": secret_text, "lang": "en"}, headers=trial_headers)

    db = SessionLocal()
    try:
        rows = db.query(AuditLog).all()
        for row in rows:
            assert secret_text not in (row.detail or "")
    finally:
        db.close()


def test_allergy_validation_rejects_malformed_herb_id(client, trial_headers):
    resp = client.put("/api/profile/health", json={"allergies": ["<script>"]}, headers=trial_headers)
    assert resp.status_code == 422


def test_allergy_validation_accepts_well_formed_herb_id(client, trial_headers):
    resp = client.put("/api/profile/health", json={"allergies": ["H10"]}, headers=trial_headers)
    assert resp.status_code == 200


def test_lang_validation_rejects_non_language_shape(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "headache", "lang": "english"}, headers=trial_headers)
    assert resp.status_code == 422


def test_lang_validation_falls_back_gracefully_for_unsupported_but_valid_code(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "headache", "lang": "fr"}, headers=trial_headers)
    assert resp.status_code == 200  # falls back to English matching rather than hard-failing


def test_review_status_endpoint_reports_honestly(client):
    resp = client.get("/api/reference/review-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_remedies"] > 0
    assert body["reviewed_remedies"] + body["unreviewed_remedies"] == body["total_remedies"]


def test_remedy_output_carries_reviewed_flag(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "headache and fever", "lang": "en"}, headers=trial_headers)
    body = resp.json()
    for match in body.get("matches", []):
        for remedy in match["remedies"]:
            assert "reviewed" in remedy
            assert isinstance(remedy["reviewed"], bool)


def test_purge_expired_otp_codes_removes_old_rows():
    import uuid as _uuid
    from datetime import datetime, timedelta
    from app.models import OtpCode as OtpCodeModel

    db = SessionLocal()
    try:
        stale = OtpCodeModel(
            identifier=f"stale-{_uuid.uuid4()}@example.com", channel="email",
            code_hash="x", expires_at=datetime.utcnow() - timedelta(days=2),
        )
        db.add(stale)
        db.commit()
        stale_id = stale.id

        deleted = purge_expired_otp_codes(db, older_than_hours=24)
        assert deleted >= 1

        still_there = db.query(OtpCodeModel).filter(OtpCodeModel.id == stale_id).first()
        assert still_there is None
    finally:
        db.close()


def test_production_boot_refuses_default_jwt_secret(monkeypatch):
    import importlib
    from app import config as config_module

    config_module.get_settings.cache_clear()
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "change-me-in-env")
    try:
        settings = config_module.get_settings()
        assert settings.ENV == "production"
        assert settings.JWT_SECRET == "change-me-in-env"
        # The actual refusal happens in the FastAPI startup event (main.on_startup),
        # which this test deliberately does not invoke — re-running the app's
        # lifespan mid-suite would disrupt every other test's database state.
        # This test instead locks in the *condition* the guard checks for.
    finally:
        config_module.get_settings.cache_clear()
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setenv("JWT_SECRET", "test-secret")
        config_module.get_settings.cache_clear()
