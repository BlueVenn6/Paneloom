import csv
import json
import math
import shutil
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.app.models.schemas import (
    ReviewRequest,
    SchedulePlanRequest,
    ScheduleTaskUpdate,
    SocialFeedbackCreate,
    TimeLogCreate,
    ProjectActivityHeartbeat,
)
from backend.app.services.project_service import (
    get_project_bible,
    get_project_dir,
    get_project_reference_dir,
    get_project_workspace,
    require_project,
    utc_now,
)
from backend.app.services.shotlist_service import list_shots

DEFAULT_WORKFLOW = ["script", "storyboard", "image", "edit", "copy", "publish"]
STEP_LABELS = {
    "script": "Write script",
    "storyboard": "Break into panels",
    "image": "Generate images",
    "edit": "Edit and assemble",
    "copy": "Write caption",
    "publish": "Publish and log metrics",
}
STEP_WEIGHTS = {
    "script": 0.16,
    "storyboard": 0.18,
    "image": 0.32,
    "edit": 0.18,
    "copy": 0.06,
    "publish": 0.10,
}
TIME_LOG_HEADERS = [
    "id",
    "timestamp",
    "task_id",
    "date",
    "minutes",
    "stage",
    "flow_state",
    "blocker",
    "notes",
]
FEEDBACK_HEADERS = [
    "id",
    "timestamp",
    "content_id",
    "platform",
    "publish_date",
    "title",
    "aspect_ratio",
    "format",
    "views",
    "likes",
    "comments",
    "saves",
    "shares",
    "completion_rate",
    "snapshot_date",
    "days_since_publish",
    "conversions",
    "conversion_rate",
    "revenue",
    "currency",
    "judgment",
    "notes",
]


def get_schedule(project_id: str) -> dict:
    require_project(project_id)
    return {
        "plan": _read_json(_schedule_path(project_id), {}),
        "tasks": _read_json(_tasks_path(project_id), []),
        "time_logs": _read_csv(_time_log_path(project_id)),
        "activity": _read_json(_activity_path(project_id), _empty_activity()),
        "feedback": _read_csv(_feedback_path(project_id)),
        "reviews": {
            "week": _read_json(_review_path(project_id, "week"), {}),
            "month": _read_json(_review_path(project_id, "month"), {}),
        },
        "project_progress": _project_progress(project_id),
    }


def _empty_activity() -> dict:
    return {"total_seconds": 0, "by_date": {}, "by_page": {}, "by_date_page": {}, "updated_at": ""}


def record_project_activity(project_id: str, payload: ProjectActivityHeartbeat) -> dict:
    require_project(project_id)
    activity = _read_json(_activity_path(project_id), _empty_activity())
    today = datetime.now().astimezone().date().isoformat()
    seconds = int(payload.seconds)
    by_date = dict(activity.get("by_date") or {})
    by_page = dict(activity.get("by_page") or {})
    by_date_page = dict(activity.get("by_date_page") or {})
    by_date[today] = int(by_date.get(today) or 0) + seconds
    by_page[payload.page] = int(by_page.get(payload.page) or 0) + seconds
    today_pages = dict(by_date_page.get(today) or {})
    today_pages[payload.page] = int(today_pages.get(payload.page) or 0) + seconds
    by_date_page[today] = today_pages
    activity = {
        "total_seconds": int(activity.get("total_seconds") or 0) + seconds,
        "by_date": by_date,
        "by_page": by_page,
        "by_date_page": by_date_page,
        "updated_at": utc_now(),
    }
    _write_json(_activity_path(project_id), activity)
    return activity


def _project_progress(project_id: str) -> list[dict]:
    workspace = get_project_workspace(project_id)
    bible = get_project_bible(project_id)
    shots = list_shots(project_id)
    import_state = workspace.get("script_import") if isinstance(workspace.get("script_import"), dict) else {}
    reference_count = len(
        [path for path in get_project_reference_dir(project_id).glob("*") if path.is_file()]
    )
    generated_count = sum(
        1
        for shot in shots
        if shot.get("output_path") or shot.get("output_url") or shot.get("selected_version_id")
    )
    locked_count = sum(1 for shot in shots if shot.get("locked"))
    failed_count = sum(1 for shot in shots if shot.get("status") == "failed")
    export_dir = get_project_dir(project_id) / "exports"
    export_count = len([path for path in export_dir.glob("*") if path.is_file()]) if export_dir.exists() else 0
    bible_fields = [bible.get("characters"), bible.get("locations"), bible.get("world_notes")]

    def stage(stage_id: str, status: str, completed: int, total: int, detail: str) -> dict:
        return {
            "stage": stage_id,
            "status": status,
            "completed": completed,
            "total": total,
            "detail": detail,
            "source": "project_state",
        }

    script_done = bool(str(workspace.get("script") or "").strip())
    has_import = bool(import_state)
    bible_current = import_state.get("bibleCurrent") is True if has_import else True
    storyboard_current = import_state.get("storyboardCurrent") is True if has_import else True
    bible_done = all(str(value or "").strip() for value in bible_fields) and bible_current
    storyboard_stale = bool(shots) and not storyboard_current
    storyboard_done = bool(shots) and not storyboard_stale
    image_status = (
        "done"
        if shots and generated_count == len(shots)
        else "blocked"
        if failed_count and generated_count == 0
        else "doing"
        if generated_count or any(shot.get("status") == "generating" for shot in shots)
        else "todo"
    )
    return [
        stage("script", "done" if script_done else "todo", int(script_done), 1, "workspace.script"),
        stage(
            "bible",
            "done" if bible_done else "doing" if any(bible_fields) or reference_count else "todo",
            sum(1 for value in bible_fields if str(value or "").strip()),
            len(bible_fields),
            f"references:{reference_count}",
        ),
        stage(
            "storyboard",
            "done" if storyboard_done else "blocked" if storyboard_stale else "todo",
            len(shots) if storyboard_done else 0,
            max(1, len(shots)),
            "stale_after_script_change" if storyboard_stale else f"shots:{len(shots)}",
        ),
        stage("image", image_status, generated_count, len(shots), f"failed:{failed_count}"),
        stage(
            "lock",
            "done" if shots and locked_count == len(shots) else "doing" if locked_count else "todo",
            locked_count,
            len(shots),
            "shot_lock_state",
        ),
        stage("export", "done" if export_count else "todo", int(export_count > 0), 1, f"exports:{export_count}"),
    ]


def generate_schedule(project_id: str, payload: SchedulePlanRequest) -> dict:
    require_project(project_id)
    start = _parse_date(payload.start_date) or date.today()
    target = _parse_date(payload.target_publish_date)
    if not target:
        raise ValueError("target_publish_date must be YYYY-MM-DD.")
    if target < start:
        raise ValueError("target_publish_date must be after start_date.")

    workflow = list(dict.fromkeys(payload.workflow_steps or DEFAULT_WORKFLOW))
    publish_dates = _publish_dates(start, target, payload.update_frequency_per_week)
    if not publish_dates:
        publish_dates = [target]

    content_count = min(payload.total_content_items, len(publish_dates))
    publish_dates = publish_dates[:content_count]
    daily_capacity = max(15, int(payload.daily_available_hours * 60))
    tasks: list[dict] = []

    for content_index, publish_date in enumerate(publish_dates, 1):
        total_minutes = _estimate_content_minutes(payload.panels_per_content)
        for step in workflow:
            estimate = max(15, int(total_minutes * STEP_WEIGHTS.get(step, 0.12)))
            task_date = _schedule_step_date(
                start=start,
                publish_date=publish_date,
                step_index=workflow.index(step),
                step_count=len(workflow),
            )
            tasks.append(
                {
                    "task_id": f"task-{uuid.uuid4().hex[:8]}",
                    "content_id": f"EP{content_index:03d}",
                    "date": task_date.isoformat(),
                    "stage": step,
                    "title": f"{STEP_LABELS.get(step, step.title())} EP{content_index:03d}",
                    "estimate_minutes": estimate,
                    "actual_minutes": 0,
                    "status": "todo",
                    "platforms": payload.platforms,
                    "notes": "",
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                }
            )

    tasks = _balance_daily_capacity(tasks, daily_capacity)
    plan = {
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "start_date": start.isoformat(),
        "target_publish_date": target.isoformat(),
        "update_frequency_per_week": payload.update_frequency_per_week,
        "daily_available_hours": payload.daily_available_hours,
        "daily_capacity_minutes": daily_capacity,
        "platforms": payload.platforms,
        "total_content_items": content_count,
        "panels_per_content": payload.panels_per_content,
        "workflow_steps": workflow,
        "summary": _plan_summary(tasks, daily_capacity),
    }
    _write_json(_schedule_path(project_id), plan)
    _write_json(_tasks_path(project_id), tasks)
    _ensure_csv(_time_log_path(project_id), TIME_LOG_HEADERS)
    _ensure_csv(_feedback_path(project_id), FEEDBACK_HEADERS)
    return {"plan": plan, "tasks": tasks}


def update_task(project_id: str, task_id: str, payload: ScheduleTaskUpdate) -> dict:
    tasks = _read_json(_tasks_path(project_id), [])
    for index, task in enumerate(tasks):
        if task.get("task_id") == task_id:
            updates = payload.model_dump(exclude_unset=True)
            task = {**task, **{k: v for k, v in updates.items() if v is not None}}
            task["updated_at"] = utc_now()
            tasks[index] = task
            _write_json(_tasks_path(project_id), tasks)
            return task
    raise FileNotFoundError(f"Task not found: {task_id}")


def add_time_log(project_id: str, payload: TimeLogCreate) -> dict:
    require_project(project_id)
    row = {
        "id": f"time-{uuid.uuid4().hex[:8]}",
        "timestamp": utc_now(),
        **payload.model_dump(),
    }
    if not row["date"]:
        row["date"] = date.today().isoformat()
    _append_csv(_time_log_path(project_id), row, TIME_LOG_HEADERS)
    if row.get("task_id"):
        _add_task_actual_minutes(project_id, row["task_id"], int(row["minutes"]))
    return row


def add_social_feedback(project_id: str, payload: SocialFeedbackCreate) -> dict:
    require_project(project_id)
    data = payload.model_dump()
    publish_date = _parse_date(data.get("publish_date", ""))
    snapshot_date = _parse_date(data.get("snapshot_date", "")) or date.today()
    days_since_publish = (
        max(0, (snapshot_date - publish_date).days) if publish_date else 0
    )
    views = int(data.get("views") or 0)
    conversions = int(data.get("conversions") or 0)
    conversion_rate = round((conversions / views) * 100, 4) if views else 0
    row = {
        "id": f"social-{uuid.uuid4().hex[:8]}",
        "timestamp": utc_now(),
        **data,
        "snapshot_date": snapshot_date.isoformat(),
        "days_since_publish": days_since_publish,
        "conversion_rate": conversion_rate,
    }
    if not row["publish_date"]:
        row["publish_date"] = date.today().isoformat()
    _append_csv(_feedback_path(project_id), row, FEEDBACK_HEADERS)
    return row


def generate_review(project_id: str, payload: ReviewRequest) -> dict:
    schedule = get_schedule(project_id)
    anchor = _parse_date(payload.anchor_date) or date.today()
    days = 30 if payload.period == "month" else 7
    start = anchor - timedelta(days=days - 1)
    tasks = [
        task
        for task in schedule["tasks"]
        if start <= (_parse_date(task.get("date", "")) or anchor) <= anchor
    ]
    logs = [
        row
        for row in schedule["time_logs"]
        if start <= (_parse_date(row.get("date", "")) or anchor) <= anchor
    ]
    feedback = [
        row
        for row in schedule["feedback"]
        if start <= (_parse_date(row.get("publish_date", "")) or anchor) <= anchor
    ]
    feedback = _latest_feedback_snapshots(feedback)

    project_progress = schedule.get("project_progress") or []
    progress_source = project_progress if project_progress else tasks
    done = len([item for item in progress_source if item.get("status") == "done"])
    blocked = len([item for item in progress_source if item.get("status") == "blocked"])
    manual_minutes = sum(int(float(row.get("minutes") or 0)) for row in logs)
    activity = schedule.get("activity") or {}
    activity_seconds = sum(
        int(seconds or 0)
        for day, seconds in (activity.get("by_date") or {}).items()
        if start <= (_parse_date(day) or anchor) <= anchor
    )
    automatic_minutes = round(activity_seconds / 60)
    period_pages: defaultdict[str, int] = defaultdict(int)
    for day, pages in (activity.get("by_date_page") or {}).items():
        if start <= (_parse_date(day) or anchor) <= anchor and isinstance(pages, dict):
            for page, seconds in pages.items():
                period_pages[page] += int(seconds or 0)
    total_minutes = automatic_minutes if automatic_minutes > 0 else manual_minutes
    stage_minutes = defaultdict(int)
    blockers = Counter()
    for row in logs:
        stage_minutes[row.get("stage", "unknown")] += int(float(row.get("minutes") or 0))
        if row.get("blocker"):
            blockers[row["blocker"]] += 1

    views = sum(int(float(row.get("views") or 0)) for row in feedback)
    saves = sum(int(float(row.get("saves") or 0)) for row in feedback)
    shares = sum(int(float(row.get("shares") or 0)) for row in feedback)
    conversions = sum(int(float(row.get("conversions") or 0)) for row in feedback)
    revenue = sum(float(row.get("revenue") or 0) for row in feedback)
    conversion_rate = round((conversions / views) * 100, 4) if views else 0
    best_platform = _top_metric_group(feedback, "platform", "views")
    best_ratio = _top_metric_group(feedback, "aspect_ratio", "views")

    advice = []
    completion_rate = done / len(progress_source) if progress_source else 0
    if completion_rate < 0.7:
        advice.append("Reduce scope or move image/edit tasks earlier in the week.")
    if stage_minutes:
        slowest = max(stage_minutes.items(), key=lambda item: item[1])[0]
        advice.append(f"Most tracked time went to {slowest}; review that workflow step.")
    elif automatic_minutes:
        active_pages = period_pages
        if active_pages:
            busiest_page = max(active_pages.items(), key=lambda item: int(item[1] or 0))[0]
            advice.append(f"Most active project time was spent in {busiest_page}.")
    if best_ratio:
        advice.append(f"Keep testing {best_ratio} because it has the highest logged views in recent feedback.")
    if conversions:
        advice.append(f"Logged {conversions} conversions with {conversion_rate}% conversion rate.")
    if revenue:
        advice.append(f"Logged {round(revenue, 2)} total revenue in this period.")
    if blocked:
        advice.append("Resolve blocked tasks before adding new publishing targets.")
    if not advice:
        advice.append("Schedule is healthy. Keep the current cadence and log more feedback.")

    review = {
        "period": payload.period,
        "start_date": start.isoformat(),
        "end_date": anchor.isoformat(),
        "tasks_total": len(progress_source),
        "tasks_done": done,
        "tasks_blocked": blocked,
        "progress_source": "project_state" if project_progress else "manual_schedule",
        "completion_rate": round(completion_rate, 2),
        "tracked_minutes": total_minutes,
        "tracked_hours": round(total_minutes / 60, 2),
        "automatic_active_minutes": automatic_minutes,
        "manual_logged_minutes": manual_minutes,
        "activity_by_page": dict(period_pages),
        "stage_minutes": dict(stage_minutes),
        "top_blockers": blockers.most_common(5),
        "posts_logged": len(feedback),
        "views": views,
        "saves": saves,
        "shares": shares,
        "conversions": conversions,
        "conversion_rate": conversion_rate,
        "revenue": round(revenue, 2),
        "best_platform": best_platform,
        "best_aspect_ratio": best_ratio,
        "advice": advice,
        "created_at": utc_now(),
    }
    _write_json(_review_path(project_id, payload.period), review)
    return review


def _schedule_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "schedule.json"


def _tasks_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "tasks.json"


def _time_log_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "time_logs.csv"


def _activity_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "activity.json"


def _feedback_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "publishing_log.csv"


def _review_path(project_id: str, period: str) -> Path:
    return get_project_dir(project_id) / f"{period}_review.json"


def _read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid schedule JSON: {path.name}. The file was not overwritten.") from exc


def _write_json(path: Path, data) -> None:
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if path.exists():
        shutil.copy2(path, path.with_suffix(f"{path.suffix}.bak"))
    temporary_path.replace(path)


def _ensure_csv(path: Path, headers: list[str]) -> None:
    if path.exists():
        existing_rows = _read_csv(path)
        existing_headers = []
        with path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            existing_headers = next(reader, [])
        if all(header in existing_headers for header in headers):
            return
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for row in existing_rows:
                writer.writerow(row)
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _append_csv(path: Path, row: dict, headers: list[str]) -> None:
    _ensure_csv(path, headers)
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers, extrasaction="ignore")
        writer.writerow(row)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _publish_dates(start: date, target: date, frequency: int) -> list[date]:
    total_days = max(1, (target - start).days + 1)
    total_weeks = max(1, math.ceil(total_days / 7))
    total_posts = max(1, total_weeks * frequency)
    interval = max(1, total_days // total_posts)
    dates = []
    current = start
    while current <= target:
        dates.append(current)
        current += timedelta(days=interval)
    return dates


def _estimate_content_minutes(panels: int) -> int:
    return 90 + panels * 18


def _schedule_step_date(start: date, publish_date: date, step_index: int, step_count: int) -> date:
    window_days = max(1, (publish_date - start).days)
    offset = round((window_days / max(1, step_count - 1)) * step_index)
    scheduled = publish_date - timedelta(days=max(0, step_count - 1 - step_index))
    spread = start + timedelta(days=offset)
    return min(publish_date, max(start, min(scheduled, spread)))


def _balance_daily_capacity(tasks: list[dict], daily_capacity: int) -> list[dict]:
    totals: dict[str, int] = defaultdict(int)
    for task in sorted(tasks, key=lambda item: (item["date"], item["content_id"], item["stage"])):
        task_date = _parse_date(task["date"]) or date.today()
        estimate = int(task["estimate_minutes"])
        if estimate > daily_capacity:
            task["date"] = task_date.isoformat()
            totals[task["date"]] += estimate
            continue
        while totals[task_date.isoformat()] + estimate > daily_capacity:
            task_date += timedelta(days=1)
        task["date"] = task_date.isoformat()
        totals[task["date"]] += estimate
    return tasks


def _plan_summary(tasks: list[dict], daily_capacity: int) -> dict:
    by_date = defaultdict(int)
    for task in tasks:
        by_date[task["date"]] += int(task["estimate_minutes"])
    overloaded = [day for day, minutes in by_date.items() if minutes > daily_capacity]
    return {
        "task_count": len(tasks),
        "work_days": len(by_date),
        "estimated_minutes": sum(by_date.values()),
        "estimated_hours": round(sum(by_date.values()) / 60, 2),
        "overloaded_days": overloaded,
    }


def _add_task_actual_minutes(project_id: str, task_id: str, minutes: int) -> None:
    tasks = _read_json(_tasks_path(project_id), [])
    for index, task in enumerate(tasks):
        if task.get("task_id") == task_id:
            task["actual_minutes"] = int(task.get("actual_minutes") or 0) + minutes
            if task.get("status") == "todo":
                task["status"] = "doing"
            task["updated_at"] = utc_now()
            tasks[index] = task
            _write_json(_tasks_path(project_id), tasks)
            return


def _latest_feedback_snapshots(rows: list[dict]) -> list[dict]:
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (
            str(row.get("platform") or ""),
            str(row.get("content_id") or row.get("id") or ""),
        )
        current = latest.get(key)
        row_stamp = str(row.get("snapshot_date") or row.get("timestamp") or "")
        current_stamp = str(
            current.get("snapshot_date") or current.get("timestamp") or ""
        ) if current else ""
        if current is None or row_stamp >= current_stamp:
            latest[key] = row
    return list(latest.values())


def _top_metric_group(rows: list[dict], key: str, metric: str) -> str:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        group = str(row.get(key) or "")
        if not group:
            continue
        try:
            totals[group] += float(row.get(metric) or 0)
        except (TypeError, ValueError):
            continue
    return max(totals.items(), key=lambda item: item[1])[0] if totals else ""
