import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "./api";
import Sidebar from "./components/Sidebar.jsx";
import ErrorBoundary, { PageErrorFallback } from "./components/ErrorBoundary.jsx";
import { languageOptions, useI18n } from "./i18n.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import ProjectEditor from "./pages/ProjectEditor.jsx";
import SchedulePage from "./pages/SchedulePage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import StoryboardPage from "./pages/StoryboardPage.jsx";

const CURRENT_PROJECT_STORAGE_KEY = "paneloom-current-project-id";
const LEGACY_PROJECT_STORAGE_KEY = "storyboard-genie-current-project-id";
const PAGE_IDS = new Set(["dashboard", "projects", "storyboard", "schedule", "settings"]);

function pageFromHash() {
  const value = window.location.hash.replace(/^#/, "");
  return PAGE_IDS.has(value) ? value : "dashboard";
}

export default function App() {
  const { languageSelection, setLanguageSelection, t } = useI18n();
  const [activePage, setActivePage] = useState(pageFromHash);
  const [projects, setProjects] = useState([]);
  const [currentProjectId, setCurrentProjectId] = useState(
    () =>
      localStorage.getItem(CURRENT_PROJECT_STORAGE_KEY) ||
      localStorage.getItem(LEGACY_PROJECT_STORAGE_KEY) ||
      "",
  );
  const [projectError, setProjectError] = useState("");
  const [cloudAiAvailable, setCloudAiAvailable] = useState(() => navigator.onLine);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const lastInteractionRef = useRef(Date.now());

  function userFacingError(error) {
    const message = String(error?.message || error || "");
    if (
      message === "Failed to fetch" ||
      message.includes("NetworkError") ||
      message.includes("Load failed")
    ) {
      return t("backendConnectionFailed");
    }
    return message;
  }

  async function refreshProjects() {
    try {
      const response = await api.listProjects();
      const list = response.data || [];
      setProjects(list);
      setProjectError("");
      const projectExists = list.some((project) => project.project_id === currentProjectId);
      if ((!currentProjectId || !projectExists) && list.length > 0) {
        setCurrentProjectId(list[0].project_id);
      }
      if (currentProjectId && !projectExists && list.length === 0) {
        setCurrentProjectId("");
      }
    } catch (error) {
      setProjectError(userFacingError(error));
    }
  }

  useEffect(() => {
    let active = true;
    async function bootstrapDesktopState() {
      let preferredProjectId = currentProjectId;
      try {
        const preferenceResponse = await api.getUiPreferences();
        const preferences = preferenceResponse.data || {};
        preferredProjectId = preferences.current_project_id || preferredProjectId;
        if (preferences.language_selection) setLanguageSelection(preferences.language_selection);
      } catch {
        // Local storage remains a development-mode fallback.
      }
      try {
        const response = await api.listProjects();
        if (!active) return;
        const list = response.data || [];
        setProjects(list);
        setProjectError("");
        const preferredExists = list.some(
          (project) => project.project_id === preferredProjectId,
        );
        setCurrentProjectId(
          preferredExists ? preferredProjectId : list[0]?.project_id || "",
        );
      } catch (error) {
        if (active) setProjectError(userFacingError(error));
      } finally {
        if (active) setPreferencesLoaded(true);
      }
    }
    bootstrapDesktopState();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    async function refreshCloudStatus() {
      if (!navigator.onLine) {
        setCloudAiAvailable(false);
        return;
      }
      try {
        const health = await api.health();
        setCloudAiAvailable(health.cloud_ai_available !== false);
      } catch {
        setCloudAiAvailable(false);
      }
    }
    const handleOffline = () => setCloudAiAvailable(false);
    const handleOnline = () => refreshCloudStatus();
    refreshCloudStatus();
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  useEffect(() => {
    function handleHashChange() {
      setActivePage(pageFromHash());
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    if (currentProjectId) {
      localStorage.setItem(CURRENT_PROJECT_STORAGE_KEY, currentProjectId);
      localStorage.removeItem(LEGACY_PROJECT_STORAGE_KEY);
    } else {
      localStorage.removeItem(CURRENT_PROJECT_STORAGE_KEY);
      localStorage.removeItem(LEGACY_PROJECT_STORAGE_KEY);
    }
  }, [currentProjectId]);

  useEffect(() => {
    if (!preferencesLoaded) return;
    api.saveUiPreferences({
      current_project_id: currentProjectId,
      language_selection: languageSelection,
    }).catch(() => {});
  }, [currentProjectId, languageSelection, preferencesLoaded]);

  const currentProject = useMemo(
    () => projects.find((project) => project.project_id === currentProjectId) || null,
    [projects, currentProjectId],
  );

  useEffect(() => {
    if (!currentProjectId) return undefined;
    lastInteractionRef.current = Date.now();
    const markActive = () => {
      lastInteractionRef.current = Date.now();
    };
    window.addEventListener("pointerdown", markActive, true);
    window.addEventListener("keydown", markActive, true);
    const timer = window.setInterval(() => {
      const recentlyActive = Date.now() - lastInteractionRef.current < 120_000;
      if (document.visibilityState !== "visible" || !document.hasFocus() || !recentlyActive) return;
      api
        .recordProjectActivity(currentProjectId, { seconds: 30, page: activePage || "unknown" })
        .catch(() => {});
    }, 30_000);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("pointerdown", markActive, true);
      window.removeEventListener("keydown", markActive, true);
    };
  }, [currentProjectId, activePage]);

  const pageTitle = {
    dashboard: t("dashboard"),
    projects: t("projects"),
    storyboard: t("storyboard"),
    schedule: t("schedule"),
    settings: t("settings"),
  }[activePage];

  function navigate(page) {
    if (!PAGE_IDS.has(page)) return;
    setActivePage(page);
    if (window.location.hash !== `#${page}`) {
      window.history.pushState(null, "", `#${page}`);
    }
  }

  function openProjectAssets() {
    navigate("storyboard");
    window.setTimeout(() => {
      document.getElementById("project-assets")?.scrollIntoView({ behavior: "smooth" });
    }, 0);
  }

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} onNavigate={navigate} />
      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">{t("workspace")}</p>
            <h2>{pageTitle}</h2>
          </div>
          <div className="topbar-controls">
            <label className="project-picker">
              <span>{t("currentProject")}</span>
              <select
                value={currentProjectId}
                onChange={(event) => setCurrentProjectId(event.target.value)}
              >
                <option value="">{t("noProjectSelectedOption")}</option>
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="language-picker">
              <span>{t("language")}</span>
              <select
                value={languageSelection}
                onChange={(event) => setLanguageSelection(event.target.value)}
              >
                {languageOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {t(option.labelKey)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </header>

        {projectError && <div className="alert error">{projectError}</div>}
        {!cloudAiAvailable && <div className="alert">{t("offlineModeMessage")}</div>}

        <ErrorBoundary
          resetKey={`${activePage}:${currentProjectId}`}
          fallback={({ error, reset }) => (
            <PageErrorFallback
              error={error}
              onRetry={reset}
              onDashboard={() => navigate("dashboard")}
              t={t}
            />
          )}
        >
          <PageDiagnosticCrashProbe />
          {activePage === "dashboard" && (
            <Dashboard
              currentProject={currentProject}
              onOpenAssets={openProjectAssets}
            />
          )}
          {activePage === "projects" && (
            <ProjectEditor
              projects={projects}
              currentProjectId={currentProjectId}
              onSelectProject={setCurrentProjectId}
              onProjectsChanged={refreshProjects}
            />
          )}
          {activePage === "storyboard" && (
            <StoryboardPage currentProject={currentProject} cloudAiAvailable={cloudAiAvailable} />
          )}
          {activePage === "schedule" && <SchedulePage currentProject={currentProject} />}
          {activePage === "settings" && <SettingsPage />}
        </ErrorBoundary>
      </main>
    </div>
  );
}

function PageDiagnosticCrashProbe() {
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!window.__PANELOOM_RUNTIME_DIAGNOSTICS__) return undefined;
    window.__PANELOOM_TRIGGER_PAGE_ERROR__ = () => {
      setError(new Error("Controlled page render failure for desktop acceptance."));
    };
    return () => {
      delete window.__PANELOOM_TRIGGER_PAGE_ERROR__;
    };
  }, []);

  if (error) throw error;
  return null;
}
