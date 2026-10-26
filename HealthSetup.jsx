import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import TopBar from "../components/TopBar";
import api from "../services/api";
import { useApp } from "../context/AppContext";

export default function HealthSetup() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { setHealth, profile } = useApp();

  const [herbs, setHerbs] = useState([]);
  const [allergies, setAllergies] = useState([]);
  const [isPregnant, setIsPregnant] = useState(false);
  const [onBloodThinners, setOnBloodThinners] = useState(false);
  const [onThyroid, setOnThyroid] = useState(false);
  const [hasDiabetes, setHasDiabetes] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listHerbs().then(setHerbs).catch(() => setHerbs([]));
  }, []);

  function toggleAllergy(herbId) {
    setAllergies((prev) => (prev.includes(herbId) ? prev.filter((h) => h !== herbId) : [...prev, herbId]));
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const saved = await api.saveHealth({
        allergies,
        is_pregnant: isPregnant,
        on_blood_thinners: onBloodThinners,
        on_thyroid_medication: onThyroid,
        has_diabetes: hasDiabetes,
        existing_conditions: [],
        age_years: profile?.age ?? null,
      });
      setHealth(saved);
      navigate("/symptoms");
    } finally {
      setBusy(false);
    }
  }

  const nameKey = `name_${i18n.language}`;

  return (
    <div className="app-shell">
      <TopBar showBack />
      <div className="screen">
        <h1>{t("health_title")}</h1>
        <p>{t("health_subtitle")}</p>

        <form onSubmit={submit} className="card" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <label style={{ fontWeight: 600, fontSize: "0.9rem" }}>{t("allergies")}</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {herbs.map((h) => (
              <button
                type="button"
                key={h.herb_id}
                onClick={() => toggleAllergy(h.herb_id)}
                className={`lang-chip ${allergies.includes(h.herb_id) ? "active" : ""}`}
                style={{ padding: "8px 12px", fontSize: "0.85rem" }}
              >
                {h[nameKey] || h.name_en}
              </button>
            ))}
          </div>

          <div className="checkbox-row">
            <input id="preg" type="checkbox" checked={isPregnant} onChange={(e) => setIsPregnant(e.target.checked)} />
            <label htmlFor="preg">{t("pregnant")}</label>
          </div>
          <div className="checkbox-row">
            <input id="bt" type="checkbox" checked={onBloodThinners} onChange={(e) => setOnBloodThinners(e.target.checked)} />
            <label htmlFor="bt">{t("blood_thinners")}</label>
          </div>
          <div className="checkbox-row">
            <input id="thy" type="checkbox" checked={onThyroid} onChange={(e) => setOnThyroid(e.target.checked)} />
            <label htmlFor="thy">{t("thyroid")}</label>
          </div>
          <div className="checkbox-row">
            <input id="dia" type="checkbox" checked={hasDiabetes} onChange={(e) => setHasDiabetes(e.target.checked)} />
            <label htmlFor="dia">{t("diabetes")}</label>
          </div>

          <button className="btn btn-primary btn-block" disabled={busy} type="submit" style={{ marginTop: 8 }}>
            {busy ? "…" : t("save_continue")}
          </button>
        </form>
      </div>
    </div>
  );
}
