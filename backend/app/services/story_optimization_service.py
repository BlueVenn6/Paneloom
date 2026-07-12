import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.app.config import (
    get_active_settings,
    get_text_api_config,
    is_offline_mode,
    validate_text_settings,
)
from backend.app.models.schemas import StoryOptimizationRequest
from backend.app.services.language_service import is_output_language_compatible, normalize_output_language

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.openai_text_client import generate_text  # noqa: E402


SYSTEM_PROMPT = """You are a manga storyboard development editor.
Help the user improve a story before breaking it into panels.
Return only valid JSON with these fields:
logline, improved_script, recommended_panel_count, platform_recommendations,
storyboard_strategy, revision_suggestions, risks.
platform_recommendations, storyboard_strategy, and revision_suggestions must be arrays of strings.
risks must be an array of objects shaped as {"risk": "...", "solution": "..."}.
Keep the user's original intent and language. Do not mention copyrighted styles."""


def optimize_story(payload: StoryOptimizationRequest) -> dict[str, Any]:
    settings = get_active_settings(include_secret=True)
    errors = validate_text_settings(settings)
    offline = is_offline_mode()
    if not payload.use_ai:
        return _local_optimization(payload)
    if offline:
        return _ai_failure("offline_mode", "Cloud AI is unavailable in offline mode.")
    if errors:
        return _ai_failure("configuration_error", " ".join(errors))
    return _optimize_with_ai(get_text_api_config(settings), payload)


def _optimize_with_ai(settings: dict[str, Any], payload: StoryOptimizationRequest) -> dict[str, Any]:
    started = perf_counter()
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

    Output language: {payload.output_language or "the same main language as the original story"}.
    Rewrite the story rather than merely returning the original text.
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
        return _ai_failure(
            str(response.get("error") or "text_generation_failed"),
            str(response.get("exception_message") or "Text model request failed."),
        )
    parsed = _parse_json_object(response.get("text", ""))
    if not parsed:
        return _ai_failure("invalid_model_output", "Text model did not return valid optimization JSON.")
    improved_script = str(parsed.get("improved_script") or "").strip()
    if not improved_script:
        return _ai_failure(
            "missing_improved_script",
            "Text model response did not include an optimized script.",
        )
    if _normalized_text(improved_script) == _normalized_text(payload.script):
        return _ai_failure(
            "unchanged_model_output",
            "Text model returned the original script without an actual optimization.",
        )
    locale = normalize_output_language(payload.output_language, payload.script)
    user_visible = " ".join(
        [
            improved_script,
            str(parsed.get("logline") or ""),
            json.dumps(parsed.get("revision_suggestions") or [], ensure_ascii=False),
            json.dumps(parsed.get("risks") or [], ensure_ascii=False),
        ]
    )
    if not is_output_language_compatible(user_visible, locale):
        return _ai_failure(
            "output_language_mismatch",
            "Text model output did not match the selected interface language.",
        )
    result = _normalize_result(parsed, payload, source="ai", warnings=[])
    result.update(
        {
            "provider": settings.get("provider", ""),
            "model": settings.get("model", ""),
            "duration_seconds": round(perf_counter() - started, 2),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "input_sha256": hashlib.sha256(payload.script.encode("utf-8")).hexdigest(),
            "output_language": payload.output_language or "source",
        }
    )
    return result


def _ai_failure(error: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "source": "ai",
        "error": error,
        "error_message": message,
        "warnings": [],
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


def _normalize_result(
    data: dict[str, Any],
    payload: StoryOptimizationRequest,
    *,
    source: str,
    warnings: list[str],
) -> dict[str, Any]:
    panel_count = _safe_int(data.get("recommended_panel_count"), _recommended_panel_count(payload.script))
    ai_fallback: list[str] = []
    return {
        "ok": True,
        "source": source,
        "logline": str(data.get("logline") or _logline(payload.script)),
        "improved_script": str(data.get("improved_script") or payload.script),
        "recommended_panel_count": max(1, min(panel_count, 80)),
        "platform_recommendations": _as_list(
            data.get("platform_recommendations"),
            ai_fallback
            if source == "ai"
            else ["Reels/Shorts for vertical rhythm", "Pinterest for comic-grid saving"],
        ),
        "storyboard_strategy": _as_list(
            data.get("storyboard_strategy"),
            ai_fallback if source == "ai" else _local_strategy(payload.script),
        ),
        "revision_suggestions": _as_list(
            data.get("revision_suggestions"),
            ai_fallback if source == "ai" else _local_revision_suggestions(payload.script),
        ),
        "risks": _as_risk_list(
            data.get("risks"),
            []
            if source == "ai"
            else [
                {
                    "risk": "Character or prop continuity may drift between panels.",
                    "solution": "Lock reusable character, prop, and location references before generation.",
                }
            ],
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
                {
                    "risk": "Long abstract paragraphs are difficult to visualize.",
                    "solution": "Convert them into visible character actions and location changes.",
                },
                {
                    "risk": "Recurring visual elements may drift.",
                    "solution": "Lock character, prop, and location references first.",
                },
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


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _as_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip("-• ").strip() for line in value.splitlines() if line.strip()]
    return fallback


def _as_risk_list(value: Any, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    values = value if isinstance(value, list) else [value] if value else []
    normalized: list[dict[str, str]] = []
    for item in values:
        if isinstance(item, dict):
            risk = str(item.get("risk") or item.get("issue") or "").strip()
            solution = str(item.get("solution") or item.get("mitigation") or "").strip()
        else:
            risk = str(item or "").strip()
            solution = ""
        if risk:
            normalized.append({"risk": risk, "solution": solution})
    return normalized or fallback
