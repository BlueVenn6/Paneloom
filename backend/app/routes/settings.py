from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import perf_counter

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

from api.openai_image_client import generate_image
from api.openai_text_client import generate_text

router = APIRouter(prefix="/settings", tags=["settings"])
_TEXT_TEST_LOCK = Lock()
_IMAGE_TEST_LOCK = Lock()


def _merge_existing_secret(payload: SettingsPayload) -> dict:
    incoming = payload.model_dump()
    current = get_active_settings(include_secret=True)
    clear_saved_keys = bool(incoming.pop("clear_saved_keys", False))
    if clear_saved_keys:
        incoming["api_key"] = ""
        incoming["text_api_key"] = ""
    else:
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
    settings, source = _settings_for_test(payload)

    image_errors = validate_api_settings(settings)
    text_errors = validate_text_settings(settings)

    text_config = get_text_api_config(settings)
    image_result = {"ok": False, "status": "failed", "errors": image_errors}
    text_result = {
        "ok": False,
        "status": "failed",
        "errors": text_errors,
        "provider": text_config["provider"],
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        image_future = executor.submit(_test_image_generation, settings) if not image_errors else None
        text_future = executor.submit(_test_text_inference, text_config) if not text_errors else None
        if image_future:
            image_result = image_future.result()
        if text_future:
            text_result = text_future.result()

    ok = bool(image_result.get("ok")) and bool(text_result.get("ok"))
    return ApiResponse(
        ok=ok,
        message="Real provider tests completed.",
        data={"source": source, "image": image_result, "text": text_result},
    )


@router.post("/test/text")
def test_text_settings(payload: SettingsPayload | None = None) -> ApiResponse:
    settings, source = _settings_for_test(payload)
    errors = validate_text_settings(settings)
    if not _TEXT_TEST_LOCK.acquire(blocking=False):
        result = {"ok": False, "status": "busy", "errors": ["A text provider test is already running."]}
    else:
        try:
            result = (
                {"ok": False, "status": "failed", "errors": errors}
                if errors
                else _test_text_inference(get_text_api_config(settings))
            )
        finally:
            _TEXT_TEST_LOCK.release()
    return ApiResponse(
        ok=bool(result.get("ok")),
        message="Text provider test completed.",
        data={"source": source, **result},
    )


@router.post("/test/image")
def test_image_settings(payload: SettingsPayload | None = None) -> ApiResponse:
    settings, source = _settings_for_test(payload)
    errors = validate_api_settings(settings)
    if not _IMAGE_TEST_LOCK.acquire(blocking=False):
        result = {"ok": False, "status": "busy", "errors": ["An image provider test is already running."]}
    else:
        try:
            result = (
                {"ok": False, "status": "failed", "errors": errors}
                if errors
                else _test_image_generation(settings)
            )
        finally:
            _IMAGE_TEST_LOCK.release()
    return ApiResponse(
        ok=bool(result.get("ok")),
        message="Image provider test completed.",
        data={"source": source, **result},
    )


def _settings_for_test(payload: SettingsPayload | None) -> tuple[dict, str]:
    if payload:
        return normalize_settings(_merge_existing_secret(payload)), "request"
    settings = get_active_settings(include_secret=True)
    return settings, settings.get("source", "active")

def _test_text_inference(config: dict) -> dict:
    started = perf_counter()
    result = generate_text(
        config,
        system_prompt="You are a connection test. Follow the user instruction exactly.",
        user_prompt="Reply with exactly: OK",
        temperature=0,
        max_output_tokens=8,
    )
    elapsed = round(perf_counter() - started, 2)
    text = str(result.get("text") or "").strip()
    ok = bool(result.get("ok") and text)
    return {
        "ok": ok,
        "status": "passed" if ok else "failed",
        "validation_level": "real_inference",
        "provider": config.get("provider", ""),
        "model": config.get("model", ""),
        "status_code": result.get("status_code"),
        "duration_seconds": elapsed,
        "response_preview": text[:40] if ok else "",
        "errors": [] if ok else [_provider_result_error(result, "Text model did not return text.")],
    }


def _test_image_generation(settings: dict) -> dict:
    started = perf_counter()
    with TemporaryDirectory(prefix="paneloom-image-test-") as directory:
        output_path = Path(directory) / "provider-test.png"
        result = generate_image(
            settings,
            prompt="A plain white circle centered on a solid black background. No text.",
            size="1024x1024",
            quality="low",
            output_path=output_path,
        )
        saved = output_path.is_file() and output_path.stat().st_size > 0
    elapsed = round(perf_counter() - started, 2)
    ok = bool(result.get("ok") and saved)
    return {
        "ok": ok,
        "status": "passed" if ok else "failed",
        "validation_level": "real_generation",
        "model": settings.get("image_model", ""),
        "status_code": result.get("status_code"),
        "duration_seconds": elapsed,
        "output_verified": saved,
        "errors": [] if ok else [_provider_result_error(result, "Image model did not return a valid image file.")],
    }


def _provider_result_error(result: dict, fallback: str) -> str:
    return str(
        result.get("error_message")
        or result.get("exception_message")
        or result.get("error")
        or result.get("short_error")
        or fallback
    )
