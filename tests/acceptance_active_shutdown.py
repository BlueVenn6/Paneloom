import json
import ctypes
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_PYTHON = ROOT / ".desktop-venv" / "Scripts" / "python.exe"


def wait_for_json(
    path: Path,
    key: str,
    timeout: float = 30,
    expected_value: object | None = None,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get(key) and (expected_value is None or data.get(key) == expected_value):
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {key} in {path.name}")


def port_is_closed(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def request_json(url: str, path: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{url}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def close_native_windows(process_id: int) -> int:
    user32 = ctypes.windll.user32
    closed = 0

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        nonlocal closed
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == process_id and user32.IsWindowVisible(hwnd):
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
            closed += 1
        return True

    user32.EnumWindows(callback, 0)
    return closed


def remove_cache_after_process_exit(path: Path, timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            shutil.rmtree(path, ignore_errors=False)
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            time.sleep(0.25)
    return False


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="paneloom-active-shutdown-",
        ignore_cleanup_errors=True,
    ) as directory:
        root = Path(directory)
        provider_state_path = root / "provider-state.json"
        runtime_state_path = root / "runtime-state.json"
        provider = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tests" / "controlled_long_provider.py"),
                "--state",
                str(provider_state_path),
                "--delay",
                "120",
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        launcher = None
        try:
            provider_state = wait_for_json(provider_state_path, "ready")
            env = os.environ.copy()
            env.update(
                {
                    "PANELOOM_APP_DATA_DIR": str(root / "appdata"),
                    "PANELOOM_PROJECTS_HOME": str(root / "projects"),
                    "PANELOOM_SETTINGS_PATH": str(root / "appdata" / "config" / "settings.json"),
                    "PANELOOM_RUNTIME_STATE_PATH": str(runtime_state_path),
                    "PANELOOM_LEGACY_DATA_ROOT": str(root / "nonexistent legacy source"),
                    "OPENAI_PROVIDER_TYPE": "custom",
                    "OPENAI_BASE_URL": f"http://127.0.0.1:{provider_state['port']}/v1",
                    "OPENAI_API_KEY": "controlled-test-key",
                    "IMAGE_MODEL": "controlled-image-model",
                    "IMAGE_SIZE": "64x64",
                    "IMAGE_QUALITY": "low",
                }
            )
            launcher = subprocess.Popen(
                [
                    str(DESKTOP_PYTHON),
                    str(ROOT / "desktop" / "launcher.py"),
                    "--no-single-instance",
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            desktop_ready = wait_for_json(
                runtime_state_path,
                "status",
                timeout=180,
                expected_value="window_ready",
            )
            if desktop_ready.get("status") != "window_ready":
                raise RuntimeError(f"Desktop did not reach ready state: {desktop_ready}")
            url = f"http://127.0.0.1:{desktop_ready['port']}"
            project_response = request_json(
                url,
                "/projects",
                "POST",
                {"name": "Active Shutdown Smoke", "description": "Disposable lifecycle test"},
            )
            project_id = project_response["data"]["project_id"]
            shot_response = request_json(
                url,
                f"/projects/{project_id}/shots",
                "POST",
                {"scene_id": "SMOKE", "prompt": "controlled long request"},
            )
            shot_id = shot_response["data"]["shot_id"]
            job_response = request_json(
                url,
                f"/projects/{project_id}/generate/{shot_id}/job",
                "POST",
                {"size": "64x64", "quality": "low"},
            )
            if not job_response.get("ok"):
                raise RuntimeError("Controlled generation job did not start.")
            provider_final = wait_for_json(provider_state_path, "request_received")

            deadline = time.monotonic() + 15
            reached_generating = False
            while time.monotonic() < deadline:
                shots = request_json(url, f"/projects/{project_id}/shots").get("data", [])
                current = next((item for item in shots if item.get("shot_id") == shot_id), {})
                if current.get("status") == "generating":
                    reached_generating = True
                    break
                time.sleep(0.1)
            windows_closed = close_native_windows(int(desktop_ready["pid"]))
            if windows_closed < 1:
                raise RuntimeError("No native desktop window accepted WM_CLOSE.")
            try:
                stdout, stderr = launcher.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill", "/PID", str(launcher.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                )
                raise TimeoutError("Desktop did not exit within 60 seconds of WM_CLOSE.")
            if launcher.returncode != 0:
                raise RuntimeError(f"Desktop active-task shutdown failed: {stderr or stdout}")
            desktop_result = json.loads(runtime_state_path.read_text(encoding="utf-8"))

            registry = json.loads(
                (root / "appdata" / "registry" / "projects.json").read_text(encoding="utf-8")
            )
            project_paths = list(registry.get("projects", {}).values())
            shots = json.loads((Path(project_paths[0]) / "shots.json").read_text(encoding="utf-8"))
            shot = shots[0]
            temporary_files = list(Path(project_paths[0]).rglob("*.tmp"))
            remote_still_running = provider.poll() is None
            webview_cache_released = remove_cache_after_process_exit(
                root / "appdata" / "cache" / "webview"
            )
            result = {
                "ok": bool(
                    desktop_result.get("status") == "stopped"
                    and desktop_result.get("active_jobs_interrupted") is True
                    and provider_final.get("request_received")
                    and reached_generating
                    and launcher.poll() is not None
                    and port_is_closed(int(desktop_ready["port"]))
                    and shot.get("status") == "failed"
                    and shot.get("generation_error")
                    and not temporary_files
                    and webview_cache_released
                ),
                "desktop_ready": desktop_ready,
                "desktop_stopped": desktop_result,
                "job_started": bool(job_response.get("ok")),
                "shot_reached_generating": reached_generating,
                "native_windows_closed": windows_closed,
                "provider_received_request": bool(provider_final.get("request_received")),
                "provider_path": provider_final.get("path", ""),
                "remote_provider_still_running_after_local_exit": remote_still_running,
                "local_port_released": port_is_closed(int(desktop_ready["port"])),
                "restored_shot_status": shot.get("status", ""),
                "restored_shot_has_error": bool(shot.get("generation_error")),
                "temporary_files": len(temporary_files),
                "webview_cache_released": webview_cache_released,
            }
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1
        finally:
            if launcher and launcher.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(launcher.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                )
            if provider.poll() is None:
                provider.terminate()
                try:
                    provider.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    provider.kill()


if __name__ == "__main__":
    raise SystemExit(main())
