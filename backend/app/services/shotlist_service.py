import csv
import json
import re
import shutil
import uuid
from functools import wraps
from pathlib import Path
from threading import RLock

from backend.app.models.schemas import ShotCreate, ShotUpdate
from backend.app.services.project_service import (
    get_project_dir,
    require_project,
    resolve_project_path,
    touch_project,
    utc_now,
)


_SHOT_LOCKS: dict[str, RLock] = {}


def _synchronized(function):
    @wraps(function)
    def wrapper(project_id: str, *args, **kwargs):
        lock = _SHOT_LOCKS.setdefault(project_id, RLock())
        with lock:
            return function(project_id, *args, **kwargs)

    return wrapper


def _shots_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "shots.json"


def _read_shots(project_id: str) -> list[dict]:
    require_project(project_id)
    path = _shots_path(project_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("shots.json is invalid; it was not overwritten.") from exc
    return data if isinstance(data, list) else []


def _write_shots(project_id: str, shots: list[dict]) -> None:
    path = _shots_path(project_id)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary_path.write_text(
        json.dumps(shots, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if path.exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    temporary_path.replace(path)
    touch_project(project_id)


def _shot_has_local_output(project_id: str, shot: dict) -> bool:
    paths = []
    if shot.get("output_path"):
        paths.append(shot.get("output_path"))
    for output in shot.get("outputs") or []:
        if isinstance(output, dict) and output.get("output_path"):
            paths.append(output.get("output_path"))
    return any(resolve_project_path(project_id, path).exists() for path in paths if path)


def _repair_stale_generation_state(project_id: str, shots: list[dict]) -> list[dict]:
    changed = False
    repaired = []
    for shot in shots:
        next_shot = dict(shot)
        if (
            next_shot.get("status") == "generating"
            and next_shot.get("output_url")
            and _shot_has_local_output(project_id, next_shot)
        ):
            next_shot["status"] = "done"
            next_shot["download_error"] = ""
            next_shot["generation_error"] = ""
            next_shot["updated_at"] = utc_now()
            changed = True
        repaired.append(next_shot)
    if changed:
        _write_shots(project_id, repaired)
    return repaired


def _latest_failure_by_shot(project_id: str) -> dict[str, str]:
    path = get_project_dir(project_id) / "failed_jobs.csv"
    if not path.exists():
        return {}
    failures: dict[str, str] = {}
    try:
        with path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                shot_id = row.get("shot_id") or ""
                message = _friendly_failure_message(row) or (
                    row.get("error_message")
                    or row.get("short_error")
                    or row.get("error_code")
                    or row.get("exception_message")
                    or ""
                )
                if shot_id and message:
                    failures[shot_id] = message
    except OSError:
        return {}
    return failures


def _friendly_failure_message(row: dict) -> str:
    status_code = str(row.get("status_code") or "")
    raw = str(row.get("raw_response") or "")
    message = str(row.get("error_message") or "")
    if status_code == "524" or "error code: 524" in raw.lower() or "cloudflare" in raw.lower():
        return (
            "图片接口上游超时（Cloudflare 524）。本地没有设置生成超时，"
            "但中转/供应商网关在图片生成完成前断开了请求。"
        )
    if "额度" in message or "quota" in message.lower():
        return message
    if status_code in {"408", "504"}:
        return f"图片接口上游超时（HTTP {status_code}）。"
    return ""


def _attach_generation_errors(project_id: str, shots: list[dict]) -> list[dict]:
    failures = _latest_failure_by_shot(project_id)
    if not failures:
        return shots
    changed = False
    enriched = []
    for shot in shots:
        next_shot = dict(shot)
        failure_message = failures.get(next_shot.get("shot_id", ""), "")
        if next_shot.get("status") == "failed" and failure_message:
            if next_shot.get("generation_error") != failure_message:
                next_shot["generation_error"] = failure_message
                next_shot["updated_at"] = utc_now()
                changed = True
        if (
            next_shot.get("status") == "generating"
            and not next_shot.get("output_url")
            and failure_message
        ):
            next_shot["status"] = "failed"
            next_shot["generation_error"] = failure_message
            next_shot["updated_at"] = utc_now()
            changed = True
        enriched.append(next_shot)
    if changed:
        _write_shots(project_id, enriched)
    return enriched


@_synchronized
def list_shots(project_id: str) -> list[dict]:
    repaired = _repair_stale_generation_state(project_id, _read_shots(project_id))
    return _attach_generation_errors(project_id, repaired)


def recover_interrupted_generation_states() -> int:
    from backend.app.services.project_service import list_projects

    recovered = 0
    for project in list_projects():
        project_id = project.get("project_id", "")
        if not project_id:
            continue
        lock = _SHOT_LOCKS.setdefault(project_id, RLock())
        with lock:
            shots = _read_shots(project_id)
            changed = False
            for shot in shots:
                if shot.get("status") == "generating":
                    shot["status"] = "failed"
                    shot["generation_error"] = (
                        "Generation was interrupted when the backend stopped. Retry this panel."
                    )
                    shot["updated_at"] = utc_now()
                    recovered += 1
                    changed = True
            if changed:
                _write_shots(project_id, shots)
    return recovered


@_synchronized
def add_shot(project_id: str, payload: ShotCreate) -> dict:
    shots = _read_shots(project_id)
    shot = _build_shot(payload)
    shots.append(shot)
    _write_shots(project_id, shots)
    return shot


@_synchronized
def add_shots(project_id: str, payloads: list[ShotCreate]) -> list[dict]:
    shots = _read_shots(project_id)
    created = [_build_shot(payload) for payload in payloads]
    shots.extend(created)
    _write_shots(project_id, shots)
    return created


def _build_shot(payload: ShotCreate) -> dict:
    now = utc_now()
    return {
        "shot_id": f"shot-{uuid.uuid4().hex[:8]}",
        "scene_id": payload.scene_id,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
        "duration": payload.duration,
        "visual_description": payload.visual_description,
        "prompt": payload.prompt,
        "negative_prompt": payload.negative_prompt,
        "status": "pending",
        "approval_status": "draft",
        "locked": False,
        "locked_at": "",
        "output_path": "",
        "output_url": "",
        "download_error": "",
        "selected_version_id": "",
        "revision_notes": payload.revision_notes,
        "created_at": now,
        "updated_at": now,
    }


@_synchronized
def get_shot(project_id: str, shot_id: str) -> dict | None:
    for shot in _read_shots(project_id):
        if shot.get("shot_id") == shot_id:
            return shot
    return None


@_synchronized
def update_shot(project_id: str, shot_id: str, updates: dict) -> dict:
    shots = _read_shots(project_id)
    for index, shot in enumerate(shots):
        if shot.get("shot_id") == shot_id:
            updated = {**shot, **updates, "updated_at": utc_now()}
            shots[index] = updated
            _write_shots(project_id, shots)
            return updated
    raise FileNotFoundError(f"Shot not found: {shot_id}")


@_synchronized
def patch_shot(project_id: str, shot_id: str, payload: ShotUpdate) -> dict:
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if not updates:
        shot = get_shot(project_id, shot_id)
        if not shot:
            raise FileNotFoundError(f"Shot not found: {shot_id}")
        return shot
    shot = get_shot(project_id, shot_id)
    if not shot:
        raise FileNotFoundError(f"Shot not found: {shot_id}")
    if shot.get("locked") and updates.get("locked") is not False:
        disallowed = set(updates) - {"approval_status", "locked"}
        if disallowed:
            raise ValueError("Unlock this shot before editing it.")
    next_locked = updates.get("locked", bool(shot.get("locked")))
    next_approval = updates.get("approval_status", shot.get("approval_status", "draft"))
    if next_locked and not (shot.get("output_path") or shot.get("output_url")):
        raise ValueError("A shot must have a saved image before it can be locked.")
    if next_approval == "approved" and not next_locked:
        raise ValueError("An approved shot must also be locked.")
    if "locked" in updates:
        updates["locked_at"] = utc_now() if updates["locked"] else ""
    return update_shot(project_id, shot_id, updates)


@_synchronized
def delete_shot(project_id: str, shot_id: str) -> dict:
    shots = _read_shots(project_id)
    target = next((shot for shot in shots if shot.get("shot_id") == shot_id), None)
    if target and target.get("locked"):
        raise ValueError("Unlock this approved shot before deleting it.")
    kept = [shot for shot in shots if shot.get("shot_id") != shot_id]
    if len(kept) == len(shots):
        raise FileNotFoundError(f"Shot not found: {shot_id}")
    _write_shots(project_id, kept)
    return {"shot_id": shot_id}


@_synchronized
def reorder_shots(project_id: str, shot_ids: list[str]) -> list[dict]:
    shots = _read_shots(project_id)
    by_id = {shot.get("shot_id"): shot for shot in shots}
    ordered = [by_id[shot_id] for shot_id in shot_ids if shot_id in by_id]
    remaining = [shot for shot in shots if shot.get("shot_id") not in set(shot_ids)]
    next_shots = ordered + remaining
    _write_shots(project_id, next_shots)
    return next_shots


@_synchronized
def select_shot_version(project_id: str, shot_id: str, version_id: str) -> dict:
    shot = get_shot(project_id, shot_id)
    if not shot:
        raise FileNotFoundError(f"Shot not found: {shot_id}")
    if shot.get("locked"):
        raise ValueError("Unlock this shot before selecting a different image version.")
    versions = shot.get("versions") if isinstance(shot.get("versions"), list) else []
    version = next(
        (item for item in versions if str(item.get("version_id")) == str(version_id)),
        None,
    )
    if not version:
        raise FileNotFoundError(f"Shot version not found: {version_id}")
    output_path = str(version.get("output_path") or "")
    if output_path and not resolve_project_path(project_id, output_path).exists():
        raise FileNotFoundError("The selected version image is missing from local storage.")
    if not output_path and not version.get("output_url"):
        raise FileNotFoundError("The selected version has no usable image output.")
    outputs = version.get("outputs") if isinstance(version.get("outputs"), list) else []
    return update_shot(
        project_id,
        shot_id,
        {
            "status": "done",
            "output_path": version.get("output_path", ""),
            "output_url": version.get("output_url", ""),
            "outputs": outputs,
            "selected_version_id": version_id,
            "download_error": "",
            "generation_error": "",
        },
    )


def apply_bible_to_shot_prompt(shot: dict, bible: dict) -> tuple[str, str]:
    visual_style = str(bible.get("visual_style", "")).strip()
    style_lock = ""
    if visual_style:
        color_lock = _style_color_lock(visual_style)
        style_lock = (
            "STYLE LOCK - mandatory: Use exactly this visual style for the final image: "
            f"{visual_style}. Do not drift into any other comic, manga, watercolor, newspaper, "
            "noir, sci-fi, cyberpunk, or grayscale style unless it is explicitly part of this style. "
            f"{color_lock}"
        )
    revision_notes = str(shot.get("revision_notes", "")).strip()
    revision_instruction = (
        f"REVISION NOTES - mandatory changes for this generation: {revision_notes}"
        if revision_notes
        else ""
    )
    prompt_parts = [
        bible.get("prompt_prefix", ""),
        style_lock,
        bible.get("characters", ""),
        bible.get("locations", ""),
        bible.get("props", ""),
        bible.get("world_notes", ""),
        revision_instruction,
        _remove_conflicting_style_from_shot_prompt(str(shot.get("prompt", "")), visual_style),
    ]
    prompt = ", ".join(part.strip() for part in prompt_parts if str(part).strip())
    negative_parts = [shot.get("negative_prompt", ""), bible.get("negative_prompt", "")]
    negative = ", ".join(part.strip() for part in negative_parts if str(part).strip())
    return prompt, negative


def _style_color_lock(visual_style: str) -> str:
    style = visual_style.lower()
    color_terms = [
        "color",
        "bright",
        "poster",
        "pop",
        "webtoon",
        "neon",
        "vibrant",
        "海报色",
        "亮色",
        "波普",
        "色块",
        "彩色",
        "霓虹",
    ]
    monochrome_terms = [
        "black-and-white",
        "black and white",
        "grayscale",
        "monochrome",
        "黑白",
        "灰阶",
        "單色",
        "单色",
    ]
    if any(term in style for term in color_terms) and not any(term in style for term in monochrome_terms):
        return (
            "COLOR LOCK: final image must use the specified bright/color palette; "
            "do not render as black-and-white, grayscale, monochrome ink, or noir."
        )
    if any(term in style for term in monochrome_terms):
        return "MONOCHROME LOCK: keep the image in the specified monochrome/grayscale palette."
    return ""


def _remove_conflicting_style_from_shot_prompt(prompt: str, visual_style: str) -> str:
    if not prompt or not visual_style:
        return prompt
    style = visual_style.lower()
    wants_color = any(
        term in style
        for term in [
            "color",
            "bright",
            "poster",
            "pop",
            "webtoon",
            "neon",
            "vibrant",
            "海报色",
            "亮色",
            "波普",
            "色块",
            "彩色",
            "霓虹",
        ]
    )
    if not wants_color:
        return prompt

    cleaned = prompt
    conflicting_patterns = [
        r"\bblack[- ]and[- ]white manga storyboard\b,?\s*",
        r"\bblack[- ]and[- ]white\b,?\s*",
        r"\bgrayscale\b,?\s*",
        r"\bmonochrome\b,?\s*",
        r"\bnoir\b,?\s*",
        r"黑白漫画分镜[，,]?\s*",
        r"黑白漫画[，,]?\s*",
        r"黑白[，,]?\s*",
        r"灰阶[，,]?\s*",
        r"单色[，,]?\s*",
        r"單色[，,]?\s*",
    ]
    for pattern in conflicting_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([，,。.])", r"\1", cleaned)
    return cleaned.strip(" ,，")
