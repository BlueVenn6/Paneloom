import os
from pathlib import Path
from threading import RLock

_APPROVED_PATHS: dict[tuple[str, str], Path] = {}
_APPROVAL_LOCK = RLock()
_VALID_KINDS = {"folder", "backup"}


def _canonical_path(value: str | Path) -> Path:
    return Path(os.path.realpath(os.path.expanduser(os.fspath(value))))


def approve_desktop_path(value: str | Path, kind: str) -> str:
    """Remember a path returned by a native desktop file dialog."""
    if kind not in _VALID_KINDS:
        raise ValueError("Unsupported desktop path approval type.")
    path = _canonical_path(value)
    if kind == "folder" and not path.is_dir():
        raise FileNotFoundError("The selected folder no longer exists.")
    if kind == "backup" and not path.is_file():
        raise FileNotFoundError("The selected backup no longer exists.")
    with _APPROVAL_LOCK:
        _APPROVED_PATHS[(kind, os.path.normcase(os.fspath(path)))] = path
    return str(path)


def require_approved_desktop_path(
    value: str,
    kind: str,
    *,
    default: str | Path | None = None,
) -> str:
    """Resolve only paths approved by the native dialog or a controlled test root."""
    if kind not in _VALID_KINDS:
        raise ValueError("Unsupported desktop path approval type.")
    if not str(value or "").strip():
        return str(_canonical_path(default)) if default is not None else ""

    requested_text = os.path.realpath(os.path.expanduser(os.fspath(value)))
    requested = Path(requested_text)
    key = (kind, os.path.normcase(os.fspath(requested)))
    with _APPROVAL_LOCK:
        approved = _APPROVED_PATHS.get(key)
    if approved is not None:
        return str(approved)

    if default is not None:
        approved_default = _canonical_path(default)
        if os.path.normcase(os.fspath(requested)) == os.path.normcase(os.fspath(approved_default)):
            return str(approved_default)

    test_root_value = os.getenv("PANELOOM_DESKTOP_TEST_ROOT", "").strip()
    if test_root_value:
        full_path = os.path.normpath(requested_text)
        test_root_text = os.path.normpath(os.path.realpath(os.path.expanduser(test_root_value)))
        test_root_prefix = test_root_text.rstrip("\\/") + os.sep
        if not full_path.startswith(test_root_prefix):
            raise PermissionError("The test path is outside the controlled desktop test root.")
        if kind == "backup" and not Path(full_path).is_file():
            raise FileNotFoundError("The selected backup no longer exists.")
        return full_path

    raise PermissionError(
        "For safety, select this path with Paneloom's Windows file or folder picker."
    )
