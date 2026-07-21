from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
ALLOWED_ENV_FILES = {".env.example"}
SENSITIVE_PATH_PARTS = {
    "cache",
    "db",
    "exports",
    "generated",
    "logs",
    "projects",
    "temp",
    "uploads",
}
CREDENTIAL_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
    )
    return [Path(value.decode("utf-8")) for value in result.stdout.split(b"\0") if value]


def main() -> int:
    failures: list[str] = []
    for relative_path in tracked_files():
        normalized = relative_path.as_posix()
        lowered_parts = {part.lower() for part in relative_path.parts}
        if relative_path.name.startswith(".env") and normalized not in ALLOWED_ENV_FILES:
            failures.append(f"tracked environment file: {normalized}")
        if lowered_parts & SENSITIVE_PATH_PARTS:
            failures.append(f"tracked runtime/user-data path: {normalized}")
        if relative_path.suffix.lower() in {".key", ".pem", ".pfx", ".p12"}:
            failures.append(f"tracked credential file: {normalized}")

        full_path = ROOT_DIR / relative_path
        if not full_path.is_file() or normalized.startswith("tests/"):
            continue
        try:
            content = full_path.read_bytes()
        except OSError as exc:
            failures.append(f"could not scan {normalized}: {exc}")
            continue
        for pattern in CREDENTIAL_PATTERNS:
            if pattern.search(content):
                failures.append(f"credential pattern in tracked file: {normalized}")

    if failures:
        print(f"ERROR: repository hygiene check found {len(set(failures))} blocked tracked item(s).")
        return 1
    print("Repository hygiene check passed: no tracked secrets or runtime user-data paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
