import React from "react";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGUAGES } from "../i18n";
import { useApp } from "../context/AppContext";

export default function LanguageSwitcher({ compact = false }) {
  const { i18n, t } = useTranslation();
  const { changeLanguage } = useApp();

  if (compact) {
    return (
      <select
        aria-label={t("language")}
        value={i18n.language}
        onChange={(e) => changeLanguage(e.target.value)}
        style={{ borderRadius: 10, padding: "8px 10px", border: "1.5px solid var(--color-border)" }}
      >
        {SUPPORTED_LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>{l.label}</option>
        ))}
      </select>
    );
  }

  return (
    <div className="lang-grid">
      {SUPPORTED_LANGUAGES.map((l) => (
        <button
          key={l.code}
          type="button"
          className={`lang-chip ${i18n.language === l.code ? "active" : ""}`}
          onClick={() => changeLanguage(l.code)}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
