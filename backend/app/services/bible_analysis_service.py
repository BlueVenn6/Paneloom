import json
import re
import sys
from pathlib import Path
from typing import Any

from backend.app.config import get_active_settings, get_text_api_config, is_offline_mode, validate_text_settings
from backend.app.services.project_service import get_project_bible
from backend.app.services.shotlist_service import list_shots

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.openai_text_client import generate_text  # noqa: E402


SYSTEM_PROMPT = """You analyze scripts for manga image generation consistency.
Return only valid JSON with these string fields:
visual_style, characters, locations, props, world_notes, prompt_prefix, negative_prompt.
Write practical production notes that can be pasted directly into editable UI fields.
Characters must include stable names/roles if known, age impression, silhouette, face/hair,
costume palette, key props, personality acting cues, and consistency anchors.
Locations must include reusable environments, lighting, era, props/signage rules, and mood.
Prompt prefix must be a compact generation directive that reinforces character continuity,
panel readability, selected style, and no readable text.
Focus on repeatable character appearance, props, locations, style rules, and continuity.
Write in the same main language as the source material when possible.
Do not invent excessive lore if the script does not support it."""


def analyze_project_bible(
    project_id: str,
    script: str = "",
    use_ai: bool = True,
    replace_existing: bool = False,
) -> dict[str, Any]:
    current_bible = get_project_bible(project_id)
    analysis_bible = (
        {
            "visual_style": current_bible.get("visual_style", ""),
            "negative_prompt": current_bible.get("negative_prompt", ""),
        }
        if replace_existing
        else current_bible
    )
    shots = list_shots(project_id)
    source_text = _build_source_text(script, [] if script.strip() else shots)
    warnings: list[str] = []

    if use_ai and not is_offline_mode():
        settings = get_active_settings(include_secret=True)
        errors = validate_text_settings(settings)
        if not errors and source_text.strip():
            ai_bible = _analyze_with_ai(get_text_api_config(settings), analysis_bible, source_text)
            if ai_bible["bible"]:
                return {
                    "ok": True,
                    "source": "ai",
                    "warnings": ai_bible["warnings"],
                    "bible": {**analysis_bible, **ai_bible["bible"]},
                }
            warnings.extend(ai_bible["warnings"])
        elif errors:
            warnings.append("Text model was skipped because API settings are incomplete.")

    if use_ai:
        if is_offline_mode():
            message = "Cloud AI is unavailable in offline mode."
            error = "offline_mode"
        elif warnings:
            message = " ".join(warnings)
            error = "text_generation_failed"
        else:
            message = "Text model settings are incomplete or the script is empty."
            error = "configuration_error"
        return {
            "ok": False,
            "source": "ai",
            "warnings": warnings,
            "error": error,
            "error_message": message,
            "bible": {},
        }
    local_bible = _analyze_locally(analysis_bible, source_text)
    return {
        "ok": True,
        "source": "local",
        "warnings": warnings,
        "bible": {**analysis_bible, **local_bible},
    }


def _build_source_text(script: str, shots: list[dict]) -> str:
    parts = [script.strip()]
    for index, shot in enumerate(shots[:80], 1):
        prompt = str(shot.get("prompt") or "").strip()
        visual = str(shot.get("visual_description") or "").strip()
        notes = str(shot.get("revision_notes") or "").strip()
        if prompt or visual or notes:
            parts.append(f"Panel {index}: {visual}\nPrompt: {prompt}\nNotes: {notes}")
    return "\n\n".join(part for part in parts if part)


def _analyze_with_ai(settings: dict[str, Any], current_bible: dict, source_text: str) -> dict[str, Any]:
    user_prompt = f"""
Current editable project bible:
{json.dumps(current_bible, ensure_ascii=False)}

Script and storyboard material:
{source_text[:18000]}

Create a practical manga production bible. Characters should include stable
appearance descriptors, age range if known, costume, personality cues, and any
recurring props. Locations should list reusable environments. Prompt prefix
should be a compact style/continuity prefix for image generation.
Do not leave vague placeholders. If names are unknown, describe roles as reusable
anchors, such as protagonist, boss, clerk, crowd, recurring prop, or key location.
"""
    result = generate_text(
        settings,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.2,
    )
    if not result.get("ok"):
        return {"bible": {}, "warnings": [result.get("error", "text_generation_failed")]}

    parsed = _parse_json_object(result.get("text", ""))
    if not parsed:
        return {"bible": {}, "warnings": ["AI response was not valid project bible JSON."]}

    allowed = {
        "visual_style",
        "characters",
        "locations",
        "props",
        "world_notes",
        "prompt_prefix",
        "negative_prompt",
    }
    bible = {
        key: str(value).strip()
        for key, value in parsed.items()
        if key in allowed and value is not None and str(value).strip()
    }
    return {"bible": bible, "warnings": []}


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


def _analyze_locally(current_bible: dict, source_text: str) -> dict:
    cleaned = re.sub(r"\s+", " ", source_text).strip()
    sentences = [item.strip() for item in re.split(r"(?<=[。！？!?；;])", cleaned) if item.strip()]
    character_hints = _extract_after_keywords(cleaned, ["主角", "角色", "人物", "少女", "少年", "男人", "女人"])
    location_hints = _extract_after_keywords(cleaned, ["城市", "房间", "学校", "街道", "星球", "森林", "办公室", "宫殿"])
    summary = " ".join(sentences[:4])[:900]
    return {
        "visual_style": current_bible.get("visual_style")
        or (
            "black and white manga storyboard, clean line art, expressive faces, "
            "cinematic panel composition"
        ),
        "characters": current_bible.get("characters")
        or _local_character_notes(character_hints, summary),
        "locations": current_bible.get("locations")
        or _local_location_notes(location_hints, summary),
        "props": current_bible.get("props")
        or "- 提取并固定会重复出现的关键道具、服装配件、标志物及其颜色、材质和携带者。",
        "world_notes": current_bible.get("world_notes") or summary,
        "prompt_prefix": current_bible.get("prompt_prefix")
        or (
            "consistent character design, stable hair/costume silhouettes, recurring props preserved, "
            "clear comic panel readability, no readable text, no speech bubbles unless explicitly requested"
        ),
        "negative_prompt": current_bible.get("negative_prompt")
        or "watermark, random text, speech bubble text, logo, distorted hands, bad anatomy, duplicated character, low quality",
    }


def _local_character_notes(character_hints: str, summary: str) -> str:
    if character_hints:
        return (
            f"{character_hints}\n"
            "- 为每个常驻角色固定：发型、脸型、年龄感、服装主色、随身道具、表情习惯和动作姿态。\n"
            "- 生成前请把主角、反派/上司、配角和群众角色分开描述，避免人物混淆。"
        )
    seed = summary[:220] or "当前剧本"
    return (
        f"- 主角/叙事核心：根据这段内容建立稳定外貌、服装、年龄感和情绪锚点：{seed}\n"
        "- 配角：按剧情功能拆分为对手、协助者、旁观者或群众；每类保留不同轮廓和服装色块。\n"
        "- 一致性锚点：固定发型、脸型、身高体态、常用道具、表情习惯，不要每格换造型。"
    )


def _local_location_notes(location_hints: str, summary: str) -> str:
    if location_hints:
        return (
            f"{location_hints}\n"
            "- 为每个场景固定：时代感、光线、主色、标志性道具、背景密度和可重复构图。"
        )
    seed = summary[:220] or "当前剧本"
    return (
        f"- 主要场景：从剧情内容提取并固定可重复环境：{seed}\n"
        "- 场景规则：保持光线方向、空间层次、道具位置和背景密度一致；招牌/界面只用图形，不写可读文字。"
    )


def _extract_after_keywords(text: str, keywords: list[str]) -> str:
    hits: list[str] = []
    for keyword in keywords:
        for match in re.finditer(keyword, text):
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 90)
            snippet = text[start:end].strip(" ，。；;")
            if snippet and snippet not in hits:
                hits.append(snippet)
            if len(hits) >= 6:
                break
    return "\n".join(f"- {hit}" for hit in hits[:6])
