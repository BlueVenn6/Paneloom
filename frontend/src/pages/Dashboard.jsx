import { useEffect, useState } from "react";

import { api, API_BASE } from "../api";
import { useI18n } from "../i18n.jsx";

export default function Dashboard({ currentProject, onOpenAssets }) {
  const { t } = useI18n();
  const [health, setHealth] = useState({ status: "checking", messageKey: "backendChecking" });

  useEffect(() => {
    api
      .health()
      .then((data) =>
        setHealth({
          status: data.ok ? "online" : "offline",
          messageKey: data.ok ? "backendOnline" : "backendUnhealthy",
        }),
      )
      .catch((error) => setHealth({ status: "offline", message: error.message }));
  }, []);

  return (
    <section className="content-grid">
      <div className="panel wide">
        <div className="section-heading">
          <p className="eyebrow">{t("workflow")}</p>
          <h3>{t("dashboardIntroTitle")}</h3>
        </div>
        <p className="muted">{t("dashboardIntroBody")}</p>
      </div>

      <div className="panel">
        <h3>{t("apiEndpoint")}</h3>
        <div className={`status-pill ${health.status}`}>{statusLabel(health.status, t)}</div>
        <p className="muted">{health.messageKey ? t(health.messageKey) : health.message}</p>
        <code>{API_BASE}</code>
      </div>

      <div className="panel">
        <h3>{t("currentProjectTitle")}</h3>
        {currentProject ? (
          <>
            <p className="strong">{currentProject.name}</p>
            <p className="muted">{currentProject.description || t("noDescription")}</p>
            <code>{currentProject.project_id}</code>
          </>
        ) : (
          <div className="empty-state align-left">
            <strong>{t("firstRunTitle")}</strong>
            <span>{t("firstRunBody")}</span>
            <ol className="guide-list">
              <li>{t("firstRunStepCreateProject")}</li>
              <li>{t("firstRunStepImportScript")}</li>
              <li>{t("firstRunStepAddAssets")}</li>
              <li>{t("firstRunStepExtractStyle")}</li>
              <li>{t("firstRunStepGeneratePanels")}</li>
            </ol>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>{t("projectAssets")}</h3>
        <p className="muted">{t("projectAssetsHint")}</p>
        <button
          className="primary"
          disabled={!currentProject}
          onClick={onOpenAssets}
          type="button"
        >
          {t("openProjectAssets")}
        </button>
      </div>
    </section>
  );
}

function statusLabel(status, t) {
  const labelMap = {
    checking: "healthChecking",
    online: "healthOnline",
    offline: "healthOffline",
  };
  return t(labelMap[status] || "healthOffline");
}
