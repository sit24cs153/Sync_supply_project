import React from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import LanguageSwitcher from "./LanguageSwitcher";
import { useApp } from "../context/AppContext";

export default function TopBar({ showBack = false }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { toggleLargeText, largeText } = useApp();

  return (
    <div className="topbar">
      <div className="brand">
        {showBack ? (
          <button className="btn btn-ghost" style={{ padding: 4 }} onClick={() => navigate(-1)} aria-label={t("back")}>←</button>
        ) : (
          <span className="brand-mark">S</span>
        )}
        <span>{t("app_name")}</span>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button
          className="btn btn-ghost"
          style={{ padding: "6px 10px", fontSize: "0.85rem" }}
          onClick={toggleLargeText}
          aria-pressed={largeText}
          title={t("large_text")}
        >
          A{largeText ? "−" : "+"}
        </button>
        <LanguageSwitcher compact />
        <button className="btn btn-ghost" style={{ padding: "6px 8px" }} onClick={() => navigate("/settings")} aria-label="Privacy settings">
          ⚙️
        </button>
      </div>
    </div>
  );
}
