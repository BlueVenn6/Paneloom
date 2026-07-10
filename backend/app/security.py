import base64
import ctypes
import os
import re
from ctypes import wintypes
from typing import Any


DPAPI_PREFIX = "dpapi:v1:"
_TOKEN_PATTERNS = [
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9*._-]{6,}"),
    re.compile(r'(?i)(["\']?(?:api[_-]?key|access[_-]?token)["\']?\s*[:=]\s*["\']?)[^\s,;"\']{6,}'),
    re.compile(r"(?i)([?&]key=)[^&\s]{6,}"),
]


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _require_windows() -> None:
    if os.name != "nt":
        raise OSError("Windows DPAPI is required for local API key storage.")


def protect_secret(secret: str) -> str:
    if not secret:
        return ""
    if secret.startswith(DPAPI_PREFIX):
        return secret
    _require_windows()
    raw = secret.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw)
    input_blob = _DataBlob(
        len(raw),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "Paneloom local API credential",
        None,
        None,
        None,
        0x01,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
    return f"{DPAPI_PREFIX}{base64.b64encode(encrypted).decode('ascii')}"


def unprotect_secret(value: str) -> str:
    if not value:
        return ""
    if not value.startswith(DPAPI_PREFIX):
        raise ValueError("Unsupported encrypted credential format.")
    _require_windows()
    try:
        encrypted = base64.b64decode(value[len(DPAPI_PREFIX) :], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Encrypted credential data is invalid.") from exc
    buffer = ctypes.create_string_buffer(encrypted)
    input_blob = _DataBlob(
        len(encrypted),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0x01,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        raw = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
    return raw.decode("utf-8")


def redact_sensitive_text(value: object, secrets: list[str] | None = None) -> str:
    text = "" if value is None else str(value)
    for secret in sorted({item for item in secrets or [] if len(item) >= 4}, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    for pattern in _TOKEN_PATTERNS:
        if pattern.groups:
            text = pattern.sub(r"\1[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


def redact_sensitive_value(value: Any, secrets: list[str] | None = None) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if str(key).lower() in {"api_key", "text_api_key", "access_token", "authorization"}
            else redact_sensitive_value(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_value(item, secrets) for item in value)
    if isinstance(value, str):
        return redact_sensitive_text(value, secrets)
    return value
