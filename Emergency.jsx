import React from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

export default function Emergency() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const result = location.state?.result;
  const number = result?.emergency_number || "112";

  return (
    <div className="app-shell emergency-screen">
      <div className="screen" style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }} role="alert" aria-live="assertive">
        <div style={{ fontSize: "3rem" }} aria-hidden="true">🚨</div>
        <h1 style={{ color: "var(--color-danger)" }}>{t("emergency_title")}</h1>
        <p>{t("emergency_subtitle")}</p>

        <a href={`tel:${number}`} className="btn btn-primary btn-block" style={{ background: "var(--color-danger)" }}>
          {t("call_emergency", { number })}
        </a>

        <button className="btn btn-outline btn-block" onClick={() => navigate("/nearby?kind=hospital")}>
          {t("find_hospital")}
        </button>

        <button className="btn btn-ghost" onClick={() => navigate("/symptoms")}>
          {t("back")}
        </button>
      </div>
    </div>
  );
}
