import csv
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from threading import RLock

from backend.app.config import (
    DEFAULT_PROJECTS_HOME,
    EXPORTS_DIR,
    GENERATED_ASSETS_DIR,
    PROJECT_REGISTRY_PATH,
    PROJECTS_DIR,
    REFERENCE_ASSETS_DIR,
    ensure_runtime_dirs,
    get_active_settings,
)
from backend.app.models.schemas import ProjectCreate, ProjectUpdate, ProjectWorkspacePayload
from backend.app.security import redact_sensitive_text


PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
_PROJECT_LOCKS: dict[str, RLock] = {}
_REGISTRY_LOCK = RLock()
PROJECTS_HOME = DEFAULT_PROJECTS_HOME
REGISTRY_PATH = PROJECT_REGISTRY_PATH
SELF_CONTAINED_SCHEMA_VERSION = 2
PROJECT_CONFIG_FILENAME = "project_config.json"


def _synchronized(function):
    @wraps(function)
    def wrapper(project_id: str, *args, **kwargs):
        lock = _PROJECT_LOCKS.setdefault(project_id, RLock())
        with lock:
            return function(project_id, *args, **kwargs)

    return wrapper


GENERATION_LOG_HEADERS = [
    "timestamp",
    "project_id",
    "shot_id",
    "status",
    "prompt",
    "endpoint",
    "model",
    "size",
    "quality",
    "status_code",
    "error_type",
    "error_code",
    "short_error",
    "error_message",
    "exception_type",
    "exception_message",
    "output_path",
    "output_url",
    "download_status",
    "download_error",
    "raw_response",
]
FAILED_JOBS_HEADERS = [
    "timestamp",
    "project_id",
    "shot_id",
    "prompt",
    "endpoint",
    "model",
    "status_code",
    "error_type",
    "error_code",
    "short_error",
    "error_message",
    "exception_type",
    "exception_message",
    "raw_response",
]
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
PUBLISHING_LOG_HEADERS = [
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return slug or "project"


def _validate_project_id(project_id: str) -> str:
    value = str(project_id or "")
    if not PROJECT_ID_PATTERN.fullmatch(value):
        raise FileNotFoundError("Project not found.")
    return value


def _path_is_within(path: str | Path, root: str | Path) -> bool:
    resolved_path = os.path.realpath(os.fspath(path))
    resolved_root = os.path.realpath(os.fspath(root))
    try:
        return os.path.commonpath((resolved_path, resolved_root)) == resolved_root
    except ValueError:
        return False


def resolve_path_within(root: str | Path, *parts: str | Path) -> Path:
    """Resolve a path and reject absolute, traversal, and symlink escapes from root."""
    resolved_root = os.path.realpath(os.fspath(root))
    resolved_path = os.path.realpath(
        os.path.join(resolved_root, *(os.fspath(part) for part in parts))
    )
    if not _path_is_within(resolved_path, resolved_root):
        raise ValueError("Path escapes its allowed storage directory.")
    return Path(resolved_path)


def find_existing_child_file(root: str | Path, filename: str) -> Path:
    """Return an existing direct child without constructing a path from the request value."""
    requested_name = str(filename or "")
    if not requested_name or requested_name in {".", ".."}:
        raise ValueError("Invalid project asset filename.")
    directory = Path(os.path.realpath(os.fspath(root)))
    for candidate in directory.iterdir() if directory.is_dir() else ():
        if candidate.name == requested_name and candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise FileNotFoundError("Project file not found.")


def _read_registry() -> dict[str, str]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Project registry JSON is invalid; it was not overwritten.") from exc
    projects = data.get("projects", {}) if isinstance(data, dict) else {}
    return {
        project_id: str(path)
        for project_id, path in projects.items()
        if PROJECT_ID_PATTERN.fullmatch(str(project_id)) and str(path).strip()
    }


def _write_registry(projects: dict[str, str]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = REGISTRY_PATH.with_name(f".{REGISTRY_PATH.name}.{uuid.uuid4().hex}.tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": utc_now(),
                "projects": dict(sorted(projects.items())),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if REGISTRY_PATH.exists():
        shutil.copy2(REGISTRY_PATH, REGISTRY_PATH.with_suffix(".json.bak"))
    temporary_path.replace(REGISTRY_PATH)


def register_project_path(project_id: str, project_dir: str | Path) -> Path:
    project_id = _validate_project_id(project_id)
    resolved = Path(project_dir).expanduser().resolve()
    config_path = resolved / PROJECT_CONFIG_FILENAME
    if not config_path.is_file():
        raise FileNotFoundError("The selected folder is not a Paneloom project.")
    config = _read_json(config_path, {})
    if not isinstance(config, dict) or config.get("project_id") != project_id:
        raise ValueError("Project folder ID does not match its configuration.")
    with _REGISTRY_LOCK:
        projects = _read_registry()
        existing = Path(projects[project_id]).expanduser().resolve() if project_id in projects else None
        if existing and existing != resolved and existing.exists():
            raise FileExistsError(
                "Another accessible project folder already uses this project ID. Move or close it first."
            )
        projects[project_id] = str(resolved)
        _write_registry(projects)
    return resolved


def unregister_project_path(project_id: str) -> None:
    with _REGISTRY_LOCK:
        projects = _read_registry()
        if projects.pop(project_id, None) is not None:
            _write_registry(projects)


def open_project_directory(project_path: str | Path) -> dict:
    resolved = Path(project_path).expanduser().resolve()
    config = _read_json(resolved / PROJECT_CONFIG_FILENAME, None)
    if not isinstance(config, dict) or not config.get("project_id"):
        raise FileNotFoundError("The selected folder is not a Paneloom project.")
    project_id = _validate_project_id(str(config["project_id"]))
    if int(config.get("schema_version") or 0) < SELF_CONTAINED_SCHEMA_VERSION:
        raise ValueError("This is a legacy project folder. Migrate it before opening from a new location.")
    register_project_path(project_id, resolved)
    return config


def get_project_dir(project_id: str) -> Path:
    project_id = _validate_project_id(project_id)
    with _REGISTRY_LOCK:
        registered = _read_registry().get(project_id)
    if registered:
        path = Path(registered).expanduser().resolve()
        if (path / PROJECT_CONFIG_FILENAME).is_file():
            return path
    legacy = resolve_path_within(PROJECTS_DIR, project_id)
    if (legacy / PROJECT_CONFIG_FILENAME).is_file():
        return legacy
    return Path(registered).expanduser().resolve() if registered else legacy


def is_self_contained_project(project_id: str) -> bool:
    project = get_project(project_id)
    return bool(
        project
        and int(project.get("schema_version") or 0) >= SELF_CONTAINED_SCHEMA_VERSION
        and project.get("storage_format") == "self_contained"
    )


def get_project_reference_dir(project_id: str) -> Path:
    project_id = _validate_project_id(project_id)
    if is_self_contained_project(project_id):
        return get_project_dir(project_id) / "assets" / "references"
    return resolve_path_within(REFERENCE_ASSETS_DIR, project_id)


def get_project_generated_dir(project_id: str) -> Path:
    project_id = _validate_project_id(project_id)
    if is_self_contained_project(project_id):
        return get_project_dir(project_id) / "generated"
    return resolve_path_within(GENERATED_ASSETS_DIR, project_id)


def get_project_export_dir(project_id: str) -> Path:
    project_id = _validate_project_id(project_id)
    if is_self_contained_project(project_id):
        return get_project_dir(project_id) / "exports"
    return resolve_path_within(EXPORTS_DIR, project_id)


def get_project_backup_dir(project_id: str) -> Path:
    return get_project_dir(project_id) / "backups"


def to_project_relative_path(project_id: str, path: str | Path) -> str:
    if not path:
        return ""
    candidate = Path(path)
    if not is_self_contained_project(project_id):
        return str(candidate)
    project_dir = get_project_dir(project_id).resolve()
    resolved = candidate.resolve() if candidate.is_absolute() else (project_dir / candidate).resolve()
    try:
        return resolved.relative_to(project_dir).as_posix()
    except ValueError as exc:
        raise ValueError("Project asset path escapes the project directory.") from exc


def resolve_project_path(project_id: str, stored_path: str | Path) -> Path:
    project_id = _validate_project_id(project_id)
    value = Path(stored_path)
    project_dir = get_project_dir(project_id).resolve()
    if value.is_absolute():
        resolved = Path(os.path.realpath(os.fspath(value)))
        allowed_roots = [project_dir]
        if not is_self_contained_project(project_id):
            allowed_roots.extend(
                (
                    resolve_path_within(GENERATED_ASSETS_DIR, project_id),
                    resolve_path_within(REFERENCE_ASSETS_DIR, project_id),
                    resolve_path_within(EXPORTS_DIR, project_id),
                )
            )
        if not any(_path_is_within(resolved, root) for root in allowed_roots):
            raise ValueError("Project asset path escapes the project storage directories.")
        return resolved
    return resolve_path_within(project_dir, value)


def project_file_url(project_id: str, category: str, filename: str) -> str:
    _validate_project_id(project_id)
    safe_name = str(filename or "")
    if not safe_name or safe_name in {".", ".."} or "/" in safe_name or "\\" in safe_name:
        raise ValueError("Invalid project asset filename.")
    return f"/projects/{project_id}/files/{category}/{safe_name}"


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if path.exists():
            shutil.copy2(path, path.with_suffix(f"{path.suffix}.bak"))
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _read_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid project JSON: {path.name}. The file was not overwritten.") from exc


def _ensure_csv(path: Path, headers: list[str]) -> None:
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)


def create_project(payload: ProjectCreate) -> dict:
    ensure_runtime_dirs()
    project_id = f"project-{uuid.uuid4().hex}"
    parent = Path(payload.parent_directory).expanduser() if payload.parent_directory.strip() else PROJECTS_HOME
    parent = parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    project_dir = parent / project_id
    project_dir.mkdir(parents=True, exist_ok=False)

    now = utc_now()
    project = {
        "project_id": project_id,
        "name": payload.name,
        "description": payload.description,
        "created_at": now,
        "updated_at": now,
        "project_path": ".",
        "archived": False,
        "schema_version": SELF_CONTAINED_SCHEMA_VERSION,
        "storage_format": "self_contained",
    }

    _write_json(project_dir / "project_config.json", project)
    _write_json(project_dir / "shots.json", [])
    _write_json(project_dir / "project_bible.json", _default_project_bible())
    _write_json(project_dir / "workspace.json", _default_project_workspace())
    _write_json(project_dir / "schedule.json", {})
    _write_json(project_dir / "tasks.json", [])
    _ensure_csv(project_dir / "generation_log.csv", GENERATION_LOG_HEADERS)
    _ensure_csv(project_dir / "failed_jobs.csv", FAILED_JOBS_HEADERS)
    _ensure_csv(project_dir / "time_logs.csv", TIME_LOG_HEADERS)
    _ensure_csv(project_dir / "publishing_log.csv", PUBLISHING_LOG_HEADERS)
    (project_dir / "assets" / "references").mkdir(parents=True, exist_ok=True)
    (project_dir / "generated").mkdir(parents=True, exist_ok=True)
    (project_dir / "exports").mkdir(parents=True, exist_ok=True)
    (project_dir / "backups").mkdir(parents=True, exist_ok=True)
    (project_dir / "metadata").mkdir(parents=True, exist_ok=True)
    try:
        register_project_path(project_id, project_dir)
    except Exception:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise
    return project


def list_projects() -> list[dict]:
    ensure_runtime_dirs()
    projects: list[dict] = []
    seen: set[str] = set()
    with _REGISTRY_LOCK:
        registered = _read_registry()
    config_paths = [Path(path) / PROJECT_CONFIG_FILENAME for path in registered.values()]
    config_paths.extend(PROJECTS_DIR.glob(f"*/{PROJECT_CONFIG_FILENAME}"))
    for config_path in config_paths:
        project = _read_json(config_path, {})
        if not isinstance(project, dict) or not project.get("project_id"):
            continue
        project_id = str(project["project_id"])
        if project_id in seen:
            continue
        seen.add(project_id)
        projects.append(
            {
                **project,
                "migration_required": int(project.get("schema_version") or 0)
                < SELF_CONTAINED_SCHEMA_VERSION,
                "project_available": config_path.is_file(),
            }
        )
    return sorted(projects, key=lambda item: item.get("updated_at", ""), reverse=True)


def sanitize_existing_project_logs() -> int:
    """Remove credential echoes from historical provider logs without retaining unsafe copies."""
    ensure_runtime_dirs()
    try:
        settings = get_active_settings(include_secret=True)
        secrets = [
            str(settings.get("api_key") or ""),
            str(settings.get("text_api_key") or ""),
        ]
    except (OSError, ValueError):
        secrets = []
    changed = 0
    for project in list_projects():
        project_dir = get_project_dir(project["project_id"])
        for filename in ("generation_log.csv", "failed_jobs.csv"):
            path = project_dir / filename
            if not path.is_file():
                continue
            original = path.read_text(encoding="utf-8")
            redacted = redact_sensitive_text(original, secrets)
            if redacted == original:
                continue
            temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            temporary_path.write_text(redacted, encoding="utf-8")
            temporary_path.replace(path)
            changed += 1
    return changed


@_synchronized
def update_project(project_id: str, payload: ProjectUpdate) -> dict:
    project = require_project(project_id)
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    project.update(updates)
    project["updated_at"] = utc_now()
    _write_json(get_project_dir(project_id) / "project_config.json", project)
    return project


@_synchronized
def duplicate_project(project_id: str, name: str = "") -> dict:
    source = require_project(project_id)
    source_dir = get_project_dir(project_id)
    duplicate = create_project(
        ProjectCreate(
            name=name.strip() or f"{source.get('name', 'Project')} Copy",
            description=source.get("description", ""),
            parent_directory=str(source_dir.parent),
        )
    )
    duplicate_id = duplicate["project_id"]
    target_dir = get_project_dir(duplicate_id)
    for entry in source_dir.iterdir():
        if entry.name in {PROJECT_CONFIG_FILENAME, "backups", "metadata"}:
            continue
        target = target_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)
    for path in target_dir.rglob("*.json"):
        if path.name == PROJECT_CONFIG_FILENAME:
            continue
        data = _read_json(path, None)
        if data is not None:
            _write_json(path, _rewrite_project_asset_paths(data, project_id, duplicate_id))
    return duplicate


@_synchronized
def delete_project(project_id: str) -> dict:
    project = require_project(project_id)
    project_dir = get_project_dir(project_id)
    contained = is_self_contained_project(project_id)
    trash_root = project_dir.parent / ".Paneloom Trash" / (
        f"{project_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )
    trash_root.parent.mkdir(parents=True, exist_ok=True)
    if trash_root.exists():
        raise FileExistsError("A trash entry with the same timestamp already exists.")
    shutil.move(str(project_dir), str(trash_root))
    unregister_project_path(project_id)

    if not contained:
        for label, source in [
            ("generated", resolve_path_within(GENERATED_ASSETS_DIR, project_id)),
            ("references", resolve_path_within(REFERENCE_ASSETS_DIR, project_id)),
            ("exports", resolve_path_within(EXPORTS_DIR, project_id)),
        ]:
            if source.exists():
                shutil.move(str(source), str(trash_root / label))
    return {
        "project_id": project_id,
        "name": project.get("name", ""),
        "deleted": True,
        "recoverable_path": str(trash_root),
    }


def get_project(project_id: str) -> dict | None:
    project_dir = get_project_dir(project_id)
    config_path = project_dir / "project_config.json"
    project = _read_json(config_path, None)
    return project if isinstance(project, dict) else None


def require_project(project_id: str) -> dict:
    project = get_project(project_id)
    if not project:
        raise FileNotFoundError(f"Project not found: {project_id}")
    return project


@_synchronized
def touch_project(project_id: str) -> None:
    project = require_project(project_id)
    project["updated_at"] = utc_now()
    _write_json(get_project_dir(project_id) / "project_config.json", project)


def _default_project_bible() -> dict:
    return {
        "visual_style": (
            "black and white manga storyboard, clean line art, expressive faces, "
            "cinematic panel composition"
        ),
        "characters": "",
        "locations": "",
        "props": "",
        "world_notes": "",
        "prompt_prefix": "",
        "style_analysis": "",
        "style_analysis_localized": {},
        "style_reference_filename": "",
        "visual_continuity_lock": "",
        "visual_anchor_shot_id": "",
        "visual_anchor_reference_filename": "",
        "visual_anchor_metrics": {},
        "negative_prompt": (
            "watermark, random text, speech bubble text, logo, distorted hands, "
            "bad anatomy, duplicated character, low quality"
        ),
    }


def _default_project_workspace() -> dict:
    return {
        "script": "",
        "script_import": {},
        "script_versions": [],
        "story_goal": "",
        "story_optimization": None,
        "target_panel_count": 8,
        "include_dialogue": True,
        "use_ai": True,
        "visual_format": "webtoon_strip",
        "panel_gutter_style": "framed",
        "selected_aspects": ["vertical_9_16"],
        "selected_reference_filenames": [],
        "updated_at": "",
    }


def get_project_workspace(project_id: str) -> dict:
    require_project(project_id)
    workspace = _read_json(
        get_project_dir(project_id) / "workspace.json",
        _default_project_workspace(),
    )
    if not isinstance(workspace, dict):
        workspace = _default_project_workspace()
    return {**_default_project_workspace(), **workspace}


@_synchronized
def save_project_workspace(project_id: str, payload: ProjectWorkspacePayload | dict) -> dict:
    require_project(project_id)
    data = payload.model_dump() if isinstance(payload, ProjectWorkspacePayload) else payload
    workspace = {
        **_default_project_workspace(),
        **data,
        "updated_at": utc_now(),
    }
    _write_json(get_project_dir(project_id) / "workspace.json", workspace)
    touch_project(project_id)
    return workspace


def _rewrite_project_asset_paths(value: object, old_id: str, new_id: str) -> object:
    if isinstance(value, list):
        return [_rewrite_project_asset_paths(item, old_id, new_id) for item in value]
    if isinstance(value, dict):
        return {
            key: _rewrite_project_asset_paths(item, old_id, new_id)
            for key, item in value.items()
        }
    if isinstance(value, str) and old_id in value:
        return value.replace(old_id, new_id)
    return value


def get_project_bible(project_id: str) -> dict:
    require_project(project_id)
    path = get_project_dir(project_id) / "project_bible.json"
    bible = _read_json(path, _default_project_bible())
    if not isinstance(bible, dict):
        bible = _default_project_bible()
    return {**_default_project_bible(), **bible}


@_synchronized
def save_project_bible(project_id: str, payload: dict) -> dict:
    require_project(project_id)
    bible = {**_default_project_bible(), **payload}
    _write_json(get_project_dir(project_id) / "project_bible.json", bible)
    touch_project(project_id)
    return bible
