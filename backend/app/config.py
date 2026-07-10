import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from backend.app.security import protect_secret, unprotect_secret


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DATA_DIR = Path(
    os.getenv(
        "PANELOOM_APP_DATA_DIR",
        str(Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Paneloom"),
    )
)
APP_CONFIG_DIR = APP_DATA_DIR / "config"
APP_LOG_DIR = APP_DATA_DIR / "logs"
APP_CACHE_DIR = APP_DATA_DIR / "cache"
APP_TEMP_DIR = APP_DATA_DIR / "temp"
APP_REGISTRY_DIR = APP_DATA_DIR / "registry"
PROJECT_REGISTRY_PATH = APP_REGISTRY_DIR / "projects.json"
DEFAULT_PROJECTS_HOME = Path(
    os.getenv(
        "PANELOOM_PROJECTS_HOME",
        str(Path.home() / "Documents" / "Paneloom Projects"),
    )
)
LEGACY_DATA_ROOT = Path(os.getenv("PANELOOM_LEGACY_DATA_ROOT", str(ROOT_DIR)))
DB_DIR = LEGACY_DATA_ROOT / "db"
PROJECTS_DIR = DB_DIR / "projects"
ASSETS_DIR = LEGACY_DATA_ROOT / "assets"
GENERATED_ASSETS_DIR = ASSETS_DIR / "generated"
REFERENCE_ASSETS_DIR = ASSETS_DIR / "references"
EXPORTS_DIR = LEGACY_DATA_ROOT / "exports"
LEGACY_SETTINGS_PATH = DB_DIR / "settings.json"
DEFAULT_SETTINGS_PATH = APP_CONFIG_DIR / "settings.json"
SETTINGS_PATH = Path(os.getenv("PANELOOM_SETTINGS_PATH", str(DEFAULT_SETTINGS_PATH)))

OFFICIAL_BASE_URL = "https://api.openai.com/v1"
GLM_NATIVE_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
GOOGLE_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GOOGLE_NATIVE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TEXT_MODEL = "gpt-5.5"
DEFAULT_GLM_TEXT_MODEL = "glm-4.5"
DEFAULT_GOOGLE_TEXT_MODEL = "gemini-3.5-flash"
DEFAULT_IMAGE_MODEL = "gpt-image-2"
DEFAULT_IMAGE_SIZE = "1024x1024"
DEFAULT_IMAGE_QUALITY = "low"
DEFAULT_IMAGE_RESULT_MODE = "auto"


def ensure_runtime_dirs() -> None:
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    APP_LOG_DIR.mkdir(parents=True, exist_ok=True)
    APP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    APP_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    APP_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PROJECTS_HOME.mkdir(parents=True, exist_ok=True)


def mask_api_key(api_key: str | None) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    prefix = api_key[:3]
    suffix = api_key[-4:]
    return f"{prefix}****{suffix}"


def is_offline_mode() -> bool:
    return os.getenv("PANELOOM_FORCE_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


def _read_settings_file() -> dict[str, Any]:
    source_path = SETTINGS_PATH
    using_legacy = False
    if (
        not source_path.exists()
        and SETTINGS_PATH == DEFAULT_SETTINGS_PATH
        and LEGACY_SETTINGS_PATH.exists()
    ):
        source_path = LEGACY_SETTINGS_PATH
        using_legacy = True
    if not source_path.exists():
        return {}
    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Local settings JSON is invalid; it was not overwritten.") from exc
    if not isinstance(data, dict):
        return {}
    encrypted_keys = {
        "api_key": data.pop("api_key_encrypted", ""),
        "text_api_key": data.pop("text_api_key_encrypted", ""),
    }
    for key, encrypted in encrypted_keys.items():
        if encrypted:
            try:
                data[key] = unprotect_secret(encrypted)
            except (OSError, ValueError) as exc:
                raise ValueError(
                    "A saved API credential cannot be decrypted for this Windows user."
                ) from exc
    needs_migration = using_legacy or bool(data.get("api_key") or data.get("text_api_key"))
    if needs_migration:
        _write_settings_file(normalize_settings(data))
        if using_legacy:
            _replace_legacy_settings_with_migration_marker()
    return data


def _settings_for_storage(settings: dict[str, Any]) -> dict[str, Any]:
    stored = {
        key: value
        for key, value in settings.items()
        if key not in {"api_key", "text_api_key", "source"}
    }
    stored["storage_version"] = 2
    if settings.get("api_key"):
        stored["api_key_encrypted"] = protect_secret(str(settings["api_key"]))
    if settings.get("text_api_key"):
        stored["text_api_key_encrypted"] = protect_secret(str(settings["text_api_key"]))
    return stored


def _write_settings_file(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SETTINGS_PATH.with_name(f".{SETTINGS_PATH.name}.{uuid.uuid4().hex}.tmp")
    temporary_path.write_text(
        json.dumps(_settings_for_storage(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if SETTINGS_PATH.exists():
        shutil.copy2(SETTINGS_PATH, SETTINGS_PATH.with_suffix(f"{SETTINGS_PATH.suffix}.bak"))
    temporary_path.replace(SETTINGS_PATH)


def _replace_legacy_settings_with_migration_marker() -> None:
    marker = {
        "storage_version": 2,
        "migrated": True,
        "settings_location": "%LOCALAPPDATA%/Paneloom/config/settings.json",
    }
    temporary_path = LEGACY_SETTINGS_PATH.with_name(
        f".{LEGACY_SETTINGS_PATH.name}.{uuid.uuid4().hex}.tmp"
    )
    temporary_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    temporary_path.replace(LEGACY_SETTINGS_PATH)


def _settings_has_saved_credentials(settings: dict[str, Any]) -> bool:
    return bool(settings.get("api_key") or settings.get("base_url"))


def get_env_settings() -> dict[str, Any]:
    provider_type = os.getenv("OPENAI_PROVIDER_TYPE", "custom")
    base_url = os.getenv("OPENAI_BASE_URL") or (
        OFFICIAL_BASE_URL if provider_type == "official" else ""
    )
    return {
        "provider_type": provider_type,
        "base_url": base_url,
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "text_provider": os.getenv("TEXT_PROVIDER", "gpt"),
        "text_provider_mode": os.getenv("TEXT_PROVIDER_MODE", "native"),
        "text_base_url": os.getenv("TEXT_BASE_URL", ""),
        "text_api_key": os.getenv("TEXT_API_KEY", ""),
        "text_model": os.getenv("TEXT_MODEL", DEFAULT_TEXT_MODEL),
        "image_model": os.getenv("IMAGE_MODEL", DEFAULT_IMAGE_MODEL),
        "image_size": os.getenv("IMAGE_SIZE", DEFAULT_IMAGE_SIZE),
        "image_quality": os.getenv("IMAGE_QUALITY", DEFAULT_IMAGE_QUALITY),
        "image_result_mode": os.getenv("IMAGE_RESULT_MODE", DEFAULT_IMAGE_RESULT_MODE),
    }


def normalize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    provider_type = settings.get("provider_type") or "custom"
    if provider_type not in {"official", "custom"}:
        provider_type = "custom"

    base_url = (settings.get("base_url") or "").strip()
    if provider_type == "official":
        base_url = OFFICIAL_BASE_URL
    image_result_mode = settings.get("image_result_mode") or DEFAULT_IMAGE_RESULT_MODE
    if image_result_mode not in {"auto", "prefer_b64_json", "url_only"}:
        image_result_mode = DEFAULT_IMAGE_RESULT_MODE
    image_size = _normalize_image_size(settings.get("image_size") or DEFAULT_IMAGE_SIZE)
    text_provider = settings.get("text_provider") or "gpt"
    if text_provider not in {"gpt", "glm", "google"}:
        text_provider = "gpt"
    text_provider_mode = settings.get("text_provider_mode") or "native"
    if text_provider_mode not in {"native", "relay"}:
        text_provider_mode = "native"
    text_base_url = (settings.get("text_base_url") or "").strip()
    text_model = settings.get("text_model") or _default_text_model(text_provider)

    return {
        "provider_type": provider_type,
        "base_url": base_url,
        "api_key": settings.get("api_key") or "",
        "text_provider": text_provider,
        "text_provider_mode": text_provider_mode,
        "text_base_url": text_base_url,
        "text_api_key": settings.get("text_api_key") or settings.get("api_key") or "",
        "text_model": text_model,
        "image_model": settings.get("image_model") or DEFAULT_IMAGE_MODEL,
        "image_size": image_size,
        "image_quality": settings.get("image_quality") or DEFAULT_IMAGE_QUALITY,
        "image_result_mode": image_result_mode,
    }


def get_active_settings(include_secret: bool = True) -> dict[str, Any]:
    ensure_runtime_dirs()
    saved = _read_settings_file()
    if _settings_has_saved_credentials(saved):
        settings = normalize_settings(saved)
        source = "local"
    else:
        settings = normalize_settings(get_env_settings())
        source = "environment"

    settings["source"] = source
    if not include_secret:
        settings["api_key"] = mask_api_key(settings.get("api_key"))
        settings["text_api_key"] = mask_api_key(settings.get("text_api_key"))
    return settings


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    normalized = normalize_settings(settings)
    _write_settings_file(normalized)
    return normalized


def validate_api_settings(settings: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not settings.get("api_key"):
        errors.append("API key is missing. Configure it in Settings or OPENAI_API_KEY.")
    if not settings.get("base_url"):
        errors.append("Base URL is missing. Configure it in Settings or OPENAI_BASE_URL.")
    if not settings.get("image_model"):
        errors.append("Image model is missing.")
    if not _is_valid_image_size(settings.get("image_size", "")):
        errors.append("Image size must look like 1024x1024, 900x1600, or auto.")
    return errors


def get_text_api_config(settings: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_settings(settings)
    provider = normalized["text_provider"]
    mode = normalized["text_provider_mode"]
    base_url = normalized.get("text_base_url") or normalized.get("base_url") or ""
    if mode == "native":
        if provider == "gpt":
            base_url = OFFICIAL_BASE_URL
        elif provider == "glm":
            base_url = normalized.get("text_base_url") or GLM_NATIVE_BASE_URL
        elif provider == "google":
            base_url = GOOGLE_NATIVE_BASE_URL
    elif provider == "google" and not base_url:
        base_url = GOOGLE_OPENAI_BASE_URL

    return {
        "provider": provider,
        "mode": mode,
        "base_url": base_url,
        "api_key": normalized.get("text_api_key") or normalized.get("api_key") or "",
        "model": normalized.get("text_model") or _default_text_model(provider),
    }


def validate_text_settings(settings: dict[str, Any]) -> list[str]:
    config = get_text_api_config(settings)
    errors: list[str] = []
    if not config.get("api_key"):
        errors.append("Text API key is missing.")
    if not config.get("base_url"):
        errors.append("Text Base URL is missing.")
    if not config.get("model"):
        errors.append("Text model is missing.")
    return errors


def _normalize_image_size(value: str) -> str:
    cleaned = str(value or "").strip().lower().replace("*", "x").replace("×", "x")
    return cleaned or DEFAULT_IMAGE_SIZE


def _is_valid_image_size(value: str) -> bool:
    cleaned = _normalize_image_size(value)
    if cleaned == "auto":
        return True
    parts = cleaned.split("x")
    if len(parts) != 2:
        return False
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        return False
    return 64 <= width <= 4096 and 64 <= height <= 4096


def _default_text_model(provider: str) -> str:
    if provider == "glm":
        return DEFAULT_GLM_TEXT_MODEL
    if provider == "google":
        return DEFAULT_GOOGLE_TEXT_MODEL
    return DEFAULT_TEXT_MODEL
