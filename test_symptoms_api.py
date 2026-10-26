def test_match_rejects_empty_text(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "", "lang": "en"}, headers=trial_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "empty_text"


def test_match_rejects_overlong_text(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "a" * 1000, "lang": "en"}, headers=trial_headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "text_too_long"


def test_match_returns_disclaimer_always(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "headache", "lang": "en"}, headers=trial_headers)
    assert resp.status_code == 200
    assert resp.json()["disclaimer"]


def test_emergency_text_returns_emergency_flag_and_no_remedies(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "severe chest pain", "lang": "en"}, headers=trial_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["emergency"] is True
    assert body["matches"] == []
    assert body["emergency_number"]


def test_no_match_message_present(client, trial_headers):
    resp = client.post("/api/symptoms/match", json={"text": "zzz qqq xxx", "lang": "en"}, headers=trial_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["matches"] == []
    assert body["message"]


def test_history_empty_without_consent(client, trial_headers):
    client.post("/api/symptoms/match", json={"text": "headache", "lang": "en"}, headers=trial_headers)
    resp = client.get("/api/symptoms/history", headers=trial_headers)
    assert resp.status_code == 200
    assert resp.json() == []  # consent defaults to False — nothing retained


def test_history_populated_after_consent(client, trial_headers):
    consent = client.put("/api/profile/consent", json={"consent_store_history": True}, headers=trial_headers)
    assert consent.status_code == 200

    client.post("/api/symptoms/match", json={"text": "headache and fever", "lang": "en"}, headers=trial_headers)
    resp = client.get("/api/symptoms/history", headers=trial_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    assert body[0]["text"]


def test_delete_history_clears_log(client, trial_headers):
    client.put("/api/profile/consent", json={"consent_store_history": True}, headers=trial_headers)
    client.post("/api/symptoms/match", json={"text": "cough", "lang": "en"}, headers=trial_headers)

    deleted = client.delete("/api/profile/history", headers=trial_headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] >= 1

    after = client.get("/api/symptoms/history", headers=trial_headers)
    assert after.json() == []


def test_export_includes_consent_flag(client, trial_headers):
    resp = client.get("/api/profile/export", headers=trial_headers)
    assert resp.status_code == 200
    assert "consent_store_history" in resp.json()


def test_account_deletion_revokes_access(client, trial_headers):
    resp = client.delete("/api/profile/account", headers=trial_headers)
    assert resp.status_code == 200

    # Check with the bearer token ALONE: with X-Device-Id still attached,
    # get_current_user legitimately starts a brand-new trial for that
    # device (that's correct trial-renewal behavior, not a bug). The
    # thing this test actually guards is that the deleted user's JWT
    # itself no longer resolves to the account that owned the data.
    token_only_headers = {"Authorization": trial_headers["Authorization"]}
    after = client.get("/api/profile", headers=token_only_headers)
    assert after.status_code == 401


def test_reference_herbs_endpoint_returns_dynamic_data(client):
    resp = client.get("/api/reference/herbs")
    assert resp.status_code == 200
    herbs = resp.json()
    assert isinstance(herbs, list)
    assert len(herbs) > 0
    assert "herb_id" in herbs[0]
