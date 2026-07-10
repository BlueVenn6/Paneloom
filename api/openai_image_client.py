import base64
import json
import uuid
import mimetypes
from pathlib import Path
from typing import Any

import requests


IMAGE_REQUEST_TIMEOUT_SECONDS = 600


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _with_v1_base_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    return clean if clean.endswith("/v1") else f"{clean}/v1"


def _looks_like_missing_v1(result: dict) -> bool:
    endpoint = str(result.get("endpoint") or "")
    return result.get("status_code") == 404 and "/v1/" not in endpoint


def _atomic_write_bytes(output_path: Path, content: bytes) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _save_b64_image(b64_json: str, output_path: Path) -> None:
    _atomic_write_bytes(output_path, base64.b64decode(b64_json))


def _download_image(url: str, output_path: Path, timeout: int = 30, retries: int = 2) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_error: requests.RequestException | None = None
    for attempt in range(1, retries + 2):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            _atomic_write_bytes(output_path, response.content)
            return
        except requests.RequestException as exc:
            last_error = exc
            if attempt > retries:
                break
    raise RuntimeError(
        f"Image download failed after {retries + 1} attempts: {last_error}"
    ) from last_error


def _extract_image_payload(data: dict[str, Any]) -> dict[str, str]:
    items = data.get("data") or []
    if not items:
        return {}
    first = items[0] if isinstance(items[0], dict) else {}
    return {
        "url": first.get("url") or "",
        "b64_json": first.get("b64_json") or "",
    }


def _stringify_raw(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _extract_error_fields(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {"error_type": "", "error_code": "", "error_message": ""}
    error = raw.get("error") if isinstance(raw.get("error"), dict) else {}
    return {
        "error_type": error.get("type") or "",
        "error_code": error.get("code") or error.get("type") or "",
        "error_message": error.get("message") or raw.get("message") or "",
    }


def _classify_error(
    status_code: int | None = None,
    error_code: str = "",
    error_type: str = "",
    message: str = "",
    exception_type: str = "",
) -> str:
    haystack = " ".join(
        [error_code, error_type, message, exception_type]
    ).lower()
    if status_code in {408, 504, 524} or "cloudflare" in haystack:
        return "request_timeout"
    if "timeout" in haystack or exception_type in {"Timeout", "ConnectTimeout", "ReadTimeout"}:
        return "request_timeout"
    if "insufficient_quota" in haystack or "quota" in haystack or "额度" in haystack:
        return "insufficient_quota"
    if status_code == 401 or "invalid_api_key" in haystack or "unauthorized" in haystack:
        return "invalid_api_key"
    if status_code == 404:
        if "model" in haystack:
            return "model_not_found"
        return "endpoint_not_found"
    if status_code == 429:
        return "insufficient_quota" if "quota" in haystack else "rate_limited"
    if "model_not_found" in haystack or "model not found" in haystack:
        return "model_not_found"
    if "connection" in haystack:
        return "connection_error"
    if "download" in haystack:
        return "image_download_failed"
    if error_code:
        return error_code
    if error_type:
        return error_type
    return "image_generation_failed"


def _is_response_format_unsupported(result: dict) -> bool:
    status_code = result.get("status_code")
    haystack = " ".join(
        [
            str(result.get("provider_error_code", "")),
            str(result.get("error_code", "")),
            str(result.get("error_type", "")),
            str(result.get("error_message", "")),
            str(result.get("raw_response", "")),
        ]
    ).lower()
    return status_code in {400, 422} and (
        "response_format" in haystack
        or "unsupported parameter" in haystack
        or "unknown parameter" in haystack
        or "extra_forbidden" in haystack
    )


def _error(
    message: str,
    *,
    endpoint: str = "",
    model: str = "",
    size: str = "",
    quality: str = "",
    status_code: int | None = None,
    raw: Any | None = None,
    response_text: str = "",
    exception: Exception | None = None,
    error_type: str = "",
    error_code: str = "",
    error_message: str = "",
) -> dict:
    extracted = _extract_error_fields(raw)
    error_type = error_type or extracted["error_type"]
    error_code = error_code or extracted["error_code"]
    error_message = error_message or extracted["error_message"] or message
    raw_text = response_text or _stringify_raw(raw)
    if status_code == 524:
        error_message = "Image API timed out upstream (Cloudflare 524). The provider did not finish the image edit/generation before the gateway timeout."
    elif status_code in {408, 504}:
        error_message = f"Image API timed out upstream (HTTP {status_code})."
    elif raw_text.lstrip().lower().startswith("<!doctype html") or raw_text.lstrip().lower().startswith("<html"):
        error_message = f"Image API returned an HTML error page instead of JSON (HTTP {status_code or 'unknown'})."
    exception_type = type(exception).__name__ if exception else ""
    exception_message = str(exception) if exception else ""
    classified_code = _classify_error(
        status_code=status_code,
        error_code=error_code,
        error_type=error_type,
        message=error_message or message,
        exception_type=exception_type,
    )
    return {
        "ok": False,
        "error": classified_code,
        "error_type": error_type,
        "error_code": classified_code,
        "provider_error_code": error_code,
        "error_message": error_message,
        "exception_type": exception_type,
        "exception_message": exception_message,
        "status_code": status_code,
        "raw": raw,
        "raw_response": raw_text,
        "endpoint": endpoint,
        "model": model,
        "size": size,
        "quality": quality,
        "output_path": "",
        "output_url": "",
        "b64_json": "",
    }


def generate_image(
    config: dict[str, Any],
    prompt: str,
    size: str | None = None,
    quality: str | None = None,
    output_path: str | Path | None = None,
) -> dict:
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    if not api_key:
        return _error("API key is missing. Configure Settings or OPENAI_API_KEY.")
    if not base_url:
        return _error("Base URL is missing. Configure Settings or OPENAI_BASE_URL.")

    payload = {
        "model": config.get("image_model") or "gpt-image-2",
        "prompt": prompt,
        "size": size or config.get("image_size") or "1024x1024",
        "quality": quality or config.get("image_quality") or "low",
    }
    endpoint = _endpoint(base_url, "/images/generations")
    result_mode = config.get("image_result_mode") or "auto"

    def _post_generation(request_payload: dict[str, Any], request_endpoint: str) -> dict:
        response = requests.post(
            request_endpoint,
            headers={**_headers(api_key), "Content-Type": "application/json"},
            json=request_payload,
            timeout=(30, IMAGE_REQUEST_TIMEOUT_SECONDS),
        )
        parse_exception = None
        try:
            data = response.json()
        except ValueError as exc:
            parse_exception = exc
            data = {"text": response.text}
            if response.status_code < 400:
                return _error(
                    "Image generation response was not valid JSON.",
                    endpoint=request_endpoint,
                    model=request_payload["model"],
                    size=request_payload["size"],
                    quality=request_payload["quality"],
                    status_code=response.status_code,
                    raw=data,
                    response_text=response.text,
                    exception=exc,
                    error_code="json_parse_error",
                    error_message=str(exc),
                )
        if response.status_code >= 400:
            return _error(
                "Image generation request failed.",
                endpoint=request_endpoint,
                model=request_payload["model"],
                size=request_payload["size"],
                quality=request_payload["quality"],
                status_code=response.status_code,
                raw=data,
                response_text=response.text,
                exception=parse_exception,
            )
        return {
            "response": response,
            "data": data,
            "payload": request_payload,
        }

    try:
        request_payload = dict(payload)
        tried_b64_first = result_mode in {"auto", "prefer_b64_json"}
        if tried_b64_first:
            request_payload["response_format"] = "b64_json"

        post_result = _post_generation(request_payload, endpoint)
        if isinstance(post_result, dict) and post_result.get("ok") is False and _looks_like_missing_v1(post_result):
            endpoint = _endpoint(_with_v1_base_url(base_url), "/images/generations")
            post_result = _post_generation(request_payload, endpoint)
        if isinstance(post_result, dict) and post_result.get("ok") is False:
            if tried_b64_first and _is_response_format_unsupported(post_result):
                post_result = _post_generation(dict(payload), endpoint)
            else:
                return post_result

        response = post_result["response"]
        data = post_result["data"]
        used_payload = post_result["payload"]

        image_payload = _extract_image_payload(data)
        saved_path = ""
        output_url = image_payload.get("url", "")
        download_status = "not_needed"
        download_error = ""
        if output_path and image_payload.get("b64_json"):
            path = Path(output_path)
            _save_b64_image(image_payload["b64_json"], path)
            saved_path = str(path)
            download_status = "saved_b64_json"
        elif output_path and image_payload.get("url"):
            path = Path(output_path)
            try:
                _download_image(image_payload["url"], path)
                saved_path = str(path)
                download_status = "downloaded"
            except (requests.RequestException, RuntimeError) as exc:
                download_status = "failed"
                download_error = str(exc)

        return {
            "ok": True,
            "status": "generated_url_download_failed"
            if output_url and download_status == "failed"
            else "done",
            "error": "",
            "error_type": "",
            "error_code": "",
            "provider_error_code": "",
            "error_message": "",
            "exception_type": "",
            "exception_message": "",
            "status_code": response.status_code,
            "raw": data,
            "raw_response": _stringify_raw(data),
            "endpoint": endpoint,
            "model": used_payload["model"],
            "size": used_payload["size"],
            "quality": used_payload["quality"],
            "response_format": used_payload.get("response_format", "url"),
            "download_status": download_status,
            "download_error": download_error,
            "output_path": saved_path,
            "output_url": output_url,
            "b64_json": image_payload.get("b64_json", ""),
        }
    except requests.RequestException as exc:
        return _error(
            "Image generation request error.",
            endpoint=endpoint,
            model=payload["model"],
            size=payload["size"],
            quality=payload["quality"],
            exception=exc,
            error_message=str(exc),
        )
    except OSError as exc:
        return _error(
            "Could not save generated image.",
            endpoint=endpoint,
            model=payload["model"],
            size=payload["size"],
            quality=payload["quality"],
            exception=exc,
            error_code="image_save_failed",
            error_message=str(exc),
        )


def edit_image(
    config: dict[str, Any],
    prompt: str,
    image_path: str | Path | list[str | Path],
    size: str | None = None,
    quality: str | None = None,
    output_path: str | Path | None = None,
) -> dict:
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    if not api_key:
        return _error("API key is missing. Configure Settings or OPENAI_API_KEY.")
    if not base_url:
        return _error("Base URL is missing. Configure Settings or OPENAI_BASE_URL.")

    paths = [Path(item) for item in image_path] if isinstance(image_path, list) else [Path(image_path)]
    missing = [path for path in paths if not path.exists()]
    if missing:
        return _error(f"Reference image not found: {missing[0]}")

    data = {
        "model": config.get("image_model") or "gpt-image-2",
        "prompt": prompt,
        "size": size or config.get("image_size") or "1024x1024",
        "quality": quality or config.get("image_quality") or "low",
    }
    endpoint = _endpoint(base_url, "/images/edits")

    def _post_edit(request_endpoint: str) -> tuple[requests.Response, dict, Exception | None]:
        open_files = [path.open("rb") for path in paths]
        try:
            files = [
                (
                    "image",
                    (
                        path.name,
                        open_files[index],
                        mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    ),
                )
                for index, path in enumerate(paths)
            ]
            response = requests.post(
                request_endpoint,
                headers=_headers(api_key),
                data=data,
                files=files,
                timeout=(30, IMAGE_REQUEST_TIMEOUT_SECONDS),
            )
        finally:
            for file in open_files:
                file.close()
        parse_exception = None
        try:
            body = response.json()
        except ValueError as exc:
            parse_exception = exc
            body = {"text": response.text}
        return response, body, parse_exception

    try:
        response, body, parse_exception = _post_edit(endpoint)
        if response.status_code == 404 and "/v1/" not in endpoint:
            endpoint = _endpoint(_with_v1_base_url(base_url), "/images/edits")
            response, body, parse_exception = _post_edit(endpoint)
        if parse_exception and response.status_code < 400:
            return _error(
                "Image edit response was not valid JSON.",
                endpoint=endpoint,
                model=data["model"],
                size=data["size"],
                quality=data["quality"],
                status_code=response.status_code,
                raw=body,
                response_text=response.text,
                exception=parse_exception,
                error_code="json_parse_error",
                error_message=str(parse_exception),
            )
        if response.status_code >= 400:
            return _error(
                "Image edit request failed.",
                endpoint=endpoint,
                model=data["model"],
                size=data["size"],
                quality=data["quality"],
                status_code=response.status_code,
                raw=body,
                response_text=response.text,
                exception=parse_exception,
            )

        image_payload = _extract_image_payload(body)
        saved_path = ""
        download_status = "not_needed"
        download_error = ""
        if output_path and image_payload.get("b64_json"):
            out = Path(output_path)
            _save_b64_image(image_payload["b64_json"], out)
            saved_path = str(out)
            download_status = "saved_b64_json"
        elif output_path and image_payload.get("url"):
            out = Path(output_path)
            try:
                _download_image(image_payload["url"], out)
                saved_path = str(out)
                download_status = "downloaded"
            except (requests.RequestException, RuntimeError) as exc:
                download_status = "failed"
                download_error = str(exc)

        return {
            "ok": True,
            "status": "generated_url_download_failed"
            if image_payload.get("url") and download_status == "failed"
            else "done",
            "error": "",
            "error_type": "",
            "error_code": "",
            "provider_error_code": "",
            "error_message": "",
            "exception_type": "",
            "exception_message": "",
            "status_code": response.status_code,
            "raw": body,
            "raw_response": _stringify_raw(body),
            "endpoint": endpoint,
            "model": data["model"],
            "size": data["size"],
            "quality": data["quality"],
            "download_status": download_status,
            "download_error": download_error,
            "output_path": saved_path,
            "output_url": image_payload.get("url", ""),
            "b64_json": image_payload.get("b64_json", ""),
        }
    except requests.RequestException as exc:
        return _error(
            "Image edit request error.",
            endpoint=endpoint,
            model=data["model"],
            size=data["size"],
            quality=data["quality"],
            exception=exc,
            error_message=str(exc),
        )
    except OSError as exc:
        return _error(
            "Could not read or save image.",
            endpoint=endpoint,
            model=data["model"],
            size=data["size"],
            quality=data["quality"],
            exception=exc,
            error_code="image_file_error",
            error_message=str(exc),
        )
