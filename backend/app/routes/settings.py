import requests
from fastapi import APIRouter, HTTPException

from backend.app.config import (
    OFFICIAL_BASE_URL,
    get_active_settings,
    get_text_api_config,
    mask_api_key,
    normalize_settings,
    save_settings,
    validate_api_settings,
    validate_text_settings,
)
from backend.app.models.schemas import ApiResponse, SettingsPayload

router = APIRouter(prefix="/settings", tags=["settings"])


def _merge_existing_secret(payload: SettingsPayload) -> dict:
    incoming = payload.model_dump()
    current = get_active_settings(include_secret=True)
    api_key = incoming.get("api_key", "")
    if not api_key or "****" in api_key:
        incoming["api_key"] = current.get("api_key", "")
    text_api_key = incoming.get("text_api_key", "")
    if not text_api_key or "****" in text_api_key:
        incoming["text_api_key"] = current.get("text_api_key", "")
    if incoming.get("provider_type") == "official":
        incoming["base_url"] = OFFICIAL_BASE_URL
    return incoming


@router.get("")
def get_settings() -> ApiResponse:
    settings = get_active_settings(include_secret=False)
    return ApiResponse(ok=True, message="Settings loaded.", data=settings)


@router.post("")
def post_settings(payload: SettingsPayload) -> ApiResponse:
    try:
        saved = save_settings(_merge_existing_secret(payload))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    redacted = {
        **saved,
        "api_key": mask_api_key(saved.get("api_key")),
        "text_api_key": mask_api_key(saved.get("text_api_key")),
        "source": "local",
    }
    return ApiResponse(ok=True, message="Settings saved.", data=redacted)


@router.post("/test")
def test_settings(payload: SettingsPayload | None = None) -> ApiResponse:
    if payload:
        settings = normalize_settings(_merge_existing_secret(payload))
        source = "request"
    else:
        settings = get_active_settings(include_secret=True)
        source = settings.get("source", "active")

    image_errors = validate_api_settings(settings)
    text_errors = validate_text_settings(settings)

    image_result = {"ok": False, "errors": image_errors}
    if not image_errors:
        image_result = _test_openai_compatible_models(
            base_url=settings["base_url"],
            api_key=settings["api_key"],
            model=settings.get("image_model", ""),
        )
    text_config = get_text_api_config(settings)
    text_result = {"ok": False, "errors": text_errors, "provider": text_config["provider"]}
    if not text_errors:
        if text_config["provider"] == "google" and text_config["mode"] == "native":
            text_result = _test_google_native_models(text_config)
        else:
            text_result = _test_openai_compatible_models(
                base_url=text_config["base_url"],
                api_key=text_config["api_key"],
                model=text_config["model"],
            )
            text_result["provider"] = text_config["provider"]

    ok = bool(image_result.get("ok")) and bool(text_result.get("ok"))
    return ApiResponse(
        ok=ok,
        message="Connection tests completed.",
        data={"source": source, "image": image_result, "text": text_result},
    )


def _test_openai_compatible_models(base_url: str, api_key: str, model: str) -> dict:
    checked_url = f"{base_url.rstrip('/')}/models"
    try:
        response = requests.get(checked_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
        if response.status_code == 404 and not base_url.rstrip("/").endswith("/v1"):
            checked_url = f"{base_url.rstrip('/')}/v1/models"
            response = requests.get(
                checked_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text}
    except requests.RequestException as exc:
        return {"ok": False, "errors": [str(exc)]}

    if response.status_code >= 400:
        return {
            "ok": False,
            "status_code": response.status_code,
            "errors": [body],
        }

    model_ids = [
        item.get("id")
        for item in body.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    model_found = model in model_ids if model_ids else None
    return {
        "ok": model_found is not False,
        "status_code": response.status_code,
        "checked_url": checked_url,
        "model": model,
        "model_found": model_found,
        "models_checked": len(model_ids),
        "errors": [] if model_found is not False else ["Configured model was not found."],
    }


def _test_google_native_models(config: dict) -> dict:
    try:
        response = requests.get(
            f"{config['base_url'].rstrip('/')}/models",
            params={"key": config["api_key"]},
            timeout=30,
        )
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text}
    except requests.RequestException as exc:
        return {"ok": False, "provider": "google", "errors": [str(exc)]}
    if response.status_code >= 400:
        return {
            "ok": False,
            "provider": "google",
            "status_code": response.status_code,
            "errors": [body],
        }
    model_names = [
        str(item.get("name", "")).split("/")[-1]
        for item in body.get("models", [])
        if isinstance(item, dict)
    ]
    model_found = config["model"] in model_names if model_names else None
    return {
        "ok": model_found is not False,
        "provider": "google",
        "status_code": response.status_code,
        "model": config["model"],
        "model_found": model_found,
        "models_checked": len(model_names),
        "errors": [] if model_found is not False else ["Configured model was not found."],
    }
