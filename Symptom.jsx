import React, { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import TopBar from "../components/TopBar";
import api from "../services/api";
import { useApp } from "../context/AppContext";

const SPEECH_LANG_MAP = { en: "en-IN", hi: "hi-IN", ta: "ta-IN", kn: "kn-IN", ml: "ml-IN", te: "te-IN", mr: "mr-IN" };

export default function Symptom() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { profile } = useApp();

  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceUnsupported, setVoiceUnsupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef(null);

  function startListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceUnsupported(true);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = SPEECH_LANG_MAP[i18n.language] || "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    recognition.onerror = (event) => {
      // "not-allowed" / "permission-denied" = the user (or browser policy)
      // blocked the mic — show the same manual-entry fallback as an
      // unsupported browser, since the recovery is identical either way.
      setVoiceUnsupported(true);
      setListening(false);
    };
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setListening(false);
  }

  async function search(e) {
    e?.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.matchSymptoms({ text: text.trim(), lang: i18n.language, source: listening ? "voice" : "text" });
      if (result.emergency) {
        navigate("/emergency", { state: { result } });
      } else {
        navigate("/results", { state: { result, query: text.trim() } });
      }
    } catch (err) {
      if (err?.response?.status === 402) {
        navigate("/login");
        return;
      }
      setError(err?.response?.data?.error?.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const greetName = profile?.name || "";

  return (
    <div className="app-shell">
      <TopBar />
      <div className="screen">
        <h1>{t("symptom_title", { name: greetName })}</h1>

        <button
          type="button"
          className={`mic-button ${listening ? "listening" : ""}`}
          onClick={listening ? stopListening : startListening}
          aria-label={t("listen")}
        >
          🎤
        </button>
        <p style={{ textAlign: "center" }} role="status" aria-live="polite">
          {listening ? t("listening") : t("listen")}
        </p>
        {voiceUnsupported && (
          <div className="badge-warning" role="alert">
            Voice input isn't available right now (unsupported browser or microphone permission was denied) —
            please type your symptoms below instead.
          </div>
        )}

        <form onSubmit={search} className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <textarea
            rows={4}
            placeholder={t("symptom_placeholder")}
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{
              border: "1.5px solid var(--color-border)", borderRadius: 10, padding: 12,
              fontSize: "1rem", fontFamily: "inherit", resize: "vertical",
            }}
          />
          {error && <div className="badge-danger">{error}</div>}
          <button className="btn btn-primary btn-block" disabled={busy || !text.trim()} type="submit">
            {busy ? "…" : t("search")}
          </button>
        </form>

        <p className="disclaimer-box">{t("disclaimer")}</p>
      </div>
    </div>
  );
}
