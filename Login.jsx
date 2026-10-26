import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import TopBar from "../components/TopBar";
import api from "../services/api";
import { useApp } from "../context/AppContext";

/**
 * Two-step OTP login, matching the handoff guide's specified auth flow
 * (email/phone + one-time code) instead of a password.
 */
export default function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setIsAuthed, refreshProfile } = useApp();

  const [step, setStep] = useState("identifier"); // "identifier" | "code"
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  async function requestCode(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api.requestOtp(identifier.trim());
      setInfo(res.message || "Code sent.");
      setStep("code");
    } catch (err) {
      setError(err?.response?.data?.error?.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyCode(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.verifyOtp(identifier.trim(), code.trim());
      setIsAuthed(true);
      await refreshProfile();
      navigate("/symptoms");
    } catch (err) {
      setError(err?.response?.data?.error?.message || "Incorrect or expired code.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <TopBar showBack />
      <div className="screen">
        <h1>{t("login")}</h1>

        {step === "identifier" && (
          <form onSubmit={requestCode} className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field">
              <label>{t("email")} / {t("phone")}</label>
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="you@example.com or +91XXXXXXXXXX"
                required
              />
            </div>
            {error && <div className="badge-danger">{error}</div>}
            <button className="btn btn-primary btn-block" disabled={busy} type="submit">
              {busy ? "…" : "Send code"}
            </button>
          </form>
        )}

        {step === "code" && (
          <form onSubmit={verifyCode} className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {info && <div className="badge-warning">{info}</div>}
            <div className="field">
              <label>Verification code</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="6-digit code"
                required
              />
            </div>
            {error && <div className="badge-danger">{error}</div>}
            <button className="btn btn-primary btn-block" disabled={busy} type="submit">
              {busy ? "…" : t("continue")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setStep("identifier")}>
              Use a different email/phone
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
