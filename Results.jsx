import React from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import TopBar from "../components/TopBar";

const SPEECH_LANG_MAP = { en: "en-IN", hi: "hi-IN", ta: "ta-IN", kn: "kn-IN", ml: "ml-IN", te: "te-IN", mr: "mr-IN" };

function speak(text, lang) {
  if (!("speechSynthesis" in window) || !text) return;
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = SPEECH_LANG_MAP[lang] || "en-IN";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
}

export default function Results() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const result = location.state?.result;

  if (!result) {
    navigate("/symptoms", { replace: true });
    return null;
  }

  if (!result.matches || result.matches.length === 0) {
    return (
      <div className="app-shell">
        <TopBar showBack />
        <div className="screen">
          <h1>{t("results_title")}</h1>
          <div className="card">
            <p>{result.message || t("no_match")}</p>
          </div>
          <button className="btn btn-primary btn-block" onClick={() => navigate("/symptoms")}>{t("back")}</button>
          <p className="disclaimer-box">{result.disclaimer}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TopBar showBack />
      <div className="screen">
        <h1>{t("results_title")}</h1>

        {result.matches.map((m) => (
          <div key={m.condition_id} className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="pill">{m.category}</span>
              <span className="score-tag">#{m.condition_id}</span>
            </div>

            {m.hidden_for_safety > 0 && (
              <div className="badge-warning">
                {m.hidden_for_safety === 1 ? t("hidden_notice", { count: m.hidden_for_safety }) : t("hidden_notice_plural", { count: m.hidden_for_safety })}
              </div>
            )}

            {m.remedies.map((r) => (
              <div key={r.herb_id} className="remedy-card" style={{ borderTop: "1px solid var(--color-border)", paddingTop: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div className="remedy-herb-name">{r.herb_name}</div>
                    <div className="remedy-latin">{r.latin_name}</div>
                  </div>
                  <button
                    className="btn btn-ghost"
                    style={{ fontSize: "1.3rem", padding: 4 }}
                    aria-label={t("speak_remedy")}
                    onClick={() => speak(`${r.herb_name}. ${r.preparation}. ${r.see_doctor_if || ""}`, i18n.language)}
                  >
                    🔊
                  </button>
                </div>
                <p>{r.preparation}</p>
                {r.avoid_if && (
                  <div className="badge-warning">
                    <strong>{t("avoid_if")}</strong> {r.avoid_if}
                  </div>
                )}
                {r.see_doctor_if && (
                  <div className="badge-danger">
                    <strong>{t("see_doctor")}</strong> {r.see_doctor_if}
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}

        <button className="btn btn-outline btn-block" onClick={() => navigate("/nearby")}>
          {t("nearby_care")}
        </button>

        <p className="disclaimer-box">{result.disclaimer}</p>
      </div>
    </div>
  );
}
