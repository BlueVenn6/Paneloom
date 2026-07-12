export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : window.location.origin);

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
    ...options,
  });

  const body = await response.json().catch(() => ({
    ok: false,
    message: "Invalid JSON response from backend.",
  }));

  if (!response.ok) {
    throw new Error(body.detail || body.message || `Request failed: ${response.status}`);
  }
  return body;
}

export function assetUrl(path, version = "") {
  if (!path) return "";
  const url = path.startsWith("http://") || path.startsWith("https://") ? path : `${API_BASE}${path}`;
  if (!version) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}v=${encodeURIComponent(version)}`;
}

export const api = {
  health: () => fetch(`${API_BASE}/health`).then((response) => response.json()),
  listProjects: () => request("/projects"),
  getProjectStorage: () => request("/projects/storage"),
  chooseProjectFolder: () => request("/projects/choose-folder", { method: "POST" }),
  chooseBackupFile: () => request("/projects/choose-backup", { method: "POST" }),
  openProject: (path) =>
    request("/projects/open", { method: "POST", body: JSON.stringify({ path }) }),
  restoreProject: (payload) =>
    request("/projects/restore", { method: "POST", body: JSON.stringify(payload) }),
  createProject: (payload) =>
    request("/projects", { method: "POST", body: JSON.stringify(payload) }),
  updateProject: (projectId, payload) =>
    request(`/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  duplicateProject: (projectId) =>
    request(`/projects/${projectId}/duplicate`, { method: "POST" }),
  migrateProject: (projectId, destinationParent = "") =>
    request(`/projects/${projectId}/migrate`, {
      method: "POST",
      body: JSON.stringify({ destination_parent: destinationParent }),
    }),
  backupProject: (projectId, payload = {}) =>
    request(`/projects/${projectId}/backup`, {
      method: "POST",
      body: JSON.stringify({ include_exports: true, ...payload }),
    }),
  deleteProject: (projectId) =>
    request(`/projects/${projectId}`, { method: "DELETE" }),
  getProjectWorkspace: (projectId) => request(`/projects/${projectId}/workspace`),
  saveProjectWorkspace: (projectId, payload) =>
    request(`/projects/${projectId}/workspace`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  getProjectBible: (projectId) => request(`/projects/${projectId}/bible`),
  saveProjectBible: (projectId, payload) =>
    request(`/projects/${projectId}/bible`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  analyzeProjectBible: (projectId, payload) =>
    request(`/projects/${projectId}/bible/analyze`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listShots: (projectId) => request(`/projects/${projectId}/shots`),
  createShot: (projectId, payload) =>
    request(`/projects/${projectId}/shots`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createShotsFromScript: (projectId, payload) =>
    request(`/projects/${projectId}/shots/from-script`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rewriteStoryboard: (projectId, payload) =>
    request(`/projects/${projectId}/shots/rewrite-storyboard`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  optimizeStory: (projectId, payload) =>
    request(`/projects/${projectId}/shots/optimize-story`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateShot: (projectId, shotId, payload) =>
    request(`/projects/${projectId}/shots/${shotId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteShot: (projectId, shotId) =>
    request(`/projects/${projectId}/shots/${shotId}`, { method: "DELETE" }),
  reorderShots: (projectId, shotIds) =>
    request(`/projects/${projectId}/shots/reorder`, {
      method: "POST",
      body: JSON.stringify({ shot_ids: shotIds }),
    }),
  mergeShotWithNext: (projectId, shotId, nextShotId) =>
    request(`/projects/${projectId}/shots/${shotId}/merge-next`, {
      method: "POST",
      body: JSON.stringify({ next_shot_id: nextShotId }),
    }),
  mergeAdjacentShotPairs: (projectId, shotIds) =>
    request(`/projects/${projectId}/shots/merge-pairs`, {
      method: "POST",
      body: JSON.stringify({ shot_ids: shotIds }),
    }),
  selectShotVersion: (projectId, shotId, versionId) =>
    request(
      `/projects/${projectId}/shots/${shotId}/versions/${encodeURIComponent(versionId)}/select`,
      { method: "POST" },
    ),
  startGenerationJob: (projectId, shotId, payload) =>
    request(`/projects/${projectId}/generate/${shotId}/job`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getGenerationJob: (projectId, jobId) =>
    request(`/projects/${projectId}/generate/jobs/${jobId}`),
  getAspectPresets: (projectId) => request(`/projects/${projectId}/generate/aspect-presets`),
  listReferences: (projectId) => request(`/projects/${projectId}/generate/references`),
  uploadReference: (projectId, file) => {
    const body = new FormData();
    body.append("file", file);
    return request(`/projects/${projectId}/generate/references`, {
      method: "POST",
      body,
    });
  },
  deleteReference: (projectId, filename) =>
    request(`/projects/${projectId}/generate/references/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    }),
  startReferenceConceptJob: (projectId, payload) =>
    request(`/projects/${projectId}/generate/references/concepts/job`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  planReferenceAssets: (projectId, payload) =>
    request(`/projects/${projectId}/generate/references/plan`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getReferenceConceptJob: (projectId, jobId) =>
    request(`/projects/${projectId}/generate/references/jobs/${jobId}`),
  analyzeReferenceStyle: (projectId, payload) =>
    request(`/projects/${projectId}/generate/references/style-analysis`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  setShotVisualAnchor: (projectId, shotId, payload = {}) =>
    request(`/projects/${projectId}/generate/${shotId}/visual-anchor`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  importDocument: (file) => {
    const body = new FormData();
    body.append("file", file);
    return request("/imports/document", {
      method: "POST",
      body,
    });
  },
  exportProject: (projectId, format) =>
    request(`/projects/${projectId}/exports`, {
      method: "POST",
      body: JSON.stringify({ format }),
    }),
  getSchedule: (projectId) => request(`/projects/${projectId}/schedule`),
  generateSchedule: (projectId, payload) =>
    request(`/projects/${projectId}/schedule/plan`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateScheduleTask: (projectId, taskId, payload) =>
    request(`/projects/${projectId}/schedule/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  addTimeLog: (projectId, payload) =>
    request(`/projects/${projectId}/schedule/time-logs`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recordProjectActivity: (projectId, payload) =>
    request(`/projects/${projectId}/schedule/activity`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  addSocialFeedback: (projectId, payload) =>
    request(`/projects/${projectId}/schedule/feedback`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  extractSocialFeedbackScreenshot: (projectId, file, payload = {}) => {
    const body = new FormData();
    body.append("file", file);
    body.append("platform", payload.platform || "");
    body.append("publish_date", payload.publish_date || "");
    body.append("content_id", payload.content_id || "");
    body.append("use_ai", String(payload.use_ai ?? true));
    return request(`/projects/${projectId}/schedule/feedback/extract-screenshot`, {
      method: "POST",
      body,
    });
  },
  generateReview: (projectId, payload) =>
    request(`/projects/${projectId}/schedule/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSettings: () => request("/settings"),
  getUiPreferences: () => request("/settings/ui-preferences"),
  saveUiPreferences: (payload) =>
    request("/settings/ui-preferences", { method: "POST", body: JSON.stringify(payload) }),
  saveSettings: (payload) =>
    request("/settings", { method: "POST", body: JSON.stringify(payload) }),
  testTextSettings: (payload, signal) =>
    request("/settings/test/text", { method: "POST", body: JSON.stringify(payload), signal }),
  testImageSettings: (payload, signal) =>
    request("/settings/test/image", { method: "POST", body: JSON.stringify(payload), signal }),
  saveDesktopExport: (projectId, blob, suggestedFilename) => {
    const body = new FormData();
    body.append("file", blob, suggestedFilename);
    body.append("suggested_filename", suggestedFilename);
    return request(`/projects/${projectId}/desktop-save`, { method: "POST", body });
  },
};
