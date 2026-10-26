import re
import uuid


def test_trial_issues_token(client):
    device_id = f"dev-{uuid.uuid4()}"
    resp = client.post("/api/auth/trial", json={"device_id": device_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["trial_active"] is True
    assert body["access_token"]


def test_trial_is_idempotent_per_device(client):
    device_id = f"dev-{uuid.uuid4()}"
    first = client.post("/api/auth/trial", json={"device_id": device_id}).json()
    second = client.post("/api/auth/trial", json={"device_id": device_id}).json()
    assert first["user_id"] == second["user_id"]


def test_protected_endpoint_requires_auth(client):
    resp = client.get("/api/profile")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_required"


def test_protected_endpoint_works_with_trial_headers(client, trial_headers):
    resp = client.get("/api/profile", headers=trial_headers)
    assert resp.status_code == 200


def test_otp_request_rejects_invalid_identifier(client):
    resp = client.post("/api/auth/otp/request", json={"identifier": "not-an-email-or-phone"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_identifier"


def test_otp_full_login_flow(client, caplog):
    import logging
    identifier = f"user{uuid.uuid4().hex[:8]}@example.com"

    with caplog.at_level(logging.WARNING, logger="syncsupply.otp"):
        resp = client.post("/api/auth/otp/request", json={"identifier": identifier})
        assert resp.status_code == 200

    # Console provider logs the code; extract it the same way a human
    # reading server logs would in this free-tier delivery mode.
    match = None
    for record in caplog.records:
        m = re.search(r": (\d{6}) —", record.getMessage())
        if m:
            match = m.group(1)
    assert match, "OTP code should have been logged by the console provider"

    verify = client.post("/api/auth/otp/verify", json={"identifier": identifier, "code": match})
    assert verify.status_code == 200
    assert verify.json()["access_token"]


def test_otp_verify_rejects_wrong_code(client):
    identifier = f"user{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/auth/otp/request", json={"identifier": identifier})
    resp = client.post("/api/auth/otp/verify", json={"identifier": identifier, "code": "000000"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in ("otp_incorrect", "otp_expired")


def test_otp_verify_rejects_unrequested_code(client):
    identifier = f"user{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/auth/otp/verify", json={"identifier": identifier, "code": "123456"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "otp_expired"


def test_error_response_shape_is_consistent(client):
    resp = client.get("/api/profile")
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
