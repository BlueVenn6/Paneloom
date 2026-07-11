import React from "react";
import { createRoot } from "react-dom/client";

import "./runtimeDiagnostics.js";
import App from "./App.jsx";
import ErrorBoundary, { GlobalErrorFallback } from "./components/ErrorBoundary.jsx";
import { I18nProvider } from "./i18n.jsx";
import "./styles/global.css";

const rootElement = document.getElementById("root");
const root = createRoot(rootElement);
window.__PANELOOM_REACT_ROOT_MOUNTED__ = true;
root.render(
  <React.StrictMode>
    <ErrorBoundary
      resetKey="application"
      fallback={({ error, reset }) => <GlobalErrorFallback error={error} onRetry={reset} />}
    >
      <GlobalDiagnosticCrashProbe />
      <I18nProvider>
        <App />
      </I18nProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

function GlobalDiagnosticCrashProbe() {
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    if (!window.__PANELOOM_RUNTIME_DIAGNOSTICS__) return undefined;
    window.__PANELOOM_TRIGGER_GLOBAL_ERROR__ = () => {
      setError(new Error("Controlled global render failure for desktop acceptance."));
    };
    return () => {
      delete window.__PANELOOM_TRIGGER_GLOBAL_ERROR__;
    };
  }, []);

  if (error) throw error;
  return null;
}
