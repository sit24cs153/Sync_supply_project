import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import TopBar from "../components/TopBar";
import api from "../services/api";
import { useApp } from "../context/AppContext";

export default function Settings() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { logout } = useApp();

  const [consent, setConsentState] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getConsent().then((c) => setConsentState(c.consent_store_history)).finally(() => setLoading(false));
  }, []);

  async function toggleConsent() {
    setBusy(true);
    try {
      const next = !consent;
      await api.setConsent(next);
      setConsentState(next);
    } finally {
      setBusy(false);
    }
  }

  async function clearHistory() {
    setBusy(true);
    try {
      await api.deleteHistory();
      setMessage("Your symptom history has been deleted.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadExport() {
    setBusy(true);
    try {
      const data = await api.exportMyData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "syncsupply-my-data.json";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setBusy(false);
    }
  }

  async function deleteAccount() {
    if (!window.confirm("This permanently deletes your account and all data. This cannot be undone. Continue?")) return;
    setBusy(true);
    try {
      await api.deleteAccount();
      logout();
      navigate("/", { replace: true });
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="app-shell">
        <TopBar showBack />
        <div className="screen" style={{ alignItems: "center" }}><div className="loader" /></div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TopBar showBack />
      <div className="screen">
        <h1>Privacy & data</h1>

        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="checkbox-row">
            <input id="consent" type="checkbox" checked={consent} onChange={toggleConsent} disabled={busy} />
            <label htmlFor="consent">Save my symptom searches so I can view them later</label>
          </div>
          <p style={{ fontSize: "0.82rem" }}>
            Off by default. Matching still works either way — this only controls whether your past
            searches are kept for the "{t("history")}" screen.
          </p>
        </div>

        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <button className="btn btn-outline btn-block" onClick={clearHistory} disabled={busy}>
            Delete my search history
          </button>
          <button className="btn btn-outline btn-block" onClick={downloadExport} disabled={busy}>
            Download my data
          </button>
        </div>

        {message && <div className="badge-warning">{message}</div>}

        <div className="card" style={{ borderColor: "var(--color-danger)" }}>
          <button className="btn btn-block" style={{ background: "var(--color-danger)", color: "white" }} onClick={deleteAccount} disabled={busy}>
            Delete my account
          </button>
        </div>

        <button className="btn btn-ghost btn-block" onClick={() => { logout(); navigate("/"); }}>
          {t("logout")}
        </button>
      </div>
    </div>
  );
}
