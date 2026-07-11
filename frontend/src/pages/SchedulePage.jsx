import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { useI18n } from "../i18n.jsx";

const today = new Date().toISOString().slice(0, 10);
const defaultTargetDate = addDays(today, 14);

const defaultPlan = {
  start_date: today,
  target_publish_date: defaultTargetDate,
  update_frequency_per_week: 3,
  daily_available_hours: 2,
  platforms: "Reels, Shorts, Pinterest",
  total_content_items: 4,
  panels_per_content: 8,
  workflow_steps: ["script", "storyboard", "image", "edit", "copy", "publish"],
};

const defaultTimeLog = {
  task_id: "",
  date: today,
  minutes: 60,
  stage: "image",
  flow_state: "normal",
  blocker: "",
  notes: "",
};

const defaultFeedback = {
  content_id: "",
  platform: "Reels",
  publish_date: today,
  title: "",
  aspect_ratio: "9:16",
  format: "comic grid",
  views: 0,
  likes: 0,
  comments: 0,
  saves: 0,
  shares: 0,
  completion_rate: 0,
  snapshot_date: today,
  conversions: 0,
  revenue: 0,
  currency: "USD",
  judgment: "unknown",
  notes: "",
};

const workflowStageOptions = [
  { value: "script", labelKey: "taskStageScript" },
  { value: "storyboard", labelKey: "taskStageStoryboard" },
  { value: "image", labelKey: "taskStageImage" },
  { value: "generation", labelKey: "taskStageGeneration" },
  { value: "export", labelKey: "taskStageExport" },
  { value: "review", labelKey: "taskStageReview" },
  { value: "edit", labelKey: "taskStageEdit" },
  { value: "copy", labelKey: "taskStageCopy" },
  { value: "publish", labelKey: "taskStagePublish" },
];

const defaultPlatformOptions = ["Reels", "Shorts", "TikTok", "YouTube Shorts", "Pinterest", "小红书", "B站"];

const feedbackPlatformOptions = ["Reels", "TikTok", "YouTube Shorts", "Pinterest", "小红书", "B站"];

const feedbackFormatOptions = [
  { value: "comic grid", labelKey: "feedbackFormatComicGrid" },
  { value: "single panel", labelKey: "feedbackFormatSinglePanel" },
  { value: "webtoon strip", labelKey: "feedbackFormatWebtoonStrip" },
  { value: "short video", labelKey: "feedbackFormatShortVideo" },
];

const emptySchedule = () => ({
  plan: {},
  tasks: [],
  time_logs: [],
  activity: { total_seconds: 0, by_date: {}, by_page: {} },
  feedback: [],
  reviews: {},
  project_progress: [],
  shot_progress: [],
});

function normalizeReview(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (Object.keys(value).length === 0) return null;
  return { ...value, advice: Array.isArray(value.advice) ? value.advice : [] };
}

function normalizeSchedule(value) {
  const data = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  return {
    plan: data.plan && typeof data.plan === "object" && !Array.isArray(data.plan) ? data.plan : {},
    tasks: Array.isArray(data.tasks) ? data.tasks : [],
    time_logs: Array.isArray(data.time_logs) ? data.time_logs : [],
    activity: data.activity && typeof data.activity === "object"
      ? data.activity
      : { total_seconds: 0, by_date: {}, by_page: {} },
    feedback: Array.isArray(data.feedback) ? data.feedback : [],
    reviews: data.reviews && typeof data.reviews === "object" ? data.reviews : {},
    project_progress: Array.isArray(data.project_progress) ? data.project_progress : [],
    shot_progress: Array.isArray(data.shot_progress) ? data.shot_progress : [],
  };
}

const taskStatusOptions = [
  { value: "todo", labelKey: "statusTodo" },
  { value: "doing", labelKey: "statusDoing" },
  { value: "done", labelKey: "statusDone" },
  { value: "blocked", labelKey: "statusBlocked" },
  { value: "skipped", labelKey: "statusSkipped" },
  { value: "unknown", labelKey: "statusUnknown" },
];

const flowStateOptions = [
  { value: "smooth", labelKey: "flowSmooth" },
  { value: "normal", labelKey: "flowNormal" },
  { value: "blocked", labelKey: "flowBlocked" },
  { value: "rework", labelKey: "flowRework" },
  { value: "unknown", labelKey: "judgmentUnknown" },
];

export default function SchedulePage({ currentProject }) {
  const { t } = useI18n();
  const [schedule, setSchedule] = useState(emptySchedule);
  const [planForm, setPlanForm] = useState(defaultPlan);
  const [timeLog, setTimeLog] = useState(defaultTimeLog);
  const [feedback, setFeedback] = useState(defaultFeedback);
  const [feedbackScreenshot, setFeedbackScreenshot] = useState(null);
  const [review, setReview] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [showAllShots, setShowAllShots] = useState(false);

  async function refreshSchedule() {
    if (!currentProject) {
      setSchedule(emptySchedule());
      setReview(null);
      return;
    }
    const response = await api.getSchedule(currentProject.project_id);
    const data = normalizeSchedule(response.data);
    setSchedule(data);
    if (data.plan && Object.keys(data.plan).length > 0) {
      setPlanForm({
        ...defaultPlan,
        ...data.plan,
        platforms: Array.isArray(data.plan.platforms)
          ? data.plan.platforms.join(", ")
          : data.plan.platforms || "",
      });
    }
    setReview(normalizeReview(data.reviews?.week) || normalizeReview(data.reviews?.month));
  }

  useEffect(() => {
    refreshSchedule().catch((error) => setMessage(error.message));
  }, [currentProject?.project_id]);

  useEffect(() => {
    if (!currentProject) return undefined;
    const timer = window.setInterval(
      () => refreshSchedule().catch(() => {}),
      15_000,
    );
    return () => window.clearInterval(timer);
  }, [currentProject?.project_id]);

  const dueTasks = useMemo(
    () =>
      schedule.tasks.filter(
        (task) => task.date <= today && !["done", "skipped"].includes(task.status),
      ),
    [schedule.tasks],
  );

  const upcomingTasks = useMemo(
    () =>
      schedule.tasks
        .filter((task) => task.date > today && !["done", "skipped"].includes(task.status))
        .slice(0, 12),
    [schedule.tasks],
  );

  const visibleShotProgress = showAllShots
    ? schedule.shot_progress
    : schedule.shot_progress.slice(0, 12);

  const stats = useMemo(() => {
    const progress = schedule.project_progress;
    const total = progress.length || schedule.tasks.length;
    const done = progress.length
      ? progress.filter((item) => item.status === "done").length
      : schedule.tasks.filter((task) => task.status === "done").length;
    const manuallyTracked = schedule.time_logs.reduce(
      (sum, row) => sum + Number(row.minutes || 0),
      0,
    );
    const automaticSeconds = Number(schedule.activity?.total_seconds || 0);
    const latestFeedback = latestFeedbackSnapshots(schedule.feedback);
    const views = latestFeedback.reduce((sum, row) => sum + Number(row.views || 0), 0);
    const conversions = latestFeedback.reduce(
      (sum, row) => sum + Number(row.conversions || 0),
      0,
    );
    const revenue = latestFeedback.reduce((sum, row) => sum + Number(row.revenue || 0), 0);
    return {
      total,
      done,
      trackedHours: automaticSeconds > 0
        ? Math.round((automaticSeconds / 3600) * 10) / 10
        : Math.round((manuallyTracked / 60) * 10) / 10,
      trackedDisplay: automaticSeconds > 0 && automaticSeconds < 3600
        ? `${Math.max(1, Math.round(automaticSeconds / 60))}m`
        : `${automaticSeconds > 0
          ? Math.round((automaticSeconds / 3600) * 10) / 10
          : Math.round((manuallyTracked / 60) * 10) / 10}h`,
      automaticMinutes: Math.round(automaticSeconds / 60),
      manualMinutes: manuallyTracked,
      views,
      conversions,
      revenue: Math.round(revenue * 100) / 100,
      conversionRate: views ? Math.round((conversions / views) * 10000) / 100 : 0,
      completion: total ? Math.round((done / total) * 100) : 0,
    };
  }, [schedule]);

  async function run(label, action, successMessage = "") {
    setBusy(label);
    setMessage("");
    try {
      const response = await action();
      await refreshSchedule();
      setMessage(successMessage || response?.message || t("doneMessage"));
      return response;
    } catch (error) {
      setMessage(error.message);
      return null;
    } finally {
      setBusy("");
    }
  }

  async function handleGeneratePlan(event) {
    event.preventDefault();
    if (!currentProject) return;
    await run("plan", () =>
      api.generateSchedule(currentProject.project_id, {
        ...planForm,
        platforms: splitList(planForm.platforms),
        update_frequency_per_week: Number(planForm.update_frequency_per_week) || 3,
        daily_available_hours: Number(planForm.daily_available_hours) || 2,
        total_content_items: Number(planForm.total_content_items) || 4,
        panels_per_content: Number(planForm.panels_per_content) || 8,
        workflow_steps: Array.isArray(planForm.workflow_steps)
          ? planForm.workflow_steps
          : splitList(planForm.workflow_steps),
      }),
      t("scheduleGeneratedMessage"),
    );
  }

  async function updateTask(task, updates) {
    if (!currentProject) return;
    await run("task", () => api.updateScheduleTask(currentProject.project_id, task.task_id, updates));
  }

  async function handleTimeLog(event) {
    event.preventDefault();
    if (!currentProject) return;
    const response = await run("time", () =>
      api.addTimeLog(currentProject.project_id, {
        ...timeLog,
        minutes: Number(timeLog.minutes) || 1,
      }),
    );
    if (response?.ok) {
      setTimeLog({ ...defaultTimeLog, stage: timeLog.stage });
    }
  }

  async function handleFeedback(event) {
    event.preventDefault();
    if (!currentProject) return;
    const response = await run("feedback", () =>
      api.addSocialFeedback(currentProject.project_id, {
        ...feedback,
        views: Number(feedback.views) || 0,
        likes: Number(feedback.likes) || 0,
        comments: Number(feedback.comments) || 0,
        saves: Number(feedback.saves) || 0,
        shares: Number(feedback.shares) || 0,
        completion_rate: Number(feedback.completion_rate) || 0,
        conversions: Number(feedback.conversions) || 0,
        revenue: Number(feedback.revenue) || 0,
      }),
    );
    if (response?.ok) {
      setFeedback(defaultFeedback);
    }
  }

  async function handleExtractFeedbackScreenshot() {
    if (!currentProject || !feedbackScreenshot) return;
    const response = await run("feedback-screenshot", () =>
      api.extractSocialFeedbackScreenshot(currentProject.project_id, feedbackScreenshot, {
        platform: feedback.platform,
        publish_date: feedback.publish_date,
        content_id: feedback.content_id,
        use_ai: true,
      }),
    );
    const extracted = response?.data?.feedback;
    if (extracted) {
      setFeedback((current) => ({
        ...current,
        ...Object.fromEntries(
          Object.entries(extracted).filter(([, value]) => value !== "" && value !== null),
        ),
      }));
    }
    const warnings = response?.data?.warnings || [];
    if (warnings.length > 0) setMessage(warnings.join(" "));
  }

  async function handleReview(period) {
    if (!currentProject) return;
    const response = await run(`review-${period}`, () =>
      api.generateReview(currentProject.project_id, {
        period,
        anchor_date: today,
      }),
    );
    if (response?.data) setReview(response.data);
  }

  function togglePlanPlatform(platform) {
    const current = splitList(planForm.platforms);
    const next = current.includes(platform)
      ? current.filter((item) => item !== platform)
      : [...current, platform];
    setPlanForm({ ...planForm, platforms: next.join(", ") });
  }

  function toggleWorkflowStep(stage) {
    const current = Array.isArray(planForm.workflow_steps)
      ? planForm.workflow_steps
      : splitList(planForm.workflow_steps);
    const next = current.includes(stage)
      ? current.filter((item) => item !== stage)
      : [...current, stage];
    setPlanForm({ ...planForm, workflow_steps: next.length ? next : [stage] });
  }

  if (!currentProject) {
    return (
      <div className="panel">
        <h3>{t("noProjectSelected")}</h3>
        <p className="muted">{t("createOrSelectProject")}</p>
      </div>
    );
  }

  return (
    <section className="schedule-stack">
      <section className="panel">
        <div className="section-heading">
          <p className="eyebrow">{t("automaticProjectProgress")}</p>
          <h3>{t("creativeStageBoard")}</h3>
        </div>
        <p className="muted">{t("creativeStageBoardHint")}</p>
        <div className="project-progress-grid">
          {schedule.project_progress.map((item) => (
            <article className={`project-progress-item ${item.status}`} key={item.stage}>
              <span>{t(`projectStage_${item.stage}`)}</span>
              <strong>{t(`status${item.status[0].toUpperCase()}${item.status.slice(1)}`)}</strong>
              <small>{item.completed}/{item.total}</small>
            </article>
          ))}
        </div>
      </section>
      <section className="panel actual-shot-progress">
        <div className="archive-section-header">
          <div className="section-heading">
            <p className="eyebrow">{t("automaticShotProgress")}</p>
            <h3>{t("actualShotProgress")}</h3>
          </div>
          <span className="muted">
            {schedule.shot_progress.filter((item) => item.has_saved_image).length}/
            {schedule.shot_progress.length} {t("shotsWithSavedImages")}
          </span>
        </div>
        <p className="muted">{t("actualShotProgressHint")}</p>
        {schedule.shot_progress.length === 0 ? (
          <div className="empty-state align-left">{t("noStoryboardShots")}</div>
        ) : (
          <div className="shot-progress-list">
            {visibleShotProgress.map((shot) => (
              <article className={`shot-progress-row ${shot.status}`} key={shot.shot_id}>
                <div>
                  <strong>#{shot.index} · {shot.scene_id}</strong>
                  <small>{shot.shot_id}</small>
                </div>
                <span className={`status-pill ${shot.has_saved_image ? "done" : shot.status}`}>
                  {shot.has_saved_image ? t("savedImageReady") : t(`status${shot.status[0].toUpperCase()}${shot.status.slice(1)}`)}
                </span>
                <span className={`status-pill ${shot.locked ? "done" : "todo"}`}>
                  {shot.locked ? t("shotLocked") : t("shotNotLocked")}
                </span>
              </article>
            ))}
          </div>
        )}
        {schedule.shot_progress.length > 12 && (
          <button
            className="secondary compact-button"
            onClick={() => setShowAllShots((current) => !current)}
            type="button"
          >
            {showAllShots ? t("showFewerShots") : t("showAllShots")}
          </button>
        )}
      </section>
      <section className="schedule-stats">
        <div className="panel stat-card">
          <span>{t("completion")}</span>
          <strong>{stats.completion}%</strong>
          <small>{stats.done}/{stats.total} {t("taskUnit")}</small>
        </div>
        <div className="panel stat-card">
          <span>{t("tracked")}</span>
          <strong>{stats.trackedDisplay}</strong>
          <small>
            {t("automaticActiveTime")} {stats.automaticMinutes}m
            {stats.manualMinutes > 0 ? ` · ${t("manualLoggedTime")} ${stats.manualMinutes}m` : ""}
          </small>
        </div>
        <div className="panel stat-card">
          <span>{t("feedback")}</span>
          <strong>{schedule.feedback.length}</strong>
          <small>
            {stats.views} {t("totalViews")} · {stats.conversionRate}% {t("conversionRate")}
          </small>
        </div>
      </section>

      <details className="optional-planning-section">
        <summary>{t("optionalPublishingPlanTitle")}</summary>
        <p className="muted">{t("optionalPublishingPlanHint")}</p>
      <section className="content-grid balanced-two-col">
        <form className="panel form-panel" onSubmit={handleGeneratePlan}>
          <div className="section-heading">
            <p className="eyebrow">{t("optionalManualPlan")}</p>
            <h3>{t("generateProductionSchedule")}</h3>
          </div>
          <div className="form-row">
            <label>
              <span>{t("startDate")}</span>
              <input
                type="date"
                value={planForm.start_date}
                onChange={(event) => setPlanForm({ ...planForm, start_date: event.target.value })}
              />
            </label>
            <label>
              <span>{t("targetPublishDate")}</span>
              <input
                required
                type="date"
                value={planForm.target_publish_date}
                onChange={(event) =>
                  setPlanForm({ ...planForm, target_publish_date: event.target.value })
                }
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>{t("updatesPerWeek")}</span>
              <input
                min="1"
                max="14"
                type="number"
                value={planForm.update_frequency_per_week}
                onChange={(event) =>
                  setPlanForm({ ...planForm, update_frequency_per_week: event.target.value })
                }
              />
            </label>
            <label>
              <span>{t("hoursPerDay")}</span>
              <input
                min="0.25"
                step="0.25"
                type="number"
                value={planForm.daily_available_hours}
                onChange={(event) =>
                  setPlanForm({ ...planForm, daily_available_hours: event.target.value })
                }
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>{t("contentItems")}</span>
              <input
                min="1"
                type="number"
                value={planForm.total_content_items}
                onChange={(event) =>
                  setPlanForm({ ...planForm, total_content_items: event.target.value })
                }
              />
            </label>
            <label>
              <span>{t("panelsPerItem")}</span>
              <input
                min="1"
                type="number"
                value={planForm.panels_per_content}
                onChange={(event) =>
                  setPlanForm({ ...planForm, panels_per_content: event.target.value })
                }
              />
            </label>
          </div>
          <label>
            <span>{t("platforms")}</span>
            <div className="option-row">
              {defaultPlatformOptions.map((platform) => (
                <label className="check-option" key={platform}>
                  <input
                    checked={splitList(planForm.platforms).includes(platform)}
                    onChange={() => togglePlanPlatform(platform)}
                    type="checkbox"
                  />
                  <span>{platform}</span>
                </label>
              ))}
            </div>
          </label>
          <label>
            <span>{t("workflowSteps")}</span>
            <div className="option-row">
              {workflowStageOptions
                .filter((option) => ["script", "storyboard", "image", "edit", "copy", "publish"].includes(option.value))
                .map((option) => (
                  <label className="check-option" key={option.value}>
                    <input
                      checked={planForm.workflow_steps.includes(option.value)}
                      onChange={() => toggleWorkflowStep(option.value)}
                      type="checkbox"
                    />
                    <span>{t(option.labelKey)}</span>
                  </label>
                ))}
            </div>
          </label>
          <p className="muted">
            {t("scheduleReplaceWarning")}
          </p>
          <button className="primary" disabled={busy === "plan"} type="submit">
            {busy === "plan" ? t("planning") : t("generateSchedule")}
          </button>
        </form>

        <div className="panel">
          <div className="section-heading">
            <p className="eyebrow">{t("due")}</p>
            <h3>{dueTasks.length} {t("openTasksDue")}</h3>
          </div>
          <TaskList tasks={dueTasks} onUpdate={updateTask} t={t} />
          <div className="section-divider" />
          <div className="section-heading">
            <p className="eyebrow">{t("upcoming")}</p>
            <h3>{t("nextProductionTasks")}</h3>
          </div>
          <TaskList tasks={upcomingTasks} onUpdate={updateTask} t={t} />
          {message && <p className="form-message">{message}</p>}
        </div>
      </section>
      </details>

      <section className="content-grid two-col">
        <form className="panel form-panel" onSubmit={handleTimeLog}>
          <div className="section-heading">
            <p className="eyebrow">{t("tracked")}</p>
            <h3>{t("logWorkSession")}</h3>
          </div>
          <label>
            <span>{t("task")}</span>
            <select
              value={timeLog.task_id}
              onChange={(event) => {
                const task = schedule.tasks.find((item) => item.task_id === event.target.value);
                setTimeLog({
                  ...timeLog,
                  task_id: event.target.value,
                  stage: task?.stage || timeLog.stage,
                });
              }}
            >
              <option value="">{t("noLinkedTask")}</option>
              {schedule.tasks.map((task) => (
                <option key={task.task_id} value={task.task_id}>
                  {task.date} · {formatTaskTitle(task, t)}
                </option>
              ))}
            </select>
          </label>
          <div className="form-row">
            <label>
              <span>{t("date")}</span>
              <input
                type="date"
                value={timeLog.date}
                onChange={(event) => setTimeLog({ ...timeLog, date: event.target.value })}
              />
            </label>
            <label>
              <span>{t("minutes")}</span>
              <input
                min="1"
                type="number"
                value={timeLog.minutes}
                onChange={(event) => setTimeLog({ ...timeLog, minutes: event.target.value })}
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>{t("stage")}</span>
              <select
                value={timeLog.stage}
                onChange={(event) => setTimeLog({ ...timeLog, stage: event.target.value })}
              >
                {workflowStageOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {t(option.labelKey)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>{t("flow")}</span>
              <select
                value={timeLog.flow_state}
                onChange={(event) => setTimeLog({ ...timeLog, flow_state: event.target.value })}
              >
                {flowStateOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {t(option.labelKey)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            <span>{t("blocker")}</span>
            <input
              value={timeLog.blocker}
              onChange={(event) => setTimeLog({ ...timeLog, blocker: event.target.value })}
            />
          </label>
          <label>
            <span>{t("notes")}</span>
            <textarea
              rows="3"
              value={timeLog.notes}
              onChange={(event) => setTimeLog({ ...timeLog, notes: event.target.value })}
              placeholder={t("timeNotesPlaceholder")}
            />
          </label>
          <button className="primary" disabled={busy === "time"} type="submit">
            {t("logTime")}
          </button>
        </form>

        <form className="panel form-panel" onSubmit={handleFeedback}>
          <div className="section-heading">
            <p className="eyebrow">{t("feedback")}</p>
            <h3>{t("logSocialMetrics")}</h3>
          </div>
          <div className="screenshot-import">
            <label>
              <span>{t("feedbackScreenshot")}</span>
              <input
                accept="image/*"
                onChange={(event) => setFeedbackScreenshot(event.target.files?.[0] || null)}
                type="file"
              />
            </label>
            <button
              className="secondary"
              disabled={!feedbackScreenshot || busy === "feedback-screenshot"}
              onClick={handleExtractFeedbackScreenshot}
              type="button"
            >
              {busy === "feedback-screenshot" ? t("extractingMetrics") : t("extractMetricsFromScreenshot")}
            </button>
            <p className="muted">{t("feedbackScreenshotHint")}</p>
          </div>
          <div className="form-row">
            <label>
              <span>{t("contentId")}</span>
              <input
                value={feedback.content_id}
                onChange={(event) => setFeedback({ ...feedback, content_id: event.target.value })}
                placeholder="EP001"
              />
            </label>
            <label>
              <span>{t("platform")}</span>
              <select
                value={feedback.platform}
                onChange={(event) => setFeedback({ ...feedback, platform: event.target.value })}
              >
                {feedbackPlatformOptions.map((platform) => (
                  <option key={platform} value={platform}>
                    {platform}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>{t("publishDate")}</span>
              <input
                type="date"
                value={feedback.publish_date}
                onChange={(event) => setFeedback({ ...feedback, publish_date: event.target.value })}
              />
            </label>
            <label>
              <span>{t("snapshotDate")}</span>
              <input
                type="date"
                value={feedback.snapshot_date}
                onChange={(event) => setFeedback({ ...feedback, snapshot_date: event.target.value })}
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              <span>{t("judgment")}</span>
              <select
                value={feedback.judgment}
                onChange={(event) => setFeedback({ ...feedback, judgment: event.target.value })}
              >
                <option value="unknown">{t("judgmentUnknown")}</option>
                <option value="great">{t("judgmentGreat")}</option>
                <option value="good">{t("judgmentGood")}</option>
                <option value="average">{t("judgmentAverage")}</option>
                <option value="poor">{t("judgmentPoor")}</option>
              </select>
            </label>
            <label>
              <span>{t("daysSincePublish")}</span>
              <input
                readOnly
                value={daysBetween(feedback.publish_date, feedback.snapshot_date)}
              />
            </label>
          </div>
          <label>
            <span>{t("title")}</span>
            <input
              value={feedback.title}
              onChange={(event) => setFeedback({ ...feedback, title: event.target.value })}
            />
          </label>
          <div className="form-row">
            <label>
              <span>{t("aspect")}</span>
              <select
                value={feedback.aspect_ratio}
                onChange={(event) => setFeedback({ ...feedback, aspect_ratio: event.target.value })}
              >
                <option value="9:16">{t("aspectVertical916")}</option>
                <option value="4:5">{t("aspectPortrait45")}</option>
                <option value="1:1">{t("aspectSquare")}</option>
                <option value="16:9">{t("aspectLandscape169")}</option>
                <option value="2:3">{t("aspectPin23")}</option>
              </select>
            </label>
            <label>
              <span>{t("format")}</span>
              <select
                value={feedback.format}
                onChange={(event) => setFeedback({ ...feedback, format: event.target.value })}
              >
                {feedbackFormatOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {t(option.labelKey)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="metric-grid">
            {[
              ["views", t("views")],
              ["likes", t("likes")],
              ["comments", t("comments")],
              ["saves", t("saves")],
              ["shares", t("shares")],
              ["completion_rate", t("completionRate")],
              ["conversions", t("conversions")],
              ["revenue", t("revenue")],
            ].map(([field, label]) => (
              <label key={field}>
                <span>{label}</span>
                <input
                  min="0"
                  step={["completion_rate", "revenue"].includes(field) ? "0.01" : "1"}
                  type="number"
                  value={feedback[field]}
                  onChange={(event) => setFeedback({ ...feedback, [field]: event.target.value })}
                />
              </label>
            ))}
          </div>
          <label>
            <span>{t("currency")}</span>
            <input
              value={feedback.currency}
              onChange={(event) => setFeedback({ ...feedback, currency: event.target.value })}
              placeholder="USD"
            />
          </label>
          <label>
            <span>{t("notes")}</span>
            <textarea
              rows="3"
              value={feedback.notes}
              onChange={(event) => setFeedback({ ...feedback, notes: event.target.value })}
              placeholder={t("feedbackNotesPlaceholder")}
            />
          </label>
          <button className="primary" disabled={busy === "feedback"} type="submit">
            {t("saveFeedback")}
          </button>
        </form>
      </section>

      <section className="panel">
          <div className="section-heading">
            <p className="eyebrow">{t("review")}</p>
            <h3>{t("weeklyMonthlyRecap")}</h3>
          </div>
          <p className="muted">{t("reviewWorkflowHint")}</p>
          <ol className="guide-list compact-guide">
            <li>{t("reviewStepLogDuringProduction")}</li>
            <li>{t("reviewStepFillAfterPublish")}</li>
            <li>{t("reviewStepRunRecap")}</li>
          </ol>
          <div className="button-row">
            <button className="primary" onClick={() => handleReview("week")} type="button">
              {t("weeklyReview")}
            </button>
            <button className="secondary" onClick={() => handleReview("month")} type="button">
              {t("monthlyReview")}
            </button>
          </div>
          {review && (
            <div className="review-box">
              <div className="metric-grid">
                <Metric label={t("done")} value={`${review.tasks_done}/${review.tasks_total}`} />
                <Metric label={t("hours")} value={review.tracked_hours} />
                <Metric label={t("posts")} value={review.posts_logged} />
                <Metric label={t("views")} value={review.views} />
                <Metric label={t("conversions")} value={review.conversions || 0} />
                <Metric label={t("conversionRate")} value={`${review.conversion_rate || 0}%`} />
                <Metric label={t("revenue")} value={review.revenue || 0} />
              </div>
              <p className="muted">{t("bestPlatform")}: {review.best_platform || "-"}</p>
              <p className="muted">{t("bestAspect")}: {review.best_aspect_ratio || "-"}</p>
              <ul className="advice-list">
                {(Array.isArray(review.advice) ? review.advice : []).map((item) => (
                  <li key={item}>{localizeReviewAdvice(item, t)}</li>
                ))}
              </ul>
            </div>
          )}
      </section>
    </section>
  );
}

function TaskList({ tasks, onUpdate, t }) {
  if (tasks.length === 0) {
    return <p className="muted">{t("noTasksYet")}</p>;
  }
  return (
    <div className="task-list">
      {tasks.map((task) => (
        <article className={`task-row ${task.status}`} key={task.task_id}>
          <div>
            <strong>{formatTaskTitle(task, t)}</strong>
            <small>
              {task.date} · {task.content_id} · {task.estimate_minutes} {t("minuteShort")}
            </small>
          </div>
          <select
            value={task.status}
            onChange={(event) => onUpdate(task, { status: event.target.value })}
          >
            {taskStatusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {t(option.labelKey)}
              </option>
            ))}
          </select>
        </article>
      ))}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="mini-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatTaskTitle(task, t) {
  const labelKey = workflowStageOptions.find((option) => option.value === task.stage)?.labelKey;
  if (!labelKey) return task.title || task.task_id;
  return `${t(labelKey)} ${task.content_id || ""}`.trim();
}

function localizeReviewAdvice(item, t) {
  const text = String(item || "");
  if (text.startsWith("Reduce scope")) return t("reviewAdviceReduceScope");
  if (text.startsWith("Most tracked time went to")) return t("reviewAdviceSlowestStep");
  if (text.startsWith("Keep testing")) return t("reviewAdviceKeepTesting");
  if (text.startsWith("Resolve blocked tasks")) return t("reviewAdviceResolveBlocks");
  if (text.startsWith("Logged") && text.includes("conversions")) return t("reviewAdviceConversions");
  if (text.startsWith("Logged") && text.includes("total revenue")) return t("reviewAdviceRevenue");
  if (text.startsWith("Schedule is healthy")) return t("reviewAdviceHealthy");
  return text;
}

function addDays(dateValue, days) {
  const date = new Date(`${dateValue}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function daysBetween(startValue, endValue) {
  if (!startValue || !endValue) return 0;
  const start = new Date(`${startValue}T00:00:00`);
  const end = new Date(`${endValue}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;
  return Math.max(0, Math.round((end - start) / 86400000));
}

function latestFeedbackSnapshots(rows) {
  const latest = new Map();
  rows.forEach((row) => {
    const key = `${row.platform || ""}::${row.content_id || row.id || ""}`;
    const current = latest.get(key);
    const rowStamp = row.snapshot_date || row.timestamp || "";
    const currentStamp = current?.snapshot_date || current?.timestamp || "";
    if (!current || rowStamp >= currentStamp) latest.set(key, row);
  });
  return Array.from(latest.values());
}
