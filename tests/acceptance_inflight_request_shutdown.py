import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from acceptance_active_shutdown import (
    DESKTOP_PYTHON,
    ROOT,
    close_native_windows,
    port_is_closed,
    request_json,
    wait_for_json,
)


def start_launcher(root: Path, runtime_state: Path, provider_port: int):
    runtime_state.unlink(missing_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PANELOOM_APP_DATA_DIR": str(root / "appdata"),
            "PANELOOM_PROJECTS_HOME": str(root / "projects"),
            "PANELOOM_DESKTOP_TEST_ROOT": str(root),
            "PANELOOM_SETTINGS_PATH": str(root / "appdata" / "config" / "settings.json"),
            "PANELOOM_RUNTIME_STATE_PATH": str(runtime_state),
            "PANELOOM_LEGACY_DATA_ROOT": str(root / "nonexistent legacy source"),
            "OPENAI_PROVIDER_TYPE": "custom",
            "OPENAI_BASE_URL": f"http://127.0.0.1:{provider_port}/v1",
            "OPENAI_API_KEY": "controlled-test-key",
            "IMAGE_MODEL": "controlled-image-model",
            "IMAGE_SIZE": "64x64",
            "IMAGE_QUALITY": "low",
        }
    )
    process = subprocess.Popen(
        [str(DESKTOP_PYTHON), str(ROOT / "desktop" / "launcher.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready = wait_for_json(runtime_state, "status", timeout=180, expected_value="window_ready")
    return process, ready


def stop_launcher(process, ready: dict, timeout: float = 60) -> tuple[int, str, str, float]:
    started = time.monotonic()
    if close_native_windows(int(ready["pid"])) < 1:
        raise RuntimeError("No native window accepted WM_CLOSE.")
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
        )
        raise TimeoutError("Launcher did not exit while a backend request was in flight.")
    return process.returncode, stdout, stderr, round(time.monotonic() - started, 3)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="paneloom-inflight-shutdown-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        provider_state = root / "provider.json"
        provider = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tests" / "controlled_long_provider.py"),
                "--state",
                str(provider_state),
                "--delay",
                "120",
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        first = None
        second = None
        try:
            provider_ready = wait_for_json(provider_state, "ready", timeout=30)
            first, ready = start_launcher(root, root / "runtime-1.json", int(provider_ready["port"]))
            url = f"http://127.0.0.1:{ready['port']}"
            project = request_json(
                url,
                "/projects",
                "POST",
                {"name": "In-flight Request", "parent_directory": str(root / "projects")},
            )["data"]
            shot = request_json(
                url,
                f"/projects/{project['project_id']}/shots",
                "POST",
                {"scene_id": "LONG", "prompt": "controlled synchronous request"},
            )["data"]
            client_result = {}

            def run_request():
                try:
                    client_result["response"] = request_json(
                        url,
                        f"/projects/{project['project_id']}/generate/{shot['shot_id']}",
                        "POST",
                        {"size": "64x64", "quality": "low"},
                    )
                except Exception as exc:  # The local connection is expected to terminate on close.
                    client_result["error"] = type(exc).__name__

            client = threading.Thread(target=run_request, daemon=True)
            client.start()
            wait_for_json(provider_state, "request_received", timeout=30)
            status_before = request_json(
                url,
                f"/projects/{project['project_id']}/shots",
            )["data"][0]["status"]
            return_code, stdout, stderr, shutdown_seconds = stop_launcher(first, ready)
            first = None
            client.join(timeout=10)
            port_released = port_is_closed(int(ready["port"]))

            second, ready_2 = start_launcher(root, root / "runtime-2.json", int(provider_ready["port"]))
            url_2 = f"http://127.0.0.1:{ready_2['port']}"
            recovered_shot = request_json(
                url_2,
                f"/projects/{project['project_id']}/shots",
            )["data"][0]
            second_code, second_stdout, second_stderr, second_shutdown = stop_launcher(second, ready_2)
            second = None

            result = {
                "ok": bool(
                    status_before == "generating"
                    and return_code == 0
                    and port_released
                    and recovered_shot.get("status") == "failed"
                    and recovered_shot.get("generation_error")
                    and second_code == 0
                    and port_is_closed(int(ready_2["port"]))
                ),
                "request_reached_provider": True,
                "status_before_close": status_before,
                "first_exit_code": return_code,
                "first_exit_error": stderr or stdout,
                "shutdown_seconds": shutdown_seconds,
                "client_thread_finished": not client.is_alive(),
                "client_result": client_result,
                "port_released": port_released,
                "restart_status": recovered_shot.get("status"),
                "restart_has_error": bool(recovered_shot.get("generation_error")),
                "second_exit_code": second_code,
                "second_exit_error": second_stderr or second_stdout,
                "second_shutdown_seconds": second_shutdown,
                "second_port_released": port_is_closed(int(ready_2["port"])),
                "remote_provider_still_running": provider.poll() is None,
            }
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1
        finally:
            for process in (first, second):
                if process and process.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        text=True,
                    )
            if provider.poll() is None:
                provider.terminate()
                try:
                    provider.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    provider.kill()


if __name__ == "__main__":
    raise SystemExit(main())
