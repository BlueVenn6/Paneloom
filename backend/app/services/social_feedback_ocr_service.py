import base64
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from backend.app.config import get_active_settings, get_text_api_config, is_offline_mode, validate_text_settings

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.openai_text_client import generate_text_with_image  # noqa: E402


SYSTEM_PROMPT = """Extract social media analytics from a screenshot.
Return only valid JSON. Do not invent missing numbers.
Fields:
content_id, platform, publish_date, snapshot_date, title, aspect_ratio, format,
views, likes, comments, saves, shares, completion_rate, conversions, revenue,
currency, judgment, notes.
Use numbers only for metric fields. completion_rate should be a percentage number.
judgment must be one of: great, good, average, poor, unknown."""
MAX_FEEDBACK_SCREENSHOT_BYTES = 10 * 1024 * 1024


def extract_social_feedback_from_image(
    *,
    filename: str,
    content: bytes,
    mime_type: str,
    platform: str = "",
    publish_date: str = "",
    content_id: str = "",
    use_ai: bool = True,
) -> dict[str, Any]:
    if not content:
        raise ValueError("Screenshot is empty.")
    if len(content) > MAX_FEEDBACK_SCREENSHOT_BYTES:
        raise ValueError("Screenshot exceeds the 10MB limit.")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except OSError as exc:
        raise ValueError("Uploaded feedback screenshot is not a valid image.") from exc
    settings = get_active_settings(include_secret=True)
    errors = validate_text_settings(settings)
    if not use_ai:
        return _empty_result("AI extraction is disabled.")
    if is_offline_mode():
        return _empty_result("Cloud AI is unavailable in offline mode; fill metrics manually.")
    if errors:
        return _empty_result("Text model settings are incomplete; fill metrics manually.")

    prompt = f"""
Screenshot filename: {filename}
Known platform: {platform or "-"}
Known publish_date: {publish_date or "-"}
Known content_id: {content_id or "-"}

Extract visible analytics and conversion/revenue information. If the screenshot
does not show conversion or revenue, keep those fields as 0. If the screenshot
date is visible, use it as snapshot_date; otherwise leave it empty.
"""
    result = generate_text_with_image(
        get_text_api_config(settings),
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt,
        image_b64=base64.b64encode(content).decode("ascii"),
        mime_type=mime_type or "image/png",
        temperature=0.1,
    )
    if not result.get("ok"):
        return _empty_result(result.get("error") or "Screenshot extraction failed.")
    parsed = _parse_json_object(result.get("text", ""))
    if not parsed:
        return _empty_result("The model did not return valid metric JSON.")
    normalized = _normalize_feedback(parsed)
    if platform and not normalized["platform"]:
        normalized["platform"] = platform
    if publish_date and not normalized["publish_date"]:
        normalized["publish_date"] = publish_date
    if content_id and not normalized["content_id"]:
        normalized["content_id"] = content_id
    return {"ok": True, "source": "ai", "feedback": normalized, "warnings": []}


def _empty_result(warning: str) -> dict[str, Any]:
    return {
        "ok": False,
        "source": "manual",
        "feedback": _normalize_feedback({}),
        "warnings": [warning],
    }


def _parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


def _normalize_feedback(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_id": str(data.get("content_id") or ""),
        "platform": str(data.get("platform") or ""),
        "publish_date": str(data.get("publish_date") or ""),
        "snapshot_date": str(data.get("snapshot_date") or ""),
        "title": str(data.get("title") or ""),
        "aspect_ratio": str(data.get("aspect_ratio") or ""),
        "format": str(data.get("format") or ""),
        "views": _safe_int(data.get("views")),
        "likes": _safe_int(data.get("likes")),
        "comments": _safe_int(data.get("comments")),
        "saves": _safe_int(data.get("saves")),
        "shares": _safe_int(data.get("shares")),
        "completion_rate": _safe_float(data.get("completion_rate")),
        "conversions": _safe_int(data.get("conversions")),
        "revenue": _safe_float(data.get("revenue")),
        "currency": str(data.get("currency") or "USD"),
        "judgment": _normalize_judgment(data.get("judgment")),
        "notes": str(data.get("notes") or ""),
    }


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "").replace("%", "").strip()))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _normalize_judgment(value: Any) -> str:
    text = str(value or "unknown").lower()
    return text if text in {"great", "good", "average", "poor", "unknown"} else "unknown"
