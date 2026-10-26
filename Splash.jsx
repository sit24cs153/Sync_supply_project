import React from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function Splash() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="screen" style={{ justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <div className="brand-mark" style={{ width: 72, height: 72, borderRadius: 20, fontSize: "2rem", marginBottom: 8 }}>S</div>
      <h1>{t("app_name")}</h1>
      <p>{t("tagline")}</p>

      <div style={{ width: "100%", marginTop: 18 }}>
        <LanguageSwitcher />
      </div>

      <div className="card" style={{ width: "100%", marginTop: 20 }}>
        <p style={{ marginBottom: 12 }}>{t("trial_banner")}</p>
        <button className="btn btn-primary btn-block" onClick={() => navigate("/onboarding/profile")}>
          {t("splash_cta")}
        </button>
      </div>

      <button className="btn btn-outline btn-block" onClick={() => navigate("/login")}>
        {t("login")}
      </button>

      <p className="disclaimer-box" style={{ marginTop: 20 }}>{t("disclaimer")}</p>
    </div>
  );
}
