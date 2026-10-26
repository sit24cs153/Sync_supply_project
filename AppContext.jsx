import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import api from "../services/api";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const { i18n } = useTranslation();
  const [isAuthed, setIsAuthed] = useState(!!localStorage.getItem("syncsupply_token"));
  const [trialActive, setTrialActive] = useState(true);
  const [trialExpiresAt, setTrialExpiresAt] = useState(null);
  const [profile, setProfile] = useState(null);
  const [health, setHealth] = useState(null);
  const [largeText, setLargeText] = useState(localStorage.getItem("syncsupply_large_text") === "1");
  const [loading, setLoading] = useState(true);

  const changeLanguage = useCallback((code) => {
    i18n.changeLanguage(code);
    localStorage.setItem("syncsupply_lang", code);
    if (typeof document !== "undefined") {
      document.documentElement.lang = code; // screen readers need this to switch pronunciation rules
    }
  }, [i18n]);

  const toggleLargeText = useCallback(() => {
    setLargeText((prev) => {
      const next = !prev;
      localStorage.setItem("syncsupply_large_text", next ? "1" : "0");
      return next;
    });
  }, []);

  const refreshProfile = useCallback(async () => {
    try {
      const p = await api.getProfile();
      setProfile(p);
      if (p.preferred_language) changeLanguage(p.preferred_language);
      if (typeof p.large_text_mode === "boolean") setLargeText(p.large_text_mode);
    } catch (e) {
      // not fatal — profile may not exist yet
    }
    try {
      const h = await api.getHealth();
      setHealth(h);
    } catch (e) {
      /* ignore */
    }
  }, [changeLanguage]);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    try {
      if (!localStorage.getItem("syncsupply_token")) {
        const trial = await api.startTrial();
        setTrialActive(trial.trial_active);
        setTrialExpiresAt(trial.trial_expires_at);
        setIsAuthed(true);
      } else {
        setIsAuthed(true);
      }
      await refreshProfile();
    } finally {
      setLoading(false);
    }
  }, [refreshProfile]);

  useEffect(() => {
    bootstrap();
    if (typeof document !== "undefined") {
      document.documentElement.lang = i18n.language;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setIsAuthed(false);
    setProfile(null);
    setHealth(null);
  }, []);

  const value = {
    isAuthed, setIsAuthed,
    trialActive, trialExpiresAt,
    profile, setProfile, refreshProfile,
    health, setHealth,
    largeText, toggleLargeText,
    changeLanguage,
    loading,
    logout,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
