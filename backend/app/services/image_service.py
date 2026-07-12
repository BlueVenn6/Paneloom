import csv
import base64
import io
import json
import mimetypes
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import BoundedSemaphore, Lock
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from backend.app.config import (
    get_active_settings,
    get_text_api_config,
    is_offline_mode,
    validate_api_settings,
    validate_text_settings,
)
from backend.app.models.schemas import ImageGenerationRequest
from backend.app.security import redact_sensitive_value
from backend.app.services.aspect_service import resolve_generation_sizes
from backend.app.services.project_service import (
    get_project_bible,
    get_project_dir,
    get_project_generated_dir,
    get_project_reference_dir,
    get_project_workspace,
    project_file_url,
    require_project,
    resolve_project_path,
    to_project_relative_path,
    save_project_bible,
    utc_now,
)
from backend.app.services.shotlist_service import (
    apply_bible_to_shot_prompt,
    get_shot,
    list_shots,
    update_shot,
)

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.openai_image_client import generate_image  # noqa: E402
from api.openai_text_client import generate_text, generate_text_with_image  # noqa: E402

_GENERATION_LOCKS: dict[str, Lock] = {}
_LOG_LOCKS: dict[str, Lock] = {}
_IMAGE_PROVIDER_SLOTS = BoundedSemaphore(2)
MAX_REFERENCE_BYTES = 20 * 1024 * 1024
REFERENCE_FORMAT_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


def _bounded_generate_image(*args, **kwargs):
    with _IMAGE_PROVIDER_SLOTS:
        return generate_image(*args, **kwargs)


def _generation_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")


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


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _append_csv(path: Path, row: dict, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = headers
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            existing_headers = reader.fieldnames or []
            existing_rows = list(reader)
        missing_headers = [header for header in headers if header not in existing_headers]
        if missing_headers:
            fieldnames = existing_headers + missing_headers
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for existing_row in existing_rows:
                    writer.writerow(existing_row)
        elif existing_headers:
            fieldnames = existing_headers

    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        if not path.exists() or path.stat().st_size == 0:
            writer.writeheader()
        try:
            active_settings = get_active_settings(include_secret=True)
            secrets = [
                str(active_settings.get("api_key") or ""),
                str(active_settings.get("text_api_key") or ""),
            ]
        except (OSError, ValueError):
            secrets = []
        writer.writerow(redact_sensitive_value(row, secrets))


def _log_generation(project_id: str, row: dict) -> None:
    with _LOG_LOCKS.setdefault(project_id, Lock()):
        _append_csv(get_project_dir(project_id) / "generation_log.csv", row, GENERATION_LOG_HEADERS)


def _log_failure(project_id: str, row: dict) -> None:
    with _LOG_LOCKS.setdefault(project_id, Lock()):
        _append_csv(get_project_dir(project_id) / "failed_jobs.csv", row, FAILED_JOBS_HEADERS)


def _public_asset_url(project_id: str, filename: str) -> str:
    return project_file_url(project_id, "generated", filename)


def _generation_endpoint(settings: dict) -> str:
    base_url = settings.get("base_url") or ""
    return f"{base_url.rstrip('/')}/images/generations" if base_url else ""


def _generation_lock(project_id: str) -> Lock:
    if project_id not in _GENERATION_LOCKS:
        _GENERATION_LOCKS[project_id] = Lock()
    return _GENERATION_LOCKS[project_id]


def _reference_paths(project_id: str, filenames: list[str] | None) -> list[Path]:
    paths: list[Path] = []
    for filename in filenames or []:
        path = get_project_reference_dir(project_id) / Path(filename).name
        if path.exists() and path.is_file():
            paths.append(path)
    return paths


def _direct_reference_prompt_note(reference_paths: list[Path]) -> str:
    if not reference_paths:
        return ""
    names = ", ".join(path.stem for path in reference_paths)
    role_notes: list[str] = []
    for path in reference_paths:
        stem = path.stem.lower()
        if "character" in stem or "角色" in stem:
            role_notes.append("treat it as the core character sheet")
        elif "prop" in stem or "道具" in stem:
            role_notes.append("treat it as the core prop reference")
        elif "scene" in stem or "location" in stem or "场景" in stem:
            role_notes.append("treat it as the core location reference")
        elif "style" in stem or "风格" in stem:
            role_notes.append("treat it as the core style reference")
    role_text = "; ".join(dict.fromkeys(role_notes))
    if role_text:
        role_text = f" ({role_text})"
    return (
        "DIRECT GENERATION REFERENCE LOCK: Selected project reference asset names: "
        f"{names}{role_text}. The direct generation endpoint does not receive image pixels, "
        "so follow these references through textual continuity: consistent protagonist face shape, "
        "hair silhouette, clothing logic, recurring props, style anchors, palette logic, "
        "line quality, and storyboard panel composition. Obey the current STYLE LOCK above."
    )


def _parse_size(size: str) -> tuple[int, int] | None:
    try:
        width_text, height_text = str(size).lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _target_aspect_note(size_item: dict) -> str:
    dimensions = _parse_size(size_item.get("size", ""))
    if not dimensions:
        return ""
    width, height = dimensions
    orientation = "vertical portrait" if height > width else "horizontal landscape" if width > height else "square"
    return (
        f"Final image must use a {orientation} canvas at {width}x{height}px "
        f"with the full composition designed for aspect preset {size_item.get('label', '')}. "
        "This output is one panel in a continuous comic storyboard sequence, not a standalone poster. "
        "Keep character appearance, costumes, props, lighting, and world details consistent with adjacent panels. "
        "Do not create a comic page collage unless explicitly requested by the shot prompt."
    )


def _panel_gutter_note(panel_gutter_style: str) -> str:
    if panel_gutter_style == "seamless":
        return (
            "PANEL SEPARATION LOCK: Use seamless vertical flow. Do not draw white gutters, "
            "panel borders, comic frames, or rounded panel boxes. Connect beats with continuous "
            "background flow, camera movement, or soft transitions."
        )
    return (
        "PANEL SEPARATION LOCK: Use one uniform border system across every stacked beat. "
        "At a 1024px canvas width, every internal separator and outer panel border must have an "
        "equivalent 4px thickness, one identical solid color, square joins, and equal gutter spacing. "
        "Do not vary border thickness, opacity, color, decoration, spacing, or margins, and do not mix "
        "framed and borderless panels in the same image."
    )


def _visual_format_note(visual_format: str, panel_gutter_style: str = "framed") -> str:
    if visual_format == "webtoon_strip":
        if panel_gutter_style == "seamless":
            return (
                "VISUAL FORMAT LOCK: Generate one seamless vertical webtoon/comic strip image. "
                "The image must contain 3 to 5 sequential story beats inside the same canvas, "
                "top-to-bottom reading flow, no captions, no speech bubbles, and no readable text. "
                f"{_panel_gutter_note(panel_gutter_style)}"
            )
        return (
            "VISUAL FORMAT LOCK: Generate one vertical webtoon/comic strip image. "
            "The image must contain 3 to 5 stacked comic panels inside the same canvas, "
            "with visible gutters or spacing, top-to-bottom reading flow, sequential action beats, "
            "and consistent characters across the mini panels. Do not make a single poster-like illustration.\n"
            f"{_panel_gutter_note(panel_gutter_style)}"
        )
    return (
        "VISUAL FORMAT LOCK: Generate one single comic panel image only. "
        "Show one decisive story moment in one composition. Do not create multiple panels, "
        "collage layouts, page grids, or a webtoon strip."
    )


def _read_image_size(path: str | Path) -> str:
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            return f"{image.width}x{image.height}"
    except OSError:
        return ""


def _fit_image_to_target_size(path: str | Path, target_size: str) -> dict:
    dimensions = _parse_size(target_size)
    if not dimensions:
        return {
            "normalized": False,
            "original_size": "",
            "final_size": "",
            "normalization_error": "invalid_target_size",
        }

    image_path = Path(path)
    target_width, target_height = dimensions
    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            original_size = f"{image.width}x{image.height}"
            if image.size == (target_width, target_height):
                return {
                    "normalized": False,
                    "original_size": original_size,
                    "final_size": original_size,
                    "normalization_error": "",
                }

            fitted = ImageOps.fit(
                image,
                (target_width, target_height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            fitted.save(image_path, format="PNG", optimize=True)
            return {
                "normalized": True,
                "original_size": original_size,
                "final_size": f"{target_width}x{target_height}",
                "normalization_error": "",
            }
    except OSError as exc:
        return {
            "normalized": False,
            "original_size": "",
            "final_size": "",
            "normalization_error": str(exc),
        }


def _normalize_generated_result(result: dict, size_item: dict) -> dict:
    target_size = size_item.get("size", "")
    output_path = result.get("output_path")
    if not output_path:
        result.update(
            {
                "normalized": False,
                "original_size": "",
                "final_size": "",
                "normalization_error": "generated_image_was_not_saved_locally",
            }
        )
        return result

    normalize_info = _fit_image_to_target_size(output_path, target_size)
    final_size = _read_image_size(output_path)
    normalize_info["final_size"] = final_size or normalize_info.get("final_size", "")
    if target_size and final_size != target_size:
        normalize_info["normalization_error"] = (
            normalize_info.get("normalization_error")
            or f"final_size_mismatch: expected {target_size}, got {final_size or 'unknown'}"
        )
    result.update(normalize_info)
    return result


def _clamped_ratio(target: float, current: float, lower: float, upper: float) -> float:
    if target <= 0 or current <= 0:
        return 1.0
    return max(lower, min(upper, target / current))


def _apply_visual_anchor_tone_lock(output_path: str | Path, bible: dict) -> dict:
    anchor = bible.get("visual_anchor_metrics")
    if not isinstance(anchor, dict) or not anchor:
        return {"visual_anchor_applied": False}
    path = Path(output_path)
    if not path.exists():
        return {"visual_anchor_applied": False, "visual_anchor_error": "generated_image_missing"}
    try:
        before = _image_style_metrics(path)
        brightness_factor = _clamped_ratio(
            float(anchor.get("brightness") or 0),
            float(before.get("brightness") or 0),
            0.82,
            1.22,
        )
        contrast_factor = _clamped_ratio(
            float(anchor.get("contrast") or 0),
            float(before.get("contrast") or 0),
            0.85,
            1.18,
        )
        saturation_factor = _clamped_ratio(
            float(anchor.get("saturation") or 0),
            float(before.get("saturation") or 0),
            0.85,
            1.18,
        )
        adjusted = any(
            abs(factor - 1.0) >= 0.015
            for factor in (brightness_factor, contrast_factor, saturation_factor)
        )
        if adjusted:
            with Image.open(path) as image:
                rendered = ImageOps.exif_transpose(image).convert("RGB")
                rendered = ImageEnhance.Brightness(rendered).enhance(brightness_factor)
                rendered = ImageEnhance.Contrast(rendered).enhance(contrast_factor)
                rendered = ImageEnhance.Color(rendered).enhance(saturation_factor)
                temporary = path.with_name(f".{path.stem}-visual-lock-{_generation_stamp()}.tmp")
                try:
                    rendered.save(temporary, format="PNG", optimize=True)
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
        after = _image_style_metrics(path)
        return {
            "visual_anchor_applied": True,
            "visual_anchor_adjusted": adjusted,
            "visual_anchor_shot_id": str(bible.get("visual_anchor_shot_id") or ""),
            "visual_metrics_before": before,
            "visual_metrics_after": after,
            "visual_adjustment": {
                "brightness": round(brightness_factor, 3),
                "contrast": round(contrast_factor, 3),
                "saturation": round(saturation_factor, 3),
            },
        }
    except (OSError, TypeError, ValueError) as exc:
        return {"visual_anchor_applied": False, "visual_anchor_error": str(exc)}


def _outputs_from_results(project_id: str, results: list[dict]) -> list[dict]:
    return [
        {
            "aspect_preset": item.get("aspect_preset", "default"),
            "aspect_label": item.get("aspect_label", "Default"),
            "size": item.get("target_size", ""),
            "provider_size": item.get("provider_size", ""),
            "visual_format": item.get("visual_format", ""),
            "original_size": item.get("original_size", ""),
            "final_size": item.get("final_size", ""),
            "normalized": item.get("normalized", False),
            "normalization_error": item.get("normalization_error", ""),
            "visual_anchor_applied": item.get("visual_anchor_applied", False),
            "visual_anchor_adjusted": item.get("visual_anchor_adjusted", False),
            "visual_anchor_shot_id": item.get("visual_anchor_shot_id", ""),
            "visual_metrics_before": item.get("visual_metrics_before", {}),
            "visual_metrics_after": item.get("visual_metrics_after", {}),
            "visual_adjustment": item.get("visual_adjustment", {}),
            "visual_anchor_error": item.get("visual_anchor_error", ""),
            "output_path": to_project_relative_path(project_id, item.get("output_path", "")),
            "output_url": _public_asset_url(project_id, item["target_filename"])
            if item.get("output_path")
            else item.get("output_url", ""),
            "status": item.get("status", ""),
            "download_error": item.get("download_error", ""),
        }
        for item in results
        if item.get("ok")
    ]


def _sequence_context_note(project_id: str, shot_id: str) -> str:
    shots = list_shots(project_id)
    index = next(
        (position for position, item in enumerate(shots) if item.get("shot_id") == shot_id),
        -1,
    )
    if index < 0:
        return ""

    current = shots[index]
    previous = shots[index - 1] if index > 0 else None
    next_shot = shots[index + 1] if index + 1 < len(shots) else None
    pieces = [
        f"This is panel {index + 1} of {len(shots)} in a continuous comic storyboard sequence.",
        "Design it as a story beat connected to the surrounding panels, not as a standalone illustration.",
    ]
    current_visual = current.get("visual_description") or current.get("prompt") or ""
    if current_visual:
        pieces.append(f"Current panel story beat: {current_visual}")
    if previous:
        previous_visual = previous.get("visual_description") or previous.get("prompt") or ""
        if previous_visual:
            pieces.append(f"Previous panel continuity: {previous_visual[:260]}")
    if next_shot:
        next_visual = next_shot.get("visual_description") or next_shot.get("prompt") or ""
        if next_visual:
            pieces.append(f"Next panel setup: {next_visual[:260]}")
    pieces.append("Keep recurring characters, clothing, props, setting, and emotional progression consistent.")
    return "\n".join(pieces)


def _failure_details(
    *,
    settings: dict,
    prompt: str,
    result: dict | None = None,
    error_code: str = "",
    error_message: str = "",
) -> dict:
    result = result or {}
    short_error = result.get("error_code") or error_code or "configuration_error"
    provider_error_code = result.get("provider_error_code") or ""
    details = {
        "prompt": prompt,
        "endpoint": result.get("endpoint") or _generation_endpoint(settings),
        "model": result.get("model") or settings.get("image_model", ""),
        "size": result.get("size") or "",
        "quality": result.get("quality") or settings.get("image_quality", ""),
        "status_code": result.get("status_code") or "",
        "error_type": result.get("error_type") or "",
        "error_code": provider_error_code or short_error,
        "short_error": short_error,
        "error_message": result.get("error_message") or error_message,
        "raw_response": result.get("raw_response") or _stringify(result.get("raw")),
        "provider_error_code": provider_error_code,
        "exception_type": result.get("exception_type") or "",
        "exception_message": result.get("exception_message") or "",
        "download_status": result.get("download_status") or "",
        "download_error": result.get("download_error") or "",
    }
    return redact_sensitive_value(
        details,
        [str(settings.get("api_key") or ""), str(settings.get("text_api_key") or "")],
    )


def generate_shot_image(
    project_id: str,
    shot_id: str,
    request: ImageGenerationRequest | None = None,
) -> dict:
    with _generation_lock(project_id):
        return _generate_shot_image_locked(project_id, shot_id, request)


def _generate_shot_image_locked(
    project_id: str,
    shot_id: str,
    request: ImageGenerationRequest | None = None,
) -> dict:
    require_project(project_id)
    shot = get_shot(project_id, shot_id)
    if not shot:
        raise FileNotFoundError(f"Shot not found: {shot_id}")
    if is_offline_mode():
        return {
            "project_id": project_id,
            "shot_id": shot_id,
            "status": "blocked",
            "output_path": shot.get("output_path", ""),
            "output_url": shot.get("output_url", ""),
            "error": "offline_mode",
            "error_code": "offline_mode",
            "error_message": "Cloud image generation is unavailable in offline mode.",
        }
    if shot.get("locked"):
        return {
            "project_id": project_id,
            "shot_id": shot_id,
            "status": "blocked",
            "output_path": shot.get("output_path", ""),
            "output_url": shot.get("output_url", ""),
            "error": "shot_locked",
            "error_code": "shot_locked",
            "error_message": "Unlock this approved shot before generating a replacement.",
        }

    settings = get_active_settings(include_secret=True)
    config_errors = validate_api_settings(settings)
    project_bible = get_project_bible(project_id)
    prompt = request.prompt if request and request.prompt else shot.get("prompt", "")
    if not (request and request.prompt):
        prompt, bible_negative = apply_bible_to_shot_prompt(shot, project_bible)
    else:
        bible_negative = ""
    if shot.get("negative_prompt"):
        prompt = f"{prompt}\n\nNegative prompt: {shot['negative_prompt']}"
    elif bible_negative:
        prompt = f"{prompt}\n\nNegative prompt: {bible_negative}"
    reference_paths = _reference_paths(
        project_id,
        request.reference_filenames if request else [],
    )
    sequence_note = _sequence_context_note(project_id, shot_id)
    if sequence_note:
        prompt = f"{sequence_note}\n\n{prompt}"
    visual_format = request.visual_format if request else "single_panel"
    panel_gutter_style = request.panel_gutter_style if request else "framed"
    prompt = f"{_visual_format_note(visual_format, panel_gutter_style)}\n\n{prompt}"

    update_shot(project_id, shot_id, {"status": "generating"})
    timestamp = utc_now()

    if config_errors:
        error = " ".join(config_errors)
        details = _failure_details(
            settings=settings,
            prompt=prompt,
            error_code="configuration_error",
            error_message=error,
        )
        update_shot(
            project_id,
            shot_id,
            {
                "status": "failed",
                "generation_error": details["error_message"] or details["short_error"],
            },
        )
        _log_generation(
            project_id,
            {
                "timestamp": timestamp,
                "project_id": project_id,
                "shot_id": shot_id,
                "status": "failed",
                **details,
                "output_path": "",
                "output_url": "",
                "download_status": "",
                "download_error": "",
            },
        )
        _log_failure(
            project_id,
            {
                "timestamp": timestamp,
                "project_id": project_id,
                "shot_id": shot_id,
                "prompt": details["prompt"],
                "endpoint": details["endpoint"],
                "model": details["model"],
                "status_code": details["status_code"],
                "error_type": details["error_type"],
                "error_code": details["error_code"],
                "short_error": details["short_error"],
                "error_message": details["error_message"],
                "exception_type": details["exception_type"],
                "exception_message": details["exception_message"],
                "raw_response": details["raw_response"],
            },
        )
        return {
            "project_id": project_id,
            "shot_id": shot_id,
            "status": "failed",
            "output_path": "",
            "output_url": "",
            "error": details["short_error"],
            "error_code": details["error_code"],
            "short_error": details["short_error"],
            "error_message": details["error_message"],
            "details": details,
        }

    output_dir = get_project_generated_dir(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    requested_aspects = list(request.aspect_presets) if request else []
    if not requested_aspects:
        requested_aspects = list(get_project_workspace(project_id).get("selected_aspects") or [])
    if not requested_aspects:
        requested_aspects = ["vertical_9_16"]
    generation_sizes = resolve_generation_sizes(
        requested_aspects,
        request.size if request and request.size else "1024x1792",
    )
    results = []
    version_stamp = _generation_stamp()
    for size_item in generation_sizes:
        suffix = "" if size_item["id"] == "default" else f"-{size_item['id']}"
        filename = f"{shot_id}{suffix}-{version_stamp}.png"
        output_path = output_dir / filename
        size_prompt = f"{prompt}\n\n{_target_aspect_note(size_item)}"
        provider_size = size_item.get("generation_size") or size_item["size"]
        direct_reference_note = _direct_reference_prompt_note(reference_paths)
        if direct_reference_note:
            size_prompt = f"{size_prompt}\n\n{direct_reference_note}"
        result = _bounded_generate_image(
            settings,
            prompt=size_prompt,
            size=provider_size,
            quality=request.quality if request else None,
            output_path=output_path,
        )
        result["aspect_preset"] = size_item["id"]
        result["aspect_label"] = size_item["label"]
        result["target_size"] = size_item["size"]
        result["provider_size"] = provider_size
        result["visual_format"] = visual_format
        result["target_filename"] = filename
        if result.get("ok"):
            _normalize_generated_result(result, size_item)
            if not result.get("normalization_error"):
                result.update(_apply_visual_anchor_tone_lock(output_path, project_bible))
            if result.get("normalization_error") or result.get("final_size") != size_item["size"]:
                result.update(
                    {
                        "ok": False,
                        "status": "failed",
                        "error": "image_size_mismatch",
                        "error_code": "image_size_mismatch",
                        "short_error": "image_size_mismatch",
                        "error_message": (
                            f"Generated image did not match selected ratio. "
                            f"Expected {size_item['size']}, got {result.get('final_size') or 'unknown'}."
                        ),
                    }
                )
        results.append(result)
        if not result.get("ok"):
            break

    result = results[-1] if results else {}

    if result.get("ok"):
        result_status = result.get("status") or "done"
        saved_path = to_project_relative_path(project_id, result.get("output_path") or "")
        output_url = _public_asset_url(project_id, result["target_filename"]) if saved_path else result.get("output_url", "")
        download_status = result.get("download_status", "")
        download_error = result.get("download_error", "")
        outputs = _outputs_from_results(project_id, results)
        version_entry = {
            "version_id": version_stamp,
            "created_at": timestamp,
            "status": result_status,
            "output_path": saved_path,
            "output_url": output_url,
            "outputs": outputs,
        }
        existing_versions = shot.get("versions") if isinstance(shot.get("versions"), list) else []
        update_shot(
            project_id,
            shot_id,
            {
                "status": result_status,
                "output_path": saved_path,
                "output_url": output_url,
                "outputs": outputs,
                "versions": [*existing_versions, version_entry],
                "selected_version_id": version_stamp,
                "download_error": download_error,
                "generation_error": "",
            },
        )
        _log_generation(
            project_id,
            {
                "timestamp": timestamp,
                "project_id": project_id,
                "shot_id": shot_id,
                "status": result_status,
                "prompt": prompt,
                "endpoint": result.get("endpoint", ""),
                "model": result.get("model", ""),
                "size": result.get("size", ""),
                "quality": result.get("quality", ""),
                "status_code": result.get("status_code", ""),
                "error_type": "",
                "error_code": "",
                "short_error": "",
                "error_message": "",
                "exception_type": "",
                "exception_message": "",
                "output_path": saved_path,
                "output_url": output_url,
                "download_status": download_status,
                "download_error": download_error,
                "raw_response": "",
            },
        )
        return {
            "project_id": project_id,
            "shot_id": shot_id,
            "status": result_status,
            "output_path": saved_path,
            "output_url": output_url,
            "download_status": download_status,
            "download_error": download_error,
            "outputs": outputs,
            "version_id": version_stamp,
            "error": "",
            "error_code": "",
            "short_error": "",
            "error_message": "",
        }

    details = _failure_details(settings=settings, prompt=prompt, result=result)
    error = details["short_error"] or "image_generation_failed"
    partial_outputs = _outputs_from_results(project_id, results)
    partial_result = next((item for item in reversed(results) if item.get("ok")), None)
    partial_path = (
        to_project_relative_path(project_id, partial_result.get("output_path", ""))
        if partial_result
        else ""
    )
    partial_url = (
        _public_asset_url(project_id, partial_result["target_filename"])
        if partial_result and partial_result.get("output_path")
        else ""
    )
    partial_versions = shot.get("versions") if isinstance(shot.get("versions"), list) else []
    if partial_outputs:
        partial_versions = [
            *partial_versions,
            {
                "version_id": version_stamp,
                "created_at": timestamp,
                "status": "partial",
                "output_path": partial_path,
                "output_url": partial_url,
                "outputs": partial_outputs,
            },
        ]
    update_shot(
        project_id,
        shot_id,
        {
            "status": "failed",
            "generation_error": details["error_message"] or details["short_error"],
            "download_error": details["download_error"],
            "output_path": partial_path,
            "output_url": partial_url,
            "outputs": partial_outputs,
            "versions": partial_versions,
            "selected_version_id": version_stamp if partial_outputs else shot.get("selected_version_id", ""),
        },
    )
    _log_generation(
        project_id,
        {
            "timestamp": timestamp,
            "project_id": project_id,
            "shot_id": shot_id,
            "status": "failed",
            "prompt": details["prompt"],
            "endpoint": details["endpoint"],
            "model": details["model"],
            "size": details["size"],
            "quality": details["quality"],
            "status_code": details["status_code"],
            "error_type": details["error_type"],
            "error_code": details["error_code"],
            "short_error": details["short_error"],
            "error_message": details["error_message"],
            "exception_type": details["exception_type"],
            "exception_message": details["exception_message"],
            "output_path": partial_path,
            "output_url": partial_url,
            "download_status": details["download_status"],
            "download_error": details["download_error"],
            "raw_response": details["raw_response"],
        },
    )
    _log_failure(
        project_id,
        {
            "timestamp": timestamp,
            "project_id": project_id,
            "shot_id": shot_id,
            "prompt": details["prompt"],
            "endpoint": details["endpoint"],
            "model": details["model"],
            "status_code": details["status_code"],
            "error_type": details["error_type"],
            "error_code": details["error_code"],
            "short_error": details["short_error"],
            "error_message": details["error_message"],
            "exception_type": details["exception_type"],
            "exception_message": details["exception_message"],
            "raw_response": details["raw_response"],
        },
    )
    return {
        "project_id": project_id,
        "shot_id": shot_id,
        "status": "failed",
        "output_path": partial_path,
        "output_url": partial_url,
        "outputs": partial_outputs,
        "error": error,
        "error_code": details["error_code"],
        "short_error": details["short_error"],
        "error_message": details["error_message"],
        "details": details,
    }

def generate_project_batch(
    project_id: str,
    shot_ids: list[str] | None = None,
    only_pending: bool = True,
    stop_on_error: bool = False,
    aspect_presets: list[str] | None = None,
    reference_filenames: list[str] | None = None,
    visual_format: str = "single_panel",
    panel_gutter_style: str = "framed",
) -> dict:
    require_project(project_id)
    requested = set(shot_ids or [])
    candidates = [
        shot
        for shot in list_shots(project_id)
        if (not requested or shot.get("shot_id") in requested)
        and not shot.get("locked")
        and (
            not only_pending
            or shot.get("status")
            in {"pending", "failed", "generating", "generated_url_download_failed"}
        )
    ]

    results = []
    for shot in candidates:
        request = ImageGenerationRequest(
            aspect_presets=aspect_presets or [],
            reference_filenames=reference_filenames or [],
            visual_format=visual_format,
            panel_gutter_style=panel_gutter_style,
        )
        result = generate_shot_image(project_id, shot["shot_id"], request)
        results.append(result)
        if stop_on_error and result.get("status") == "failed":
            break

    return {
        "project_id": project_id,
        "requested": len(requested) if requested else "all",
        "processed": len(results),
        "done": len([item for item in results if item.get("status") in {"done", "generated"}]),
        "failed": len([item for item in results if item.get("status") == "failed"]),
        "results": results,
    }


def save_reference_image(project_id: str, filename: str, content: bytes) -> dict:
    require_project(project_id)
    if not content:
        raise ValueError("Reference image is empty.")
    if len(content) > MAX_REFERENCE_BYTES:
        raise ValueError("Reference image exceeds the 20MB limit.")
    original_name = Path(filename).name
    if not original_name:
        raise ValueError("Reference filename is missing.")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image_format = str(image.format or "").upper()
            image.verify()
    except (OSError, ValueError) as exc:
        raise ValueError("Reference upload is not a valid supported image.") from exc
    extension = REFERENCE_FORMAT_EXTENSIONS.get(image_format)
    if not extension:
        raise ValueError("Reference image must be PNG, JPEG, or WebP.")
    safe_stem = re.sub(r"[^\w.-]+", "-", Path(original_name).stem, flags=re.UNICODE).strip(".-")
    safe_stem = safe_stem[:100] or "reference"
    output_dir = get_project_reference_dir(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{safe_stem}{extension}"
    if (output_dir / safe_name).exists():
        safe_name = f"{safe_stem}-{_generation_stamp()}{extension}"
    output_path = output_dir / safe_name
    output_path.write_bytes(content)
    return {
        "filename": safe_name,
        "path": to_project_relative_path(project_id, output_path),
        "url": project_file_url(project_id, "references", safe_name),
    }


def delete_reference_image(project_id: str, filename: str) -> dict:
    require_project(project_id)
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        raise ValueError("Invalid reference filename.")
    path = get_project_reference_dir(project_id) / safe_name
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Reference image not found: {safe_name}")
    from backend.app.services.project_service import get_project_workspace, save_project_workspace

    workspace = get_project_workspace(project_id)
    selected = workspace.get("selected_reference_filenames") or []
    if safe_name in selected:
        workspace["selected_reference_filenames"] = [
            item for item in selected if item != safe_name
        ]
        save_project_workspace(project_id, workspace)
    bible = get_project_bible(project_id)
    if bible.get("style_reference_filename") == safe_name:
        save_project_bible(
            project_id,
            {
                **bible,
                "style_reference_filename": "",
                "visual_continuity_lock": "",
                "visual_anchor_shot_id": "",
                "visual_anchor_metrics": {},
            },
        )
    path.unlink()
    metadata = _read_reference_metadata(project_id)
    if safe_name in metadata:
        metadata.pop(safe_name, None)
        _write_reference_metadata(project_id, metadata)
    return {"filename": safe_name, "deleted": True, "dependencies_updated": True}


def list_reference_images(project_id: str) -> list[dict]:
    require_project(project_id)
    directory = get_project_reference_dir(project_id)
    if not directory.exists():
        return []
    metadata = _read_reference_metadata(project_id)
    return [
        {
            "filename": path.name,
            "path": to_project_relative_path(project_id, path),
            "url": project_file_url(project_id, "references", path.name),
            "category": _reference_category_from_filename(path.name),
            **metadata.get(path.name, {}),
        }
        for path in sorted(directory.iterdir())
        if path.is_file()
    ]


def _reference_metadata_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "metadata" / "reference_assets.json"


def _read_reference_metadata(project_id: str) -> dict:
    path = _reference_metadata_path(project_id)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_reference_metadata(project_id: str, metadata: dict) -> None:
    path = _reference_metadata_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _record_reference_metadata(project_id: str, references: list[dict]) -> None:
    if not references:
        return
    metadata = _read_reference_metadata(project_id)
    for reference in references:
        metadata[reference["filename"]] = {
            key: reference.get(key, "")
            for key in ("category", "name", "purpose", "asset_id")
            if reference.get(key)
        }
    _write_reference_metadata(project_id, metadata)


def _reference_category_from_filename(filename: str) -> str:
    lower = filename.lower()
    if "supporting_characters" in lower:
        return "supporting_characters"
    if "main_characters" in lower or "character" in lower:
        return "main_characters"
    if "location" in lower or "scene" in lower:
        return "locations"
    if "prop" in lower:
        return "props"
    if "style" in lower:
        return "style"
    return ""


def _flattened_pixels(image: Image.Image) -> list:
    getter = getattr(image, "get_flattened_data", None)
    return list(getter() if getter else image.getdata())


def _image_style_metrics(path: Path) -> dict:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((384, 384), Image.Resampling.LANCZOS)
        pixels = _flattened_pixels(image)
        if not pixels:
            return {}
        sample_step = max(1, len(pixels) // 6000)
        sampled = pixels[::sample_step]
        avg = tuple(round(sum(pixel[index] for pixel in sampled) / len(sampled)) for index in range(3))
        grayscale = image.convert("L")
        gray_pixels = _flattened_pixels(grayscale)[::sample_step]
        brightness = round(sum(gray_pixels) / len(gray_pixels), 1)
        contrast = round(
            (sum((value - brightness) ** 2 for value in gray_pixels) / len(gray_pixels)) ** 0.5,
            1,
        )
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_pixels = _flattened_pixels(edges)[::sample_step]
        edge_density = round(sum(1 for value in edge_pixels if value > 32) / len(edge_pixels), 3)
        unique_colors = len({(r // 32, g // 32, b // 32) for r, g, b in sampled})
        saturation_values = []
        for r, g, b in sampled:
            high = max(r, g, b)
            low = min(r, g, b)
            saturation_values.append(0 if high == 0 else (high - low) / high)
        saturation = round(sum(saturation_values) / len(saturation_values), 3)
        return {
            "average_rgb": avg,
            "brightness": brightness,
            "contrast": contrast,
            "edge_density": edge_density,
            "color_bucket_count": unique_colors,
            "saturation": saturation,
            "width": image.width,
            "height": image.height,
        }


def _local_style_analysis_prompt(metrics: dict) -> str:
    saturation = metrics.get("saturation", 0)
    edge_density = metrics.get("edge_density", 0)
    contrast = metrics.get("contrast", 0)
    palette = "limited or muted color palette" if saturation < 0.25 else "clear color palette"
    if saturation > 0.48:
        palette = "vivid saturated color palette"
    linework = "sparse soft edges"
    if edge_density > 0.22:
        linework = "dense visible linework and strong contour structure"
    elif edge_density > 0.12:
        linework = "clean readable linework"
    lighting = "soft low-contrast tonal structure"
    if contrast > 58:
        lighting = "high-contrast light and shadow"
    elif contrast > 36:
        lighting = "moderate contrast with clear value separation"
    return (
        f"{palette}, {linework}, {lighting}, average RGB {metrics.get('average_rgb')}, "
        f"brightness {metrics.get('brightness')}, contrast {metrics.get('contrast')}, "
        f"saturation {metrics.get('saturation')}, edge density {metrics.get('edge_density')}. "
        "Preserve these style traits as reusable rendering rules rather than copying the exact image content."
    )


def _parse_style_json(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def analyze_reference_style(
    project_id: str,
    reference_filename: str,
    apply_to_bible: bool = True,
    as_visual_anchor: bool = False,
) -> dict:
    require_project(project_id)
    reference_path = get_project_reference_dir(project_id) / Path(reference_filename).name
    if not reference_path.exists() or not reference_path.is_file():
        raise FileNotFoundError(f"Reference image not found: {reference_filename}")

    metrics = _image_style_metrics(reference_path)
    local_analysis = _local_style_analysis_prompt(metrics)
    if is_offline_mode():
        ai_result = {"ok": False, "error": "offline_mode"}
    else:
        settings = get_active_settings(include_secret=True)
        text_config = get_text_api_config(settings)
        image_b64 = base64.b64encode(reference_path.read_bytes()).decode("ascii")
        mime_type = mimetypes.guess_type(reference_path.name)[0] or "image/png"
        ai_result = generate_text_with_image(
            text_config,
            system_prompt=(
                "You are a production art director extracting a reusable style guide from a user-owned reference image. "
                "Do not identify or imitate living artists or copyrighted franchises. Extract visual rules only."
            ),
            user_prompt=(
                "Analyze this reference image as a reusable custom visual style for storyboard image generation. "
                "Return only JSON with keys: style_prompt, brushwork, linework, color_palette, value_structure, "
                "composition, texture, exposure_target, color_temperature, rendering_density, "
                "panel_border_color, panel_border_thickness, gutter_color, gutter_width, "
                "typography_or_symbol_logic, do_rules, avoid_rules. "
                "style_prompt must be one concise English prompt under 900 characters, strict enough to apply to new images. "
                "Describe border thickness relative to a 1024px canvas and explicitly state whether the image is framed or seamless. "
                f"Local measured image metrics: {json.dumps(metrics, ensure_ascii=False)}"
            ),
            image_b64=image_b64,
            mime_type=mime_type,
            temperature=0.1,
        )
    parsed = _parse_style_json(ai_result.get("text", "")) if ai_result.get("ok") else None
    if parsed and parsed.get("style_prompt"):
        style_prompt = str(parsed.get("style_prompt", "")).strip()
        analysis_parts = [
            f"Brushwork: {parsed.get('brushwork', '')}",
            f"Linework: {parsed.get('linework', '')}",
            f"Color palette: {parsed.get('color_palette', '')}",
            f"Value structure: {parsed.get('value_structure', '')}",
            f"Composition: {parsed.get('composition', '')}",
            f"Texture: {parsed.get('texture', '')}",
            f"Exposure target: {parsed.get('exposure_target', '')}",
            f"Color temperature: {parsed.get('color_temperature', '')}",
            f"Rendering density: {parsed.get('rendering_density', '')}",
            f"Panel border: {parsed.get('panel_border_color', '')}; {parsed.get('panel_border_thickness', '')}",
            f"Gutter: {parsed.get('gutter_color', '')}; {parsed.get('gutter_width', '')}",
            f"Typography/symbol logic: {parsed.get('typography_or_symbol_logic', '')}",
            f"Do: {parsed.get('do_rules', '')}",
            f"Avoid: {parsed.get('avoid_rules', '')}",
            f"Measured metrics: {local_analysis}",
        ]
        source = "ai_vision"
    else:
        style_prompt = local_analysis
        analysis_parts = [
            "AI vision analysis was unavailable or did not return parseable JSON.",
            f"Measured style extraction: {local_analysis}",
        ]
        source = "local_metrics"

    style_lock = (
        "custom reference-derived style, "
        f"{style_prompt} Strictly preserve brushwork, color structure, value rhythm, texture, "
        "line quality, and composition logic from the selected reference; do not copy exact content."
    )
    if parsed:
        continuity_lock = " ".join(
            part
            for part in [
                f"Exposure/value baseline: {parsed.get('exposure_target', '')}.",
                f"Color temperature: {parsed.get('color_temperature', '')}.",
                f"Rendering density: {parsed.get('rendering_density', '')}.",
                f"Linework: {parsed.get('linework', '')}.",
                f"Panel borders: {parsed.get('panel_border_color', '')}; {parsed.get('panel_border_thickness', '')}.",
                f"Gutters: {parsed.get('gutter_color', '')}; {parsed.get('gutter_width', '')}.",
                f"Palette: {parsed.get('color_palette', '')}.",
            ]
            if not part.endswith(": .") and not part.endswith(": ; .")
        )
    else:
        continuity_lock = (
            f"Measured master-image rendering baseline: {local_analysis} "
            "Use one unchanged project-wide line-weight system and one unchanged framed/seamless panel system."
        )
    bible = get_project_bible(project_id)
    next_bible = {
        **bible,
        "visual_style": style_lock,
        "style_analysis": "\n".join(part for part in analysis_parts if part.strip()),
        "style_reference_filename": reference_path.name,
        **(
            {
                "visual_continuity_lock": continuity_lock,
                "visual_anchor_metrics": metrics,
            }
            if as_visual_anchor
            else {}
        ),
    }
    if apply_to_bible:
        save_project_bible(project_id, next_bible)
    return {
        "project_id": project_id,
        "reference": {
            "filename": reference_path.name,
            "path": to_project_relative_path(project_id, reference_path),
            "url": project_file_url(project_id, "references", reference_path.name),
        },
        "source": source,
        "applied": apply_to_bible,
        "style_prompt": style_lock,
        "style_analysis": next_bible["style_analysis"],
        "visual_continuity_lock": continuity_lock,
        "metrics": metrics,
        "ai_error": "" if ai_result.get("ok") else ai_result.get("error", ""),
        "raw_text": ai_result.get("text", ""),
    }


def set_shot_visual_anchor(project_id: str, shot_id: str) -> dict:
    require_project(project_id)
    shot = get_shot(project_id, shot_id)
    if not shot:
        raise FileNotFoundError(f"Shot not found: {shot_id}")
    output_path = str(shot.get("output_path") or "")
    if not output_path:
        raise ValueError("The panel must have a locally saved selected image before it can become the visual master.")
    source_path = resolve_project_path(project_id, output_path)
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError("The selected panel image is missing from local storage.")

    previous_bible = get_project_bible(project_id)
    previous_anchor = str(previous_bible.get("style_reference_filename") or "")
    reference = save_reference_image(
        project_id,
        f"visual-anchor-{shot_id}{source_path.suffix or '.png'}",
        source_path.read_bytes(),
    )
    analysis = analyze_reference_style(
        project_id,
        reference_filename=reference["filename"],
        apply_to_bible=True,
        as_visual_anchor=True,
    )
    next_bible = {
        **get_project_bible(project_id),
        "visual_anchor_shot_id": shot_id,
        "visual_anchor_metrics": analysis.get("metrics") or {},
    }
    saved_bible = save_project_bible(project_id, next_bible)
    if previous_anchor.startswith("visual-anchor-") and previous_anchor != reference["filename"]:
        try:
            delete_reference_image(project_id, previous_anchor)
        except (FileNotFoundError, OSError, ValueError):
            pass
    return {
        **analysis,
        "shot_id": shot_id,
        "scene_id": shot.get("scene_id", ""),
        "reference": reference,
        "bible": saved_bible,
    }


def plan_reference_assets(
    project_id: str,
    script: str = "",
    categories: list[str] | None = None,
    refinement_prompt: str = "",
) -> dict:
    require_project(project_id)
    if is_offline_mode():
        return {"ok": False, "error": "offline_mode", "error_message": "Cloud AI is unavailable in offline mode.", "plan": []}
    settings = get_active_settings(include_secret=True)
    errors = validate_text_settings(settings)
    if errors:
        return {"ok": False, "error": "configuration_error", "error_message": " ".join(errors), "plan": []}
    bible = get_project_bible(project_id)
    requested = categories or ["main_characters", "supporting_characters", "locations", "props"]
    response = generate_text(
        get_text_api_config(settings),
        system_prompt=(
            "You are a production asset planner for manga and animation. Return only valid JSON with an assets array. "
            "Each asset must have asset_id, category, name, purpose, image_prompt. Allowed categories: "
            "character_turnaround, character_expression_action, supporting_character, location, prop, style. "
            "Display name and purpose in the source script language. image_prompt may be English."
        ),
        user_prompt=(
            f"Requested groups: {json.dumps(requested, ensure_ascii=False)}\n"
            f"Project bible: {json.dumps(bible, ensure_ascii=False)}\n"
            f"Script: {script[:12000]}\n"
            f"User refinement: {refinement_prompt}\n\n"
            "Choose only assets that materially improve visual continuity, with 1 to 8 images total. "
            "For each core named character, normally plan a clean turnaround/model sheet and, when useful, a separate expression/action sheet. "
            "Plan important locations as clean reusable environment references and recurring props as isolated object references. "
            "Do not plan narrative storyboards, sequential scenes, poster art, or mixed story collages. "
            "Every image_prompt must state that this is a production reference asset, use a neutral readable layout, no story sequence, no captions, and no readable text."
        ),
        temperature=0.1,
        max_output_tokens=1800,
    )
    if not response.get("ok"):
        return {
            "ok": False,
            "error": response.get("error", "asset_plan_failed"),
            "error_message": response.get("exception_message") or "Asset planning request failed.",
            "plan": [],
        }
    parsed = _parse_style_json(response.get("text", ""))
    raw_assets = parsed.get("assets") if isinstance(parsed, dict) else None
    allowed = {
        "character_turnaround",
        "character_expression_action",
        "supporting_character",
        "location",
        "prop",
        "style",
    }
    requested_allowed: set[str] = set()
    request_map = {
        "main_characters": {"character_turnaround", "character_expression_action"},
        "supporting_characters": {"supporting_character"},
        "locations": {"location"},
        "props": {"prop"},
        "style": {"style"},
    }
    for group in requested:
        requested_allowed.update(request_map.get(group, set()))
    plan: list[dict] = []
    for index, item in enumerate(raw_assets if isinstance(raw_assets, list) else [], 1):
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        name = str(item.get("name") or "").strip()
        prompt = str(item.get("image_prompt") or "").strip()
        if category not in allowed or category not in requested_allowed or not name or not prompt:
            continue
        asset_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(item.get("asset_id") or f"asset-{index}")).strip("-")
        plan.append(
            {
                "asset_id": (asset_id or f"asset-{index}")[:80],
                "category": category,
                "name": name[:120],
                "purpose": str(item.get("purpose") or "").strip()[:500],
                "image_prompt": prompt[:5000],
            }
        )
        if len(plan) >= 8:
            break
    if not plan:
        return {"ok": False, "error": "invalid_asset_plan", "error_message": "Text model did not return a usable asset plan.", "plan": []}
    return {
        "ok": True,
        "source": "ai",
        "provider": get_text_api_config(settings).get("provider", ""),
        "model": get_text_api_config(settings).get("model", ""),
        "plan": plan,
        "count": len(plan),
        "concurrency": 2,
    }


def generate_reference_concepts(
    project_id: str,
    script: str = "",
    categories: list[str] | None = None,
    refinement_prompt: str = "",
    plan: list[dict] | None = None,
    progress_callback=None,
) -> dict:
    require_project(project_id)
    if is_offline_mode():
        return {
            "project_id": project_id,
            "status": "blocked",
            "references": [],
            "errors": ["Cloud reference generation is unavailable in offline mode."],
            "error": "offline_mode",
            "error_message": "Cloud reference generation is unavailable in offline mode.",
        }
    settings = get_active_settings(include_secret=True)
    config_errors = validate_api_settings(settings)
    if config_errors:
        return {
            "project_id": project_id,
            "status": "failed",
            "error": "configuration_error",
            "error_message": " ".join(config_errors),
            "references": [],
        }

    bible = get_project_bible(project_id)
    categories = categories or ["main_characters", "supporting_characters", "locations", "props"]
    output_dir = get_project_reference_dir(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    prompts = _reference_concept_prompts(bible, script, refinement_prompt)
    references: list[dict] = []
    errors: list[str] = []

    def generate_category(category: str, prompt: str, plan_item: dict | None = None) -> tuple[dict | None, str]:
        asset_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str((plan_item or {}).get("asset_id") or category)).strip("-")
        filename = f"project-reference-{category}-{asset_id}-{_generation_stamp()}.png"
        output_path = output_dir / filename
        result = _bounded_generate_image(
            settings,
            prompt=prompt,
            size="1024x1024",
            quality=settings.get("image_quality", "low"),
            output_path=output_path,
        )
        if result.get("ok") and result.get("output_path"):
            return (
                {
                    "filename": filename,
                    "path": to_project_relative_path(project_id, output_path),
                    "url": project_file_url(project_id, "references", filename),
                    "category": category,
                    "name": (plan_item or {}).get("name", category),
                    "purpose": (plan_item or {}).get("purpose", ""),
                    "asset_id": (plan_item or {}).get("asset_id", asset_id),
                },
                "",
            )
        detail = (
            result.get("error_message")
            or result.get("error")
            or result.get("short_error")
            or result.get("error_code")
            or category
        )
        _log_failure(
            project_id,
            {
                "timestamp": utc_now(),
                "project_id": project_id,
                "shot_id": f"reference-{category}",
                "prompt": prompt,
                "endpoint": result.get("endpoint", ""),
                "model": result.get("model", ""),
                "status_code": result.get("status_code", ""),
                "error_type": result.get("error_type", ""),
                "error_code": result.get("provider_error_code") or result.get("error_code", ""),
                "short_error": result.get("error_code", ""),
                "error_message": detail,
                "exception_type": result.get("exception_type", ""),
                "exception_message": result.get("exception_message", ""),
                "raw_response": result.get("raw_response", ""),
            },
        )
        return None, f"{category}: {detail}"

    work = (
        [
            (str(item.get("category") or "asset"), str(item.get("image_prompt") or ""), item)
            for item in (plan or [])
            if item.get("image_prompt")
        ]
        if plan
        else [(category, prompts.get(category), None) for category in categories if prompts.get(category)]
    )
    if progress_callback:
        progress_callback(completed=0, failed=0, total=len(work), current="")
    with ThreadPoolExecutor(max_workers=min(2, max(1, len(work)))) as executor:
        futures = {
            executor.submit(generate_category, category, prompt, item): item or {"name": category}
            for category, prompt, item in work
        }
        completed = 0
        failed = 0
        for future in as_completed(futures):
            reference, error = future.result()
            if reference:
                references.append(reference)
            if error:
                errors.append(error)
                failed += 1
            completed += 1
            if progress_callback:
                progress_callback(
                    completed=completed,
                    failed=failed,
                    total=len(work),
                    current=str(futures[future].get("name") or ""),
                )
    order = {str(item.get("asset_id")): index for index, item in enumerate(plan or [])}
    if plan:
        references.sort(key=lambda item: order.get(str(item.get("asset_id")), len(order)))
    else:
        references.sort(key=lambda item: categories.index(item["category"]))
    _record_reference_metadata(project_id, references)

    return {
        "project_id": project_id,
        "status": "done" if references and not errors else "partial" if references else "failed",
        "references": references,
        "errors": errors,
        "error": "" if references else "reference_generation_failed",
        "error_message": "" if references else "; ".join(errors),
        "planned": len(work),
        "completed": len(references),
        "failed": len(errors),
    }


def _reference_concept_prompts(
    bible: dict,
    script: str,
    refinement_prompt: str = "",
) -> dict[str, str]:
    style = bible.get("visual_style") or (
        "black and white manga storyboard, clean line art, expressive faces, "
        "cinematic panel composition"
    )
    style_lock = (
        "STYLE LOCK - mandatory: use exactly this visual style and no other preset: "
        f"{style}. "
    )
    characters = bible.get("characters") or "main and supporting characters from the script"
    locations = bible.get("locations") or "main story locations from the script"
    props = bible.get("props") or "recurring props and costume details from the script"
    world = bible.get("world_notes") or script[:1200]
    prefix = bible.get("prompt_prefix") or "consistent manga production reference sheet"
    negative = bible.get("negative_prompt") or "watermark, random text, logo, bad anatomy, low quality"
    refinement = f"User refinement request: {refinement_prompt}. " if refinement_prompt else ""
    return {
        "main_characters": (
            f"{prefix}, character design reference sheet. {style_lock}"
            f"{refinement}Create clear full-body, half-body, and face references for the core protagonist characters only. "
            f"Keep every character separated and visually readable. "
            f"Character notes: {characters}. Story context: {world}. No speech bubbles, no labels. "
            f"Negative prompt: {negative}"
        ),
        "supporting_characters": (
            f"{prefix}, supporting character design reference sheet. {style_lock}"
            f"{refinement}Create clear reusable references for important supporting characters and recurring groups. "
            f"Character notes: {characters}. Story context: {world}. No speech bubbles, no labels. "
            f"Negative prompt: {negative}"
        ),
        "locations": (
            f"{prefix}, environment reference sheet. {style_lock}"
            f"{refinement}Create reusable establishing views for key locations and lighting mood. "
            f"Location notes: {locations}. Story context: {world}. No text, no labels. "
            f"Negative prompt: {negative}"
        ),
        "props": (
            f"{prefix}, prop and object reference sheet. {style_lock}"
            f"{refinement}Create clear references for recurring symbolic objects, tools, devices, costume details, "
            f"and visual motifs from the story. Prop notes: {props}. Character notes: {characters}. Story context: {world}. "
            f"No text, no labels. Negative prompt: {negative}"
        ),
        "style": (
            f"{prefix}, visual style reference sheet. {style_lock}"
            f"{refinement}Create a reusable style guide image showing line weight, shading, panel mood, "
            f"lighting, background density, and rendering rules without copying any living artist or copyrighted franchise. "
            f"Story context: {world}. No text, no labels. Negative prompt: {negative}"
        ),
    }
