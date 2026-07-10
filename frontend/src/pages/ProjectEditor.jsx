import { useEffect, useMemo, useState } from "react";
import { ArchiveRestore, DatabaseBackup, FolderOpen } from "lucide-react";

import { api } from "../api";
import { useI18n } from "../i18n.jsx";

export default function ProjectEditor({
  projects,
  currentProjectId,
  onSelectProject,
  onProjectsChanged,
}) {
  const { t } = useI18n();
  const [form, setForm] = useState({ name: "", description: "", parent_directory: "" });
  const [openPath, setOpenPath] = useState("");
  const [backupPath, setBackupPath] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [editForm, setEditForm] = useState({ name: "", description: "" });
  const selectedProject = useMemo(
    () => projects.find((project) => project.project_id === currentProjectId) || null,
    [projects, currentProjectId],
  );

  useEffect(() => {
    setEditForm({
      name: selectedProject?.name || "",
      description: selectedProject?.description || "",
    });
  }, [selectedProject?.project_id, selectedProject?.name, selectedProject?.description]);

  useEffect(() => {
    api
      .getProjectStorage()
      .then((response) => {
        const path = response.data?.default_projects_home || "";
        setForm((current) => ({ ...current, parent_directory: current.parent_directory || path }));
      })
      .catch(() => {});
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy("create");
    setMessage("");
    try {
      const response = await api.createProject(form);
      setForm((current) => ({ name: "", description: "", parent_directory: current.parent_directory }));
      await onProjectsChanged();
      onSelectProject(response.data.project_id);
      setMessage(t("projectCreated"));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy("");
    }
  }

  async function runProjectAction(label, action) {
    setBusy(label);
    setMessage("");
    try {
      const response = await action();
      await onProjectsChanged();
      setMessage(response.message || t("doneMessage"));
      return response;
    } catch (error) {
      setMessage(error.message);
      return null;
    } finally {
      setBusy("");
    }
  }

  async function handleUpdateProject(event) {
    event.preventDefault();
    if (!selectedProject) return;
    await runProjectAction("update", () =>
      api.updateProject(selectedProject.project_id, editForm),
    );
  }

  async function handleDuplicateProject() {
    if (!selectedProject) return;
    const response = await runProjectAction("duplicate", () =>
      api.duplicateProject(selectedProject.project_id),
    );
    if (response?.data?.project_id) onSelectProject(response.data.project_id);
  }

  async function handleToggleArchive() {
    if (!selectedProject) return;
    await runProjectAction("archive", () =>
      api.updateProject(selectedProject.project_id, { archived: !selectedProject.archived }),
    );
  }

  async function handleDeleteProject() {
    if (!selectedProject) return;
    const confirmed = window.confirm(`${t("deleteProjectConfirm")} ${selectedProject.name}`);
    if (!confirmed) return;
    const deletedId = selectedProject.project_id;
    const response = await runProjectAction("delete", () => api.deleteProject(deletedId));
    if (response?.ok) onSelectProject("");
  }

  async function chooseFolder(target) {
    const response = await runProjectAction("choose-folder", () => api.chooseProjectFolder());
    const path = response?.data?.path || "";
    if (!path) return;
    if (target === "open") setOpenPath(path);
    else setForm((current) => ({ ...current, parent_directory: path }));
  }

  async function handleOpenProject() {
    if (!openPath.trim()) return;
    const response = await runProjectAction("open", () => api.openProject(openPath.trim()));
    if (response?.data?.project_id) onSelectProject(response.data.project_id);
  }

  async function chooseBackup() {
    const response = await runProjectAction("choose-backup", () => api.chooseBackupFile());
    if (response?.data?.path) setBackupPath(response.data.path);
  }

  async function handleRestoreProject() {
    if (!backupPath.trim()) return;
    const response = await runProjectAction("restore", () =>
      api.restoreProject({ backup_path: backupPath.trim(), destination_parent: form.parent_directory }),
    );
    if (response?.data?.project_id) onSelectProject(response.data.project_id);
  }

  async function handleBackupProject() {
    if (!selectedProject) return;
    const response = await runProjectAction("backup", () =>
      api.backupProject(selectedProject.project_id),
    );
    if (response?.data?.backup_path) {
      setMessage(`${response.message} · ${response.data.backup_path}`);
    }
  }

  async function handleMigrateProject() {
    if (!selectedProject) return;
    const response = await runProjectAction("migrate", () =>
      api.migrateProject(selectedProject.project_id, form.parent_directory),
    );
    if (response?.data?.project_id) onSelectProject(response.data.project_id);
  }

  return (
    <section className="content-grid two-col">
      <form className="panel form-panel" onSubmit={handleSubmit}>
        <div className="section-heading">
          <p className="eyebrow">{t("newProject")}</p>
          <h3>{t("createProjectFolder")}</h3>
        </div>

        <label>
          <span>{t("projectName")}</span>
          <input
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            placeholder={t("projectNamePlaceholder")}
          />
        </label>

        <label>
          <span>{t("projectLocation")}</span>
          <div className="input-action-row">
            <input
              required
              value={form.parent_directory}
              onChange={(event) => setForm({ ...form, parent_directory: event.target.value })}
            />
            <button
              className="icon-button"
              onClick={() => chooseFolder("create")}
              title={t("chooseFolder")}
              type="button"
            >
              <FolderOpen aria-hidden="true" size={17} />
            </button>
          </div>
        </label>

        <label>
          <span>{t("projectDescription")}</span>
          <textarea
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            placeholder={t("projectDescriptionPlaceholder")}
            rows={4}
          />
        </label>

        <button className="primary" disabled={busy === "create"} type="submit">
          {busy === "create" ? t("creating") : t("createProject")}
        </button>
        {message && <p className="form-message">{message}</p>}
      </form>

      <div className="panel form-panel">
        <div className="section-heading">
          <p className="eyebrow">{t("portableProjects")}</p>
          <h3>{t("openOrRestoreProject")}</h3>
        </div>
        <label>
          <span>{t("existingProjectFolder")}</span>
          <div className="input-action-row">
            <input value={openPath} onChange={(event) => setOpenPath(event.target.value)} />
            <button className="icon-button" onClick={() => chooseFolder("open")} title={t("chooseFolder")} type="button">
              <FolderOpen aria-hidden="true" size={17} />
            </button>
          </div>
        </label>
        <button className="secondary" disabled={!openPath.trim() || busy === "open"} onClick={handleOpenProject} type="button">
          {t("openProject")}
        </button>
        <label>
          <span>{t("projectBackupFile")}</span>
          <div className="input-action-row">
            <input value={backupPath} onChange={(event) => setBackupPath(event.target.value)} />
            <button className="icon-button" onClick={chooseBackup} title={t("chooseBackup")} type="button">
              <ArchiveRestore aria-hidden="true" size={17} />
            </button>
          </div>
        </label>
        <button className="secondary" disabled={!backupPath.trim() || busy === "restore"} onClick={handleRestoreProject} type="button">
          {t("restoreProject")}
        </button>
      </div>

      <div className="panel">
        <div className="section-heading">
          <p className="eyebrow">{t("projects")}</p>
          <h3>{t("projectList")}</h3>
        </div>
        <div className="project-list">
          {projects.length === 0 && <p className="muted">{t("noProjectsYet")}</p>}
          {projects.map((project) => (
            <button
              className={`project-row ${
                currentProjectId === project.project_id ? "selected" : ""
              }`}
              key={project.project_id}
              onClick={() => onSelectProject(project.project_id)}
              type="button"
            >
              <span>
                <strong>
                  {project.name} {project.archived ? `· ${t("archived")}` : ""}
                </strong>
                <small>{project.project_id}</small>
                {project.migration_required && <small>{t("migrationRequired")}</small>}
              </span>
              <small>{project.description || t("noDescription")}</small>
            </button>
          ))}
        </div>
      </div>

      {selectedProject && (
        <form className="panel form-panel wide" onSubmit={handleUpdateProject}>
          <div className="section-heading">
            <p className="eyebrow">{t("projectManagement")}</p>
            <h3>{selectedProject.name}</h3>
          </div>
          <div className="form-row">
            <label>
              <span>{t("projectName")}</span>
              <input
                required
                value={editForm.name}
                onChange={(event) => setEditForm({ ...editForm, name: event.target.value })}
              />
            </label>
            <label>
              <span>{t("projectDescription")}</span>
              <input
                value={editForm.description}
                onChange={(event) =>
                  setEditForm({ ...editForm, description: event.target.value })
                }
              />
            </label>
          </div>
          <div className="button-row">
            <button className="primary" disabled={busy === "update"} type="submit">
              {t("saveChanges")}
            </button>
            <button
              className="secondary"
              disabled={busy === "duplicate"}
              onClick={handleDuplicateProject}
              type="button"
            >
              {t("duplicateProject")}
            </button>
            <button
              className="secondary"
              disabled={busy === "backup" || selectedProject.migration_required}
              onClick={handleBackupProject}
              type="button"
            >
              <DatabaseBackup aria-hidden="true" size={16} />
              {t("backupProject")}
            </button>
            {selectedProject.migration_required && (
              <button className="primary" disabled={busy === "migrate"} onClick={handleMigrateProject} type="button">
                {t("migrateProject")}
              </button>
            )}
            <button
              className="secondary"
              disabled={busy === "archive"}
              onClick={handleToggleArchive}
              type="button"
            >
              {selectedProject.archived ? t("unarchiveProject") : t("archiveProject")}
            </button>
            <button
              className="secondary danger"
              disabled={busy === "delete"}
              onClick={handleDeleteProject}
              type="button"
            >
              {t("deleteProject")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
