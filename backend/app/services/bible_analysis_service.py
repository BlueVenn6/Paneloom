import json
import re
import sys
from pathlib import Path
from typing import Any

from backend.app.config import get_active_settings, get_text_api_config, is_offline_mode, validate_text_settings
from backend.app.services.language_service import (
    is_output_language_compatible,
    normalize_output_language,
    output_language_name,
)
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
    output_language: str = "source",
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
    ai_error = ""

    if use_ai and not is_offline_mode():
        settings = get_active_settings(include_secret=True)
        errors = validate_text_settings(settings)
        if not errors and source_text.strip():
            ai_bible = _analyze_with_ai(
                get_text_api_config(settings),
                analysis_bible,
                source_text,
                output_language,
            )
            if ai_bible["bible"]:
                return {
                    "ok": True,
                    "source": "ai",
                    "warnings": ai_bible["warnings"],
                    "bible": {**analysis_bible, **ai_bible["bible"]},
                }
            warnings.extend(ai_bible["warnings"])
            ai_error = str(ai_bible.get("error") or "")
        elif errors:
            warnings.append("Text model was skipped because API settings are incomplete.")

    if use_ai:
        if is_offline_mode():
            message = "Cloud AI is unavailable in offline mode."
            error = "offline_mode"
        elif warnings:
            message = " ".join(warnings)
            error = ai_error or "text_generation_failed"
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
    local_bible = _analyze_locally(analysis_bible, source_text, output_language)
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


def _analyze_with_ai(
    settings: dict[str, Any],
    current_bible: dict,
    source_text: str,
    output_language: str = "source",
) -> dict[str, Any]:
    language_name = output_language_name(output_language, source_text)
    user_prompt = f"""
Current editable project bible:
{json.dumps(current_bible, ensure_ascii=False)}

Script and storyboard material:
{source_text[:18000]}

Required output language: {language_name}

Create a practical manga production bible. Characters should include stable
appearance descriptors, age range if known, costume, personality cues, and any
recurring props. Locations should list reusable environments. Prompt prefix
should be a compact style/continuity prefix for image generation.
Do not leave vague placeholders. If names are unknown, describe roles as reusable
anchors, such as protagonist, boss, clerk, crowd, recurring prop, or key location.
All JSON string values must use {language_name}. JSON key names remain unchanged.
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
    locale = normalize_output_language(output_language, source_text)
    if bible and not is_output_language_compatible(" ".join(bible.values()), locale):
        return {
            "bible": {},
            "warnings": ["AI Bible output language did not match the selected interface language."],
            "error": "output_language_mismatch",
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


def _analyze_locally(current_bible: dict, source_text: str, output_language: str = "source") -> dict:
    cleaned = re.sub(r"\s+", " ", source_text).strip()
    sentences = [item.strip() for item in re.split(r"(?<=[。！？!?；;])", cleaned) if item.strip()]
    character_hints = _extract_after_keywords(cleaned, ["主角", "角色", "人物", "少女", "少年", "男人", "女人"])
    location_hints = _extract_after_keywords(cleaned, ["城市", "房间", "学校", "街道", "星球", "森林", "办公室", "宫殿"])
    summary = " ".join(sentences[:4])[:900]
    locale = normalize_output_language(output_language, source_text)
    if locale == "en":
        prop_default = "- Fix every recurring prop, costume accessory, symbol, color, material, and owner."
        prompt_default = "consistent character design, stable hair and costume silhouettes, recurring props preserved, clear comic readability, no readable text"
        negative_default = "watermark, random text, speech bubble text, logo, distorted hands, bad anatomy, duplicated character, low quality"
    elif locale == "ja":
        prop_default = "- 繰り返し登場する小物、衣装、記号の色、素材、所有者を固定する。"
        prompt_default = "一貫したキャラクターデザイン、固定された髪型と衣装、小物の継続、読みやすい漫画構図、可読文字なし"
        negative_default = "透かし、ランダム文字、吹き出し文字、ロゴ、崩れた手、不自然な人体、重複人物、低品質"
    elif locale == "ko":
        prop_default = "- 반복 소품, 의상 장식, 상징의 색상과 재질 및 소유자를 고정하세요."
        prompt_default = "일관된 캐릭터 디자인, 고정된 헤어와 의상 실루엣, 반복 소품 유지, 읽기 쉬운 만화 구도, 글자 없음"
        negative_default = "워터마크, 무작위 글자, 말풍선 글자, 로고, 잘못된 손, 나쁜 해부학, 중복 인물, 저품질"
    elif locale == "zh-TW":
        prop_default = "- 提取並固定會重複出現的關鍵道具、服裝配件、標誌物及其顏色、材質和攜帶者。"
        prompt_default = "角色設計一致，髮型與服裝輪廓穩定，重複道具保持一致，漫畫構圖清晰，不出現可讀文字"
        negative_default = "浮水印，隨機文字，氣泡文字，標誌，手部畸形，人體結構錯誤，重複人物，低品質"
    else:
        prop_default = "- 提取并固定会重复出现的关键道具、服装配件、标志物及其颜色、材质和携带者。"
        prompt_default = "角色设计一致，发型与服装轮廓稳定，重复道具保持一致，漫画构图清晰，不出现可读文字"
        negative_default = "水印，随机文字，气泡文字，标志，手部畸形，人体结构错误，重复人物，低质量"
    return {
        "visual_style": current_bible.get("visual_style")
        or (
            "black and white manga storyboard, clean line art, expressive faces, "
            "cinematic panel composition"
        ),
        "characters": current_bible.get("characters")
        or _local_character_notes(character_hints, summary, locale),
        "locations": current_bible.get("locations")
        or _local_location_notes(location_hints, summary, locale),
        "props": current_bible.get("props")
        or prop_default,
        "world_notes": current_bible.get("world_notes") or summary,
        "prompt_prefix": current_bible.get("prompt_prefix")
        or prompt_default,
        "negative_prompt": current_bible.get("negative_prompt")
        or negative_default,
    }


def _local_character_notes(character_hints: str, summary: str, locale: str = "zh-CN") -> str:
    if locale == "zh-TW":
        seed = character_hints or summary[:220] or "目前劇本"
        return (
            f"- 角色基準：{seed}\n"
            "- 為每個常駐角色固定髮型、臉型、年齡感、服裝主色、體型、隨身道具和表演習慣。\n"
            "- 明確區分主角、對立角色、配角與群眾。"
        )
    if locale == "en":
        seed = character_hints or summary[:220] or "the current script"
        return (
            f"- Character anchors: {seed}\n"
            "- Fix hair, face shape, age impression, costume colors, body silhouette, recurring props, and acting cues for every recurring character.\n"
            "- Keep leads, opponents, supporting roles, and crowds visually distinct."
        )
    if locale == "ja":
        seed = character_hints or summary[:220] or "現在の脚本"
        return (
            f"- キャラクター基準：{seed}\n"
            "- 各レギュラーの髪型、顔、年齢感、衣装色、体型、小物、演技の癖を固定する。\n"
            "- 主役、対立役、脇役、群衆を明確に描き分ける。"
        )
    if locale == "ko":
        seed = character_hints or summary[:220] or "현재 대본"
        return (
            f"- 캐릭터 기준: {seed}\n"
            "- 모든 반복 등장인물의 머리, 얼굴형, 나이 인상, 의상 색상, 체형, 소품과 연기 습관을 고정하세요.\n"
            "- 주인공, 대립 인물, 조연과 군중을 명확히 구분하세요."
        )
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


def _local_location_notes(location_hints: str, summary: str, locale: str = "zh-CN") -> str:
    if locale == "zh-TW":
        seed = location_hints or summary[:220] or "目前劇本"
        return (
            f"- 可重複使用的場景：{seed}\n"
            "- 固定每個場景的時代、光線方向、主色、標誌性道具、空間配置與背景密度。"
        )
    if locale == "en":
        seed = location_hints or summary[:220] or "the current script"
        return (
            f"- Reusable locations: {seed}\n"
            "- Fix period, light direction, primary colors, landmark props, spatial layout, and background density for each location."
        )
    if locale == "ja":
        seed = location_hints or summary[:220] or "現在の脚本"
        return (
            f"- 再利用する場所：{seed}\n"
            "- 各場所の時代、光の方向、基調色、象徴的な小物、空間配置、背景密度を固定する。"
        )
    if locale == "ko":
        seed = location_hints or summary[:220] or "현재 대본"
        return (
            f"- 반복 장소: {seed}\n"
            "- 각 장소의 시대, 빛 방향, 주조색, 상징 소품, 공간 배치와 배경 밀도를 고정하세요."
        )
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
