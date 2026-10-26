import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import TopBar from "../components/TopBar";
import api from "../services/api";
import { useApp } from "../context/AppContext";

export default function ProfileSetup() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { setProfile } = useApp();

  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [dob, setDob] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = {
        name,
        age: age ? Number(age) : null,
        weight_kg: weight ? Number(weight) : null,
        date_of_birth: dob ? new Date(dob).toISOString() : null,
        preferred_language: i18n.language,
        large_text_mode: document.body.classList.contains("large-text"),
      };
      const saved = await api.saveProfile(payload);
      setProfile(saved);
      navigate("/onboarding/health");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <TopBar showBack />
      <div className="screen">
        <h1>{t("profile_title")}</h1>
        <form onSubmit={submit} className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="field">
            <label>{t("name")}</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label>{t("age")}</label>
            <input type="number" min="0" max="120" value={age} onChange={(e) => setAge(e.target.value)} />
          </div>
          <div className="field">
            <label>{t("weight")}</label>
            <input type="number" min="0" max="400" value={weight} onChange={(e) => setWeight(e.target.value)} />
          </div>
          <div className="field">
            <label>{t("dob")}</label>
            <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
          </div>
          <button className="btn btn-primary btn-block" disabled={busy} type="submit">
            {busy ? "…" : t("save_continue")}
          </button>
        </form>
      </div>
    </div>
  );
}
