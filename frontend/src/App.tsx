import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { getScenes, type SceneIndex } from "./api/client";
import { DisclaimerBanner } from "./components/DisclaimerBanner";
import { CreditsPage } from "./pages/CreditsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { WaterBodyPage } from "./pages/WaterBodyPage";

const FALLBACK = "Satellite-derived estimate for prioritisation only — requires laboratory verification";

export function App() {
  const [scenes, setScenes] = useState<SceneIndex | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getScenes()
      .then(setScenes)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "API unavailable"));
  }, []);

  return (
    <div className="app">
      <DisclaimerBanner text={scenes?.disclaimer || FALLBACK} />
      <header className="top">
        <strong>AquaWatch</strong>
        <nav>
          <NavLink to="/">Overview</NavLink>
          <NavLink to="/credits">Credits</NavLink>
        </nav>
      </header>
      {error ? <p className="error">{error}</p> : null}
      <Routes>
        <Route path="/" element={<OverviewPage scenes={scenes} />} />
        <Route path="/water/:id" element={<WaterBodyPage scenes={scenes} />} />
        <Route path="/credits" element={<CreditsPage scenes={scenes} />} />
      </Routes>
    </div>
  );
}
