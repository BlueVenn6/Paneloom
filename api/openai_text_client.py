import json
from typing import Any

import requests


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _extract_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else {}
        parts = content.get("parts") if isinstance(content, dict) else []
        if isinstance(parts, list):
            return "\n".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and part.get("text")
            )

    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("text")
            ]
            return "\n".join(parts)

    output = data.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            for content in item.get("content", []) if isinstance(item, dict) else []:
                if isinstance(content, dict) and content.get("text"):
                    parts.append(content["text"])
        if parts:
            return "\n".join(parts)

    return ""


def generate_text(
    config: dict[str, Any],
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model") or config.get("text_model") or "gpt-5.5"
    provider = config.get("provider") or "gpt"
    mode = config.get("mode") or "native"
    if not api_key:
        return {"ok": False, "error": "missing_api_key", "text": ""}
    if not base_url:
        return {"ok": False, "error": "missing_base_url", "text": ""}

    if provider == "google" and mode == "native":
        return _generate_google_native(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    return _generate_chat_compatible(
        api_key=api_key,
        base_url=base_url,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


def generate_text_with_image(
    config: dict[str, Any],
    *,
    system_prompt: str,
    user_prompt: str,
    image_b64: str,
    mime_type: str = "image/png",
    temperature: float = 0.1,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    model = config.get("model") or config.get("text_model") or "gpt-5.5"
    if not api_key:
        return {"ok": False, "error": "missing_api_key", "text": ""}
    if not base_url:
        return {"ok": False, "error": "missing_base_url", "text": ""}
    if config.get("provider") == "google" and config.get("mode") == "native":
        return _generate_google_native(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            image_b64=image_b64,
            mime_type=mime_type,
            max_output_tokens=max_output_tokens,
        )
    return _generate_chat_compatible(
        api_key=api_key,
        base_url=base_url,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        image_b64=image_b64,
        mime_type=mime_type,
        max_output_tokens=max_output_tokens,
    )


def _generate_chat_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    image_b64: str = "",
    mime_type: str = "image/png",
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    endpoint = _endpoint(base_url, "/chat/completions")
    user_content: str | list[dict[str, Any]]
    if image_b64:
        user_content = [
            {"type": "text", "text": user_prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
            },
        ]
    else:
        user_content = user_prompt
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
    }
    if max_output_tokens is not None:
        payload["max_tokens"] = max(1, min(int(max_output_tokens), 4096))

    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text}
        if response.status_code >= 400:
            return {
                "ok": False,
                "error": "text_generation_failed",
                "status_code": response.status_code,
                "raw_response": _stringify(body),
                "text": "",
            }
        return {
            "ok": True,
            "error": "",
            "status_code": response.status_code,
            "raw_response": _stringify(body),
            "text": _extract_text(body),
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": "text_request_error",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "text": "",
        }


def _generate_google_native(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    image_b64: str = "",
    mime_type: str = "image/png",
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    endpoint = _endpoint(base_url, f"/models/{model}:generateContent")
    parts: list[dict[str, Any]] = [{"text": user_prompt}]
    if image_b64:
        parts.append(
            {
                "inlineData": {
                    "mimeType": mime_type,
                    "data": image_b64,
                }
            }
        )
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": temperature},
    }
    if max_output_tokens is not None:
        payload["generationConfig"]["maxOutputTokens"] = max(
            1, min(int(max_output_tokens), 4096)
        )
    try:
        response = requests.post(
            f"{endpoint}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text}
        if response.status_code >= 400:
            return {
                "ok": False,
                "error": "text_generation_failed",
                "status_code": response.status_code,
                "raw_response": _stringify(body),
                "text": "",
            }
        return {
            "ok": True,
            "error": "",
            "status_code": response.status_code,
            "raw_response": _stringify(body),
            "text": _extract_text(body),
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": "text_request_error",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "text": "",
        }
