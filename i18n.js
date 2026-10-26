import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import hi from "./locales/hi.json";
import ta from "./locales/ta.json";
import kn from "./locales/kn.json";
import ml from "./locales/ml.json";
import te from "./locales/te.json";
import mr from "./locales/mr.json";

export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "ta", label: "தமிழ்" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "ml", label: "മലയാളം" },
  { code: "te", label: "తెలుగు" },
  { code: "mr", label: "मराठी" },
];

const stored = typeof window !== "undefined" ? localStorage.getItem("syncsupply_lang") : null;

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    ta: { translation: ta },
    kn: { translation: kn },
    ml: { translation: ml },
    te: { translation: te },
    mr: { translation: mr },
  },
  lng: stored || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
