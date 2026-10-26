import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import TopBar from "../components/TopBar";
import api from "../services/api";

export default function Nearby() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const kind = params.get("kind") || "ayurvedic";

  const [places, setPlaces] = useState([]);
  const [message, setMessage] = useState("");
  const [town, setTown] = useState("");
  const [busy, setBusy] = useState(false);
  const [askedLocation, setAskedLocation] = useState(false);

  async function fetchByCoords(latitude, longitude) {
    setBusy(true);
    try {
      const data = await api.nearby({ latitude, longitude, lang: i18n.language, kind });
      setPlaces(data.places || []);
      setMessage(data.message || "");
    } finally {
      setBusy(false);
    }
  }

  async function fetchByTown(e) {
    e?.preventDefault();
    if (!town.trim()) return;
    setBusy(true);
    try {
      const data = await api.nearby({ place_text: town.trim(), lang: i18n.language, kind });
      setPlaces(data.places || []);
      setMessage(data.message || "");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (askedLocation) return;
    setAskedLocation(true);
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => fetchByCoords(pos.coords.latitude, pos.coords.longitude),
      () => {
        /* permission refused or unavailable — user can type a town below */
      },
      { timeout: 8000 }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="app-shell">
      <TopBar showBack />
      <div className="screen">
        <h1>{t("nearby_care")}</h1>

        <form onSubmit={fetchByTown} className="card" style={{ display: "flex", gap: 10 }}>
          <input
            placeholder="Town or pin code"
            value={town}
            onChange={(e) => setTown(e.target.value)}
            style={{ flex: 1, border: "1.5px solid var(--color-border)", borderRadius: 10, padding: 12 }}
          />
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "…" : "Go"}
          </button>
        </form>

        {busy && <div className="loader" />}

        {!busy && message && (
          <div className="badge-warning">{message}</div>
        )}

        {!busy && places.map((p, idx) => (
          <div key={idx} className="card place-card">
            <strong>{p.name}</strong>
            {p.address && <span style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>{p.address}</span>}
            {p.open_now !== null && p.open_now !== undefined && (
              <span className="pill" style={{ alignSelf: "flex-start" }}>
                {p.open_now ? t("open_now") : "—"}
              </span>
            )}
            <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
              <a className="btn btn-outline" href={p.maps_url} target="_blank" rel="noreferrer">
                {t("directions")}
              </a>
              {p.phone && (
                <a className="btn btn-outline" href={`tel:${p.phone}`}>Call</a>
              )}
            </div>
          </div>
        ))}

        <button className="btn btn-ghost" onClick={() => navigate(-1)}>{t("back")}</button>
      </div>
    </div>
  );
}
