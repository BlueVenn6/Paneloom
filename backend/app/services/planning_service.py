import json
import re
import sys
from pathlib import Path
from typing import Any

from backend.app.config import get_active_settings, get_text_api_config, is_offline_mode, validate_text_settings
from backend.app.models.schemas import ScriptBreakdownRequest, ShotCreate, ShotRewriteRequest
from backend.app.services.language_service import (
    is_output_language_compatible,
    normalize_output_language,
    output_language_name,
)
from backend.app.services.project_service import require_project
from backend.app.services.shotlist_service import list_shots, update_shot

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.openai_text_client import generate_text  # noqa: E402


SYSTEM_PROMPT = """You are a senior manga storyboard director.
Design panels from the full story logic, not by mechanically splitting text.
Return only valid JSON with a top-level "shots" array.
Each shot must include: scene_id, visual_description, prompt, negative_prompt,
revision_notes.

Rules:
- Use exactly the requested output language for visual_description, prompt,
  negative_prompt, and revision_notes.
- Build a clear beat sequence: hook, setup, escalation, turn, reveal, payoff.
- Each panel must show one visual moment with a specific subject, action, emotion,
  camera distance, composition, and continuity notes.
- If the requested visual format is webtoon_strip, each output image prompt must describe
  a vertical mini strip with 3 to 5 stacked comic beats inside one image.
- If the requested visual format is single_panel, each output image prompt must describe
  one cinematic comic panel only and must not ask for a collage.
- Keep visual_description concise and readable.
- Keep prompt concrete and image-focused; do not paste long script passages.
- Put dialogue, narration, platform notes, and continuity reminders in revision_notes.
- Do not draw random text, captions, subtitles, speech bubbles, or video editing instructions."""


def breakdown_script(payload: ScriptBreakdownRequest) -> dict[str, Any]:
    settings = get_active_settings(include_secret=True)
    errors = validate_text_settings(settings)
    offline = is_offline_mode()
    if not payload.use_ai:
        return {"ok": True, "source": "local", "shots": _breakdown_locally(payload), "warnings": []}
    ai_error = ""
    if not offline and not errors:
        ai_result = _breakdown_with_ai(get_text_api_config(settings), payload)
        if ai_result["shots"]:
            return {
                "ok": True,
                "source": "ai",
                "shots": ai_result["shots"],
                "warnings": ai_result["warnings"],
            }
        ai_error = str(ai_result.get("error") or "")

    if offline:
        message = "Cloud AI is unavailable in offline mode."
        error = "offline_mode"
    elif errors:
        message = " ".join(errors)
        error = "configuration_error"
    else:
        message = "Text model did not return usable storyboard JSON."
        error = ai_error or "invalid_model_output"
    return {
        "ok": False,
        "source": "ai",
        "shots": [],
        "warnings": [],
        "error": error,
        "error_message": message,
    }


def rewrite_existing_storyboard(project_id: str, payload: ShotRewriteRequest) -> dict[str, Any]:
    require_project(project_id)
    existing_shots = list_shots(project_id)
    if not existing_shots:
        return {"source": "none", "warnings": ["No existing shots to rewrite."], "shots": []}

    source_script = payload.script.strip() or _script_from_existing_shots(existing_shots)
    breakdown = breakdown_script(
        ScriptBreakdownRequest(
            script=source_script,
            style=payload.style,
            visual_format=payload.visual_format,
            panel_gutter_style=payload.panel_gutter_style,
            target_panel_count=len(existing_shots),
            include_dialogue=True,
            use_ai=payload.use_ai,
            output_language=payload.output_language,
        )
    )
    if not breakdown.get("ok", True):
        return breakdown
    rewritten = []
    for original, next_shot in zip(existing_shots, breakdown["shots"]):
        updates = {
            "scene_id": next_shot.scene_id or original.get("scene_id", ""),
            "visual_description": next_shot.visual_description,
            "prompt": next_shot.prompt,
            "negative_prompt": next_shot.negative_prompt,
            "revision_notes": next_shot.revision_notes,
        }
        if payload.reset_outputs:
            updates.update(
                {
                    "status": "pending",
                    "output_path": "",
                    "output_url": "",
                    "download_error": "",
                    "outputs": [],
                    "selected_version_id": "",
                }
            )
        rewritten.append(update_shot(project_id, original["shot_id"], updates))

    warnings = list(breakdown.get("warnings", []))
    if len(rewritten) < len(existing_shots):
        warnings.append("Fewer rewritten panels were returned than existing shots; remaining shots were left unchanged.")
    return {
        "ok": True,
        "source": breakdown.get("source", "local"),
        "warnings": warnings,
        "shots": rewritten,
    }


def _breakdown_with_ai(
    settings: dict[str, Any],
    payload: ScriptBreakdownRequest,
) -> dict[str, Any]:
    language_name = output_language_name(payload.output_language, payload.script)
    user_prompt = f"""
Script:
{payload.script}

Target panel count: {payload.target_panel_count}
Visual style: {payload.style}
Visual format: {payload.visual_format}
Panel separation style: {payload.panel_gutter_style}
Include dialogue or narration notes: {payload.include_dialogue}
Required output language: {language_name}

Before writing panels, infer the main characters, recurring props, location flow,
emotional arc, and panel rhythm from the full script.

Create exactly the target number of panels unless the story is clearly too short.
For each panel:
- scene_id should be P001, P002, ...
- visual_description should be a natural-language panel design, not raw script text.
- visual_description, prompt, negative_prompt, and revision_notes must all use {language_name}.
- prompt should be a direct image prompt under 80 words and start with a localized equivalent of "Panel X of N".
- For single_panel, prompt must describe one comic/storyboard panel with visible story action, not a poster or cover illustration.
- For webtoon_strip, prompt must describe a vertical 3-5 beat mini comic strip inside one image with stacked panels and top-to-bottom reading flow.
- If panel separation style is framed, every panel prompt must require consistent visible gutters/borders with uniform spacing.
- If panel separation style is seamless, every panel prompt must require no gutters, no borders, no frames, and a continuous vertical flow.
- revision_notes should include any dialogue/narration cue, previous/next continuity, character consistency anchor, and intended panel rhythm.
- negative_prompt must prevent watermark, random text, speech bubble text, logo,
  distorted hands, duplicated characters, bad anatomy, and low quality.
"""
    result = generate_text(
        settings,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.2,
    )
    if not result.get("ok"):
        return {"shots": [], "warnings": [result.get("error", "text_generation_failed")]}

    parsed = _parse_json_object(result.get("text", ""))
    if not parsed:
        return {"shots": [], "warnings": ["AI response was not valid JSON."]}

    raw_shots = parsed.get("shots") if isinstance(parsed, dict) else None
    if not isinstance(raw_shots, list):
        return {"shots": [], "warnings": ["AI response did not include a shots array."]}

    locale = normalize_output_language(payload.output_language, payload.script)
    raw_visible_text = " ".join(
        " ".join(
            str(item.get(key) or "")
            for key in ("visual_description", "prompt", "negative_prompt", "revision_notes")
        )
        for item in raw_shots
        if isinstance(item, dict)
    )
    if raw_shots and not is_output_language_compatible(raw_visible_text, locale):
        return {
            "shots": [],
            "warnings": ["AI storyboard output language did not match the selected interface language."],
            "error": "output_language_mismatch",
        }
    shots = [_coerce_shot(item, payload, index) for index, item in enumerate(raw_shots, 1)]
    shots = [shot for shot in shots if shot.prompt.strip()]
    return {"shots": shots[: payload.target_panel_count], "warnings": []}


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


def _coerce_shot(
    item: Any,
    payload: ScriptBreakdownRequest,
    index: int,
) -> ShotCreate:
    data = item if isinstance(item, dict) else {}
    locale = normalize_output_language(payload.output_language, payload.script)
    visual = str(data.get("visual_description") or data.get("description") or "").strip()
    prompt = str(data.get("prompt") or visual).strip()
    panel_prefix = _localized_panel_prefix(locale, index, payload.target_panel_count)
    if panel_prefix.lower() not in prompt.lower():
        prompt = f"{panel_prefix}, {_format_prompt_prefix(payload.visual_format, locale)}, {prompt}"
    style_hint = _localized_style_hint(payload.style, payload.script)
    if style_hint and style_hint.lower() not in prompt.lower():
        prompt = f"{prompt}。风格参考：{style_hint}" if _looks_cjk(payload.script) else f"{prompt}, style reference: {style_hint}"
    return ShotCreate(
        scene_id=str(data.get("scene_id") or f"P{index:03d}"),
        visual_description=visual or prompt,
        prompt=prompt,
        negative_prompt=str(data.get("negative_prompt") or _default_negative_prompt()),
        revision_notes=str(data.get("revision_notes") or data.get("dialogue") or "").strip(),
    )


def _breakdown_locally(payload: ScriptBreakdownRequest) -> list[ShotCreate]:
    chunks = _split_script(payload.script, payload.target_panel_count)
    shots: list[ShotCreate] = []
    locale = normalize_output_language(payload.output_language, payload.script)
    style_hint = _localized_style_hint(payload.style, payload.script)
    for index, chunk in enumerate(chunks, 1):
        visual = _clean_chunk(chunk)
        prompt_source = _visualize_local_beat(visual, index, locale in {"zh-CN", "zh-TW"})
        if locale in {"zh-CN", "zh-TW"}:
            prompt_source = prompt_source.rstrip("。！？!?；;,.，")
            format_instruction = (
                _localized_format_instruction_for_locale(
                    payload.visual_format, payload.panel_gutter_style, locale
                )
                if locale == "zh-TW"
                else _localized_format_instruction(payload.visual_format, payload.panel_gutter_style, cjk=True)
            )
            clarity_instruction = (
                "主體明確，動作和情緒可見，鏡頭構圖有層次，不要畫文字、字幕或氣泡。風格參考："
                if locale == "zh-TW"
                else "主体明确，动作和情绪可见，镜头构图有层次，不要画文字、字幕或气泡。风格参考："
            )
            prompt = (
                f"{_localized_panel_prefix(locale, index, payload.target_panel_count)}：{prompt_source}。"
                f"{format_instruction}"
                f"{clarity_instruction}{style_hint}"
            )
        elif locale == "ja":
            format_instruction = _localized_format_instruction_for_locale(
                payload.visual_format, payload.panel_gutter_style, locale
            )
            prompt = (
                f"{_localized_panel_prefix(locale, index, payload.target_panel_count)}：{prompt_source}。"
                f"{format_instruction} 主体、動作、感情、構図を明確にし、文字や吹き出しを描かない。"
                f"スタイル参照：{style_hint}"
            )
        elif locale == "ko":
            format_instruction = _localized_format_instruction_for_locale(
                payload.visual_format, payload.panel_gutter_style, locale
            )
            prompt = (
                f"{_localized_panel_prefix(locale, index, payload.target_panel_count)}: {prompt_source}. "
                f"{format_instruction} 인물, 동작, 감정과 구도를 명확히 하고 글자나 말풍선을 그리지 마세요. "
                f"스타일 참고: {style_hint}"
            )
        else:
            format_instruction = _localized_format_instruction(payload.visual_format, payload.panel_gutter_style, cjk=False)
            prompt = (
                f"Manga storyboard panel {index}: {prompt_source}. "
                f"{format_instruction} Show specific subjects, visible action, emotion, "
                f"layered composition, and no text or speech bubbles. "
                f"Style reference: {style_hint}"
            )
        shots.append(
            ShotCreate(
                scene_id=f"P{index:03d}",
                visual_description=prompt_source,
                prompt=prompt,
                negative_prompt=_default_negative_prompt(),
                revision_notes=visual if payload.include_dialogue else "",
            )
        )
    return shots


def _split_script(script: str, target_count: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", script) if part.strip()]
    if len(paragraphs) >= target_count:
        return paragraphs[:target_count]

    separators = r"(?<=[。！？!?；;])\s*|(?<=\.)\s+"
    sentences = [part.strip() for part in re.split(separators, script) if part.strip()]
    if not sentences:
        return [script.strip()]
    if len(sentences) <= target_count:
        return sentences

    group_size = max(1, round(len(sentences) / target_count))
    chunks = [
        " ".join(sentences[index : index + group_size])
        for index in range(0, len(sentences), group_size)
    ]
    return chunks[:target_count]


def _script_from_existing_shots(shots: list[dict]) -> str:
    chunks = []
    for index, shot in enumerate(shots, 1):
        parts = [
            shot.get("scene_id", ""),
            shot.get("visual_description", ""),
            shot.get("revision_notes", ""),
            shot.get("prompt", ""),
        ]
        text = _clean_chunk(" ".join(str(part) for part in parts if str(part).strip()))
        if text:
            chunks.append(f"{index}. {text}")
    return "\n\n".join(chunks) or "Create a continuous manga storyboard sequence from the existing panel list."


def _localized_panel_prefix(locale: str, index: int, total: int) -> str:
    if locale == "zh-TW":
        return f"漫畫分鏡第 {index}/{total} 格"
    if locale == "zh-CN":
        return f"漫画分镜第 {index}/{total} 格"
    if locale == "ja":
        return f"絵コンテ {index}/{total} コマ"
    if locale == "ko":
        return f"스토리보드 {index}/{total} 컷"
    return f"Panel {index} of {total}"


def _format_prompt_prefix(visual_format: str, locale: str = "en") -> str:
    if locale == "ja":
        return "縦型ウェブトゥーンの連続ミニストリップ" if visual_format == "webtoon_strip" else "連続する漫画の単一シネマティックコマ"
    if locale == "ko":
        return "세로형 웹툰 연속 미니 스트립" if visual_format == "webtoon_strip" else "연속 만화의 단일 시네마틱 컷"
    if locale in {"zh-CN", "zh-TW"}:
        if locale == "zh-TW":
            return "豎向條漫連續小段" if visual_format == "webtoon_strip" else "連續漫畫的單幅電影感分鏡"
        return "竖向条漫连续小段" if visual_format == "webtoon_strip" else "连续漫画的单幅电影感分镜"
    if visual_format == "webtoon_strip":
        return "vertical webtoon mini strip, 3 to 5 stacked comic beats inside one image, continuous manga sequence"
    return "single cinematic comic panel, continuous manga storyboard sequence"


def _localized_format_instruction_for_locale(
    visual_format: str,
    panel_gutter_style: str,
    locale: str,
) -> str:
    if locale == "ja":
        if visual_format == "single_panel":
            return "1 枚に 1 つの物語の瞬間だけを描き、コラージュにしない。"
        if panel_gutter_style == "seamless":
            return "1 枚の縦長画像に 3〜5 の連続場面を描き、枠線や白い余白を使わず背景を連続させる。"
        return "1 枚の縦長画像に 3〜5 の連続コマを描き、同じ太さと色の枠線と均等な余白を使う。"
    if locale == "ko":
        if visual_format == "single_panel":
            return "한 이미지에는 하나의 이야기 순간만 그리고 콜라주로 만들지 마세요."
        if panel_gutter_style == "seamless":
            return "한 장의 세로 이미지에 3~5개 연속 장면을 그리고 테두리나 흰 여백 없이 배경을 이어 주세요."
        return "한 장의 세로 이미지에 3~5개 연속 컷을 그리고 같은 굵기와 색의 테두리 및 균일한 여백을 사용하세요."
    if locale == "zh-TW":
        if visual_format == "single_panel":
            return "一張圖片只描繪一個故事瞬間，不要製作拼貼。"
        if panel_gutter_style == "seamless":
            return "一張豎圖包含 3 到 5 個連續故事節拍，不使用邊框或白色留白，以連續背景銜接。"
        return "一張豎圖包含 3 到 5 個連續分鏡，使用相同粗細與顏色的邊框及均等留白。"
    return _localized_format_instruction(visual_format, panel_gutter_style, cjk=False)


def _localized_format_instruction(visual_format: str, panel_gutter_style: str, cjk: bool) -> str:
    if visual_format == "webtoon_strip":
        if panel_gutter_style == "seamless":
            if cjk:
                return "输出为一张竖向条漫小段，画面内部包含 3 到 5 个上下连续故事节拍，不要白色分隔线、边框或圆角框，使用连续背景或镜头运动衔接。"
            return (
                "Create one seamless vertical webtoon mini strip with 3 to 5 stacked story beats, "
                "no white gutters, no borders, no frames, and continuous top-to-bottom visual flow."
            )
        if cjk:
            return "输出为一张竖向条漫小段，画面内部包含 3 到 5 个上下连续小格，每个小格都有统一的清晰边框、留白和从上到下的阅读节奏。"
        return (
            "Create one vertical webtoon mini strip with 3 to 5 stacked comic beats, "
            "consistent visible gutters, uniform panel borders, spacing, and top-to-bottom reading rhythm."
        )
    if cjk:
        return "输出为一张单格漫画画面，只表现一个清楚的故事瞬间，不要做多格拼贴。"
    return "Create one single comic panel only, showing one clear story moment, with no multi-panel collage."


def _clean_chunk(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _shorten_for_prompt(text: str, max_chars: int = 180) -> str:
    cleaned = _clean_chunk(text)
    if len(cleaned) <= max_chars:
        return cleaned
    sentence_match = re.match(r"(.{1,%d}?[。！？!?；;,.，])" % max_chars, cleaned)
    if sentence_match:
        return sentence_match.group(1).strip()
    return f"{cleaned[: max_chars - 1].rstrip()}..."


def _visualize_local_beat(text: str, index: int, cjk: bool) -> str:
    short = _shorten_for_prompt(text, 120 if cjk else 160)
    if cjk:
        shot_types = ["远景建立场景", "中景交代人物行动", "近景表现表情变化", "特写强调关键物品或转折"]
        return f"{shot_types[(index - 1) % len(shot_types)]}，围绕这一故事信息设计可见画面：{short}"
    shot_types = [
        "wide establishing composition",
        "medium shot showing the character action",
        "close-up focused on the emotional turn",
        "detail shot of the key prop or reveal",
    ]
    return f"{shot_types[(index - 1) % len(shot_types)]}, visualizing this story beat: {short}"


def _looks_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text or ""))


def _localized_style_hint(style: str, script: str) -> str:
    cleaned = _clean_chunk(style)
    if not _looks_cjk(script):
        return cleaned
    replacements = {
        "black and white manga storyboard": "黑白漫画分镜",
        "black-and-white manga storyboard style": "黑白漫画分镜风格",
        "clean line art": "干净线稿",
        "crisp clean ink line art": "清晰干净墨线",
        "white paper base": "白纸底",
        "controlled hatching": "受控排线",
        "minimal gray tones": "少量灰阶",
        "consistent characters": "角色一致",
        "expressive faces": "表情清晰",
        "cinematic panel composition": "电影感分镜构图",
        "vertical color webcomic style": "彩色竖版网漫",
        "bright readable colors": "明亮易读色彩",
        "polished mobile webtoon finish": "精致移动端网漫质感",
        "soft cel shading": "柔和赛璐璐上色",
        "cinematic grayscale comic style": "电影感灰阶漫画",
        "dramatic lighting": "戏剧化光影",
        "soft watercolor storybook comic style": "柔和水彩绘本漫画",
        "minimal clean line comic style": "极简干净线条漫画",
        "retro print comic style": "复古印刷漫画",
        "bold ink outlines": "粗黑墨线轮廓",
        "limited color accents": "有限色彩点缀",
        "vintage print texture": "复古印刷质感",
        "halftone shading": "半调网点阴影",
        "urban pop comic style": "都市波普漫画",
        "bright poster colors": "明亮海报色",
        "bold graphic shapes": "粗大胆图形块面",
        "flat color blocks": "平涂色块",
        "sticker-like accents": "贴纸感点缀",
        "street fashion details": "街头时装细节",
        "high-energy city mood": "高能都市氛围",
        "vintage newspaper comic strip style": "复古老报纸连环漫画",
        "sepia ink": "棕褐色油墨",
        "aged paper texture": "旧纸张质感",
        "chinese ink wash historical fantasy comic style": "水墨古风幻想漫画",
        "rice paper texture": "宣纸质感",
        "chinese heritage animation inspired comic style": "中国传统动画美学漫画",
        "paper-cut shapes": "剪纸块面",
        "futuristic sci-fi comic style": "未来科幻漫画",
        "luminous interfaces": "发光界面",
        "clean hard-surface design": "干净硬表面设计",
        "cyber neon city comic style": "赛博霓虹都市漫画",
        "reflective wet surfaces": "潮湿反光表面",
        "solarpunk future comic style": "太阳朋克未来漫画",
        "optimistic technology": "乐观科技感",
        "silk road fantasy mural comic style": "丝路壁画幻想漫画",
        "fresco-like texture": "壁画湿壁画质感",
        "afrofuturist graphic novel style": "非洲未来主义图像小说风格",
        "vibrant metallic accents": "鲜明金属色点缀",
        "latin american magical realism mural comic style": "拉美魔幻现实壁画漫画",
        "textured plaster": "灰泥墙面质感",
        "ukiyo-e woodblock inspired comic style": "浮世绘木版漫画",
        "flat color planes": "平面色块",
        "art deco noir comic style": "装饰艺术黑色电影漫画",
        "geometric architecture": "几何建筑",
        "gold and black accents": "金黑点缀",
    }
    lowered = cleaned.lower()
    parts = []
    for source, target in replacements.items():
        if source in lowered:
            parts.append(target)
    return "，".join(dict.fromkeys(parts)) or cleaned


def _default_negative_prompt() -> str:
    return (
        "watermark, random text, speech bubble text, logo, distorted hands, "
        "bad anatomy, duplicated character, low quality"
    )
