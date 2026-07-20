from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "screenshots"
LOCALES = {
    "zh-CN": "zh-CN-dashboard.png",
    "en": "en-dashboard.png",
    "ja": "ja-dashboard.png",
    "ko": "ko-dashboard.png",
}
EDGE_CANDIDATES = (
    Path(os.environ.get("PROGRAMFILES(X86)", ""))
    / "Microsoft"
    / "Edge"
    / "Application"
    / "msedge.exe",
    Path(os.environ.get("PROGRAMFILES", ""))
    / "Microsoft"
    / "Edge"
    / "Application"
    / "msedge.exe",
)


def find_edge() -> Path:
    command = shutil.which("msedge")
    if command:
        return Path(command).resolve()
    for candidate in EDGE_CANDIDATES:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Microsoft Edge is required to capture release screenshots.")


def save_preferences(server_url: str, locale: str) -> None:
    payload = json.dumps(
        {"current_project_id": "", "language_selection": locale}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{server_url}/settings/ui-preferences",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok") or result.get("data", {}).get("language_selection") != locale:
        raise RuntimeError(f"Could not set the screenshot locale to {locale}.")


def capture(edge: Path, server_url: str, locale: str, output: Path, profile: Path) -> None:
    command = [
        str(edge),
        "--headless=new",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-extensions",
        "--hide-scrollbars",
        "--no-first-run",
        "--force-device-scale-factor=1",
        "--window-size=1600,1000",
        "--virtual-time-budget=7000",
        f"--user-data-dir={profile}",
        f"--screenshot={output}",
        f"{server_url}/#dashboard",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode != 0 or not output.is_file():
        message = (result.stderr or result.stdout or "unknown Edge failure").strip()
        raise RuntimeError(f"Screenshot capture failed for {locale}: {message}")
    with Image.open(output) as image:
        if image.size != (1600, 1000):
            raise RuntimeError(f"Unexpected screenshot size for {locale}: {image.size}")
        colors = image.convert("RGB").resize((80, 50)).getcolors(maxcolors=4000) or []
        if len(colors) < 8:
            raise RuntimeError(f"Screenshot for {locale} appears blank.")


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("Release screenshot capture currently requires Windows.")
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise FileNotFoundError("Build frontend/dist before capturing screenshots.")

    edge = find_edge()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    previous_app_data = os.environ.get("PANELOOM_APP_DATA_DIR")
    previous_projects_home = os.environ.get("PANELOOM_PROJECTS_HOME")
    try:
        with tempfile.TemporaryDirectory(prefix="paneloom-readme-screenshots-") as temporary:
            temp_root = Path(temporary)
            os.environ["PANELOOM_APP_DATA_DIR"] = str(temp_root / "appdata")
            os.environ["PANELOOM_PROJECTS_HOME"] = str(temp_root / "projects")
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from desktop.launcher import LocalDesktopServer, create_desktop_app

            server = LocalDesktopServer(create_desktop_app())
            server.start()
            try:
                for locale, filename in LOCALES.items():
                    save_preferences(server.url, locale)
                    capture(
                        edge,
                        server.url,
                        locale,
                        OUTPUT_DIR / filename,
                        temp_root / f"edge-{locale}",
                    )
                    print(f"Captured {locale}: {OUTPUT_DIR / filename}")
            finally:
                if server.stop():
                    raise RuntimeError("The screenshot server required a forced shutdown.")
    finally:
        if previous_app_data is None:
            os.environ.pop("PANELOOM_APP_DATA_DIR", None)
        else:
            os.environ["PANELOOM_APP_DATA_DIR"] = previous_app_data
        if previous_projects_home is None:
            os.environ.pop("PANELOOM_PROJECTS_HOME", None)
        else:
            os.environ["PANELOOM_PROJECTS_HOME"] = previous_projects_home
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
