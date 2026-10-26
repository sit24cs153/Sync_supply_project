import React, { useEffect } from "react";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useApp } from "./context/AppContext";

import Splash from "./pages/Splash";
import Login from "./pages/Login";
import ProfileSetup from "./pages/ProfileSetup";
import HealthSetup from "./pages/HealthSetup";
import Symptom from "./pages/Symptom";
import Results from "./pages/Results";
import Emergency from "./pages/Emergency";
import Nearby from "./pages/Nearby";
import Settings from "./pages/Settings";

function RequireAuth({ children }) {
  const { isAuthed, loading, trialActive } = useApp();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && isAuthed && !trialActive) {
      navigate("/login", { replace: true, state: { from: location } });
    }
  }, [loading, isAuthed, trialActive, navigate, location]);

  if (loading) {
    return (
      <div className="app-shell">
        <div className="screen" style={{ justifyContent: "center", alignItems: "center" }}>
          <div className="loader" />
        </div>
      </div>
    );
  }

  if (!isAuthed) return <Navigate to="/" replace />;

  return children;
}

export default function App() {
  const { largeText } = useApp();

  useEffect(() => {
    document.body.classList.toggle("large-text", largeText);
  }, [largeText]);

  return (
    <Routes>
      <Route path="/" element={<Splash />} />
      <Route path="/login" element={<Login />} />

      <Route path="/onboarding/profile" element={<RequireAuth><ProfileSetup /></RequireAuth>} />
      <Route path="/onboarding/health" element={<RequireAuth><HealthSetup /></RequireAuth>} />

      <Route path="/symptoms" element={<RequireAuth><Symptom /></RequireAuth>} />
      <Route path="/results" element={<RequireAuth><Results /></RequireAuth>} />
      <Route path="/emergency" element={<RequireAuth><Emergency /></RequireAuth>} />
      <Route path="/nearby" element={<RequireAuth><Nearby /></RequireAuth>} />
      <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
