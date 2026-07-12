import re


SUPPORTED_UI_LOCALES = {"zh-CN", "zh-TW", "en", "ja", "ko"}


def normalize_output_language(value: str = "", source_text: str = "") -> str:
    requested = str(value or "").strip()
    if requested in SUPPORTED_UI_LOCALES:
        return requested
    if requested and requested != "source":
        return "en"
    if re.search(r"[\u3040-\u30ff]", source_text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", source_text):
        return "ko"
    if re.search(r"[\u3400-\u9fff]", source_text):
        return "zh-CN"
    return "en"


def output_language_name(value: str = "", source_text: str = "") -> str:
    locale = normalize_output_language(value, source_text)
    return {
        "zh-CN": "Simplified Chinese",
        "zh-TW": "Traditional Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
    }[locale]


def is_output_language_compatible(text: str, locale: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    normalized = normalize_output_language(locale)
    if normalized in {"zh-CN", "zh-TW"}:
        return len(re.findall(r"[\u3400-\u9fff]", value)) >= 2
    if normalized == "ja":
        return len(re.findall(r"[\u3040-\u30ff]", value)) >= 2
    if normalized == "ko":
        return len(re.findall(r"[\uac00-\ud7af]", value)) >= 2
    return bool(re.search(r"[A-Za-z]{2}", value)) and not re.search(
        r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]",
        value,
    )
