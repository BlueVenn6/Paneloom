import json
import re
import sys
from pathlib import Path
from typing import Any

from backend.app.config import (
    get_active_settings,
    get_text_api_config,
    is_offline_mode,
    validate_text_settings,
)
from backend.app.models.schemas import StoryOptimizationRequest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.openai_text_client import generate_text  # noqa: E402


SYSTEM_PROMPT = """You are a manga storyboard development editor.
Help the user improve a story before breaking it into panels.
Return only valid JSON with these fields:
logline, improved_script, recommended_panel_count, platform_recommendations,
storyboard_strategy, revision_suggestions, risks.
Keep the user's original intent and language. Do not mention copyrighted styles."""


def optimize_story(payload: StoryOptimizationRequest) -> dict[str, Any]:
    settings = get_active_settings(include_secret=True)
    errors = validate_text_settings(settings)
    offline = is_offline_mode()
    if payload.use_ai and not offline and not errors:
        result = _optimize_with_ai(get_text_api_config(settings), payload)
        if result.get("ok"):
            return result

    fallback = _local_optimization(payload)
    if payload.use_ai and offline:
        fallback["warnings"].append("Cloud AI is unavailable in offline mode; local advice was used.")
    elif payload.use_ai and errors:
        fallback["warnings"].append("Text model settings are incomplete; local advice was used.")
    elif payload.use_ai:
        fallback["warnings"].append("Text model did not return usable JSON; local advice was used.")
    return fallback


def _optimize_with_ai(settings: dict[str, Any], payload: StoryOptimizationRequest) -> dict[str, Any]:
    platforms = ", ".join(payload.target_platforms) or "Reels, Shorts, Pinterest, Instagram"
    user_prompt = f"""
Original story:
{payload.script}

Goal:
{payload.goal or "Make it more suitable for manga storyboard generation."}

Visual style:
{payload.style}

Target platforms:
{platforms}

Please improve structure for manga panels. Recommend panel count, pacing,
opening hook, scene beats, image-generation risks, and suitable platforms.
"""
    response = generate_text(
        settings,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.35,
    )
    if not response.get("ok"):
        return {"ok": False}
    parsed = _parse_json_object(response.get("text", ""))
    if not parsed:
        return {"ok": False}
    return _normalize_result(parsed, payload, source="ai", warnings=[])


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


def _normalize_result(
    data: dict[str, Any],
    payload: StoryOptimizationRequest,
    *,
    source: str,
    warnings: list[str],
) -> dict[str, Any]:
    panel_count = _safe_int(data.get("recommended_panel_count"), _recommended_panel_count(payload.script))
    return {
        "ok": True,
        "source": source,
        "logline": str(data.get("logline") or _logline(payload.script)),
        "improved_script": str(data.get("improved_script") or payload.script),
        "recommended_panel_count": max(1, min(panel_count, 80)),
        "platform_recommendations": _as_list(
            data.get("platform_recommendations"),
            ["Reels/Shorts for vertical rhythm", "Pinterest for comic-grid saving"],
        ),
        "storyboard_strategy": _as_list(
            data.get("storyboard_strategy"),
            _local_strategy(payload.script),
        ),
        "revision_suggestions": _as_list(
            data.get("revision_suggestions"),
            _local_revision_suggestions(payload.script),
        ),
        "risks": _as_list(
            data.get("risks"),
            ["Keep character and prop references fixed before generating panels."],
        ),
        "warnings": warnings,
    }


def _local_optimization(payload: StoryOptimizationRequest) -> dict[str, Any]:
    return _normalize_result(
        {
            "logline": _logline(payload.script),
            "improved_script": payload.script.strip(),
            "recommended_panel_count": _recommended_panel_count(payload.script),
            "platform_recommendations": [
                "9:16 is suitable for narrated vertical comic videos.",
                "2:3 is suitable for Pinterest saves and serialized comic pins.",
                "1:1 or 4:5 is suitable for Instagram feed tests.",
            ],
            "storyboard_strategy": _local_strategy(payload.script),
            "revision_suggestions": _local_revision_suggestions(payload.script),
            "risks": [
                "Long abstract paragraphs should be converted into visible actions.",
                "Recurring characters, props, and locations should be locked as references first.",
            ],
        },
        payload,
        source="local",
        warnings=[],
    )


def _recommended_panel_count(script: str) -> int:
    sentence_count = len([part for part in re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+", script) if part.strip()])
    paragraph_count = len([part for part in re.split(r"\n\s*\n", script) if part.strip()])
    return max(4, min(24, max(sentence_count, paragraph_count * 2)))


def _local_strategy(script: str) -> list[str]:
    return [
        "Start with one establishing panel that makes the world rule visible.",
        "Use close-ups for emotional turns instead of placing long explanation in one panel.",
        "Separate action, reaction, and consequence into different panels.",
        "End the sequence with a clear visual hook for the next post or narration beat.",
    ]


def _local_revision_suggestions(script: str) -> list[str]:
    suggestions = [
        "Replace abstract exposition with concrete locations, gestures, props, and light changes.",
        "Mark the protagonist, supporting characters, recurring props, and locations before generating panels.",
    ]
    if len(script) > 1200:
        suggestions.append("Split the story into episodes before image generation to avoid overloaded prompts.")
    return suggestions


def _logline(script: str) -> str:
    cleaned = re.sub(r"\s+", " ", script).strip()
    return cleaned[:160]


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip("-• ").strip() for line in value.splitlines() if line.strip()]
    return fallback
