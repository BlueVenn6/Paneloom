import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles


_PROCESS_STARTED_MONOTONIC = time.monotonic()
ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
DESKTOP_ICON = ROOT_DIR / "desktop" / "resources" / "paneloom.ico"
MUTEX_NAME = "Local\\PaneloomDesktopSingleInstance"
ERROR_ALREADY_EXISTS = 183
_HARD_EXIT_REQUIRED = False


class SingleInstanceError(RuntimeError):
    pass


class WindowsSingleInstance:
    def __init__(self, name: str = MUTEX_NAME):
        self._handle = None
        if os.name != "nt":
            return
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError()
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            raise SingleInstanceError("Paneloom is already running.")
        self._handle = handle

    def close(self) -> None:
        if self._handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def create_desktop_app():
    if not FRONTEND_DIST.joinpath("index.html").exists():
        raise FileNotFoundError(
            "The React production build is missing. Run the developer build before desktop validation."
        )
    os.environ["PANELOOM_DESKTOP"] = "1"
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from backend.main import app

    if not getattr(app.state, "desktop_frontend_mounted", False):
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="desktop-ui")
        app.state.desktop_frontend_mounted = True
    return app


class LocalDesktopServer:
    def __init__(self, app, port: int = 0):
        self.port = port or _free_loopback_port()
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning",
                access_log=False,
            )
        )
        self.thread = threading.Thread(
            target=self.server.run,
            name="paneloom-local-api",
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 15.0) -> None:
        self.thread.start()
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            if not self.thread.is_alive():
                raise RuntimeError("The local desktop service exited during startup.")
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except OSError as exc:
                last_error = exc
                time.sleep(0.1)
        self.stop()
        raise TimeoutError(f"The local desktop service did not become ready: {last_error}")

    def stop(self, timeout: float = 10.0) -> bool:
        """Stop the local server and report whether an in-flight request required force-exit."""
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(min(timeout, 5.0))
        if self.thread.is_alive():
            self.server.force_exit = True
            self.thread.join(max(0.5, timeout - 5.0))
            return True
        return False


def runtime_smoke(port: int = 0) -> dict:
    server = LocalDesktopServer(create_desktop_app(), port=port)
    server.start()
    try:
        with urllib.request.urlopen(f"{server.url}/health", timeout=3) as response:
            health = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(f"{server.url}/", timeout=3) as response:
            index_ok = response.status == 200 and b'id="root"' in response.read()
        return {
            "ok": health.get("ok") is True and index_ok,
            "host": "127.0.0.1",
            "port": server.port,
            "health": health,
            "frontend_served": index_ok,
        }
    finally:
        server.stop()


def run_window(port: int = 0) -> None:
    global _HARD_EXIT_REQUIRED
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is not installed. Install desktop/requirements.txt for prototype validation."
        ) from exc

    app = create_desktop_app()
    from backend.app.config import APP_CACHE_DIR, APP_LOG_DIR

    server = LocalDesktopServer(app, port=port)
    server.start()
    _write_runtime_state("ready", server.port)
    try:
        test_mode = os.getenv("PANELOOM_DESKTOP_TEST", "").strip() == "1"
        diagnostic_query = "?desktop-test=1" if test_mode else ""
        frontend_log_path = APP_LOG_DIR / "frontend-runtime.log"
        window = webview.create_window(
            "Paneloom",
            f"{server.url}/{diagnostic_query}#dashboard",
            width=1440,
            height=920,
            min_size=(1024, 700),
        )
        window.events.shown += lambda: _write_runtime_state("window_ready", server.port)
        webview.start(
            _monitor_frontend_runtime if test_mode else None,
            (window, frontend_log_path) if test_mode else None,
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(APP_CACHE_DIR / "webview"),
            icon=str(DESKTOP_ICON),
        )
    finally:
        forced_server_shutdown = server.stop()
        from backend.app.routes.generation import interrupt_active_jobs_for_desktop_shutdown
        from backend.app.services.shotlist_service import recover_interrupted_generation_states

        active_jobs_interrupted = interrupt_active_jobs_for_desktop_shutdown()
        if forced_server_shutdown and not active_jobs_interrupted:
            recover_interrupted_generation_states()
        _HARD_EXIT_REQUIRED = forced_server_shutdown or active_jobs_interrupted
        _write_runtime_state(
            "stopped",
            server.port,
            active_jobs_interrupted=_HARD_EXIT_REQUIRED,
            forced_server_shutdown=forced_server_shutdown,
        )
        # Edge WebView2 can retain cache workers after a normal window close.
        # The window and API server are already stopped, so exit this launcher
        # process explicitly to preserve the desktop zero-residual-process contract.
        _HARD_EXIT_REQUIRED = True


def _monitor_frontend_runtime(window, log_path: Path) -> None:
    """Persist sanitized browser errors only while the desktop acceptance mode is enabled."""
    seen = 0
    root_missing_recorded = False
    consecutive_failures = 0
    while True:
        try:
            state = window.evaluate_js(
                """
                (() => ({
                  url: window.location.href,
                  readyState: document.readyState,
                  rootMounted: window.__PANELOOM_REACT_ROOT_MOUNTED__ === true,
                  rootChildren: document.querySelector('#root')?.children.length || 0,
                  navCount: document.querySelectorAll('.nav-item').length,
                  entries: window.__PANELOOM_RUNTIME_DIAGNOSTICS__?.snapshot?.() || [],
                }))()
                """
            ) or {}
            consecutive_failures = 0
            entries = list(state.get("entries") or [])
            new_entries = entries[seen:]
            seen = len(entries)
            if new_entries:
                for entry in new_entries:
                    _append_frontend_diagnostic(log_path, entry)
            root_missing = (
                state.get("readyState") == "complete"
                and state.get("rootMounted") is True
                and state.get("rootChildren") == 0
            )
            if root_missing and not root_missing_recorded:
                _append_frontend_diagnostic(
                    log_path,
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "kind": "react.root.empty",
                        "message": "React root has no rendered children.",
                        "route": str(state.get("url") or "").split("#", 1)[-1],
                    },
                )
                root_missing_recorded = True
            elif not root_missing:
                root_missing_recorded = False
            time.sleep(0.5)
        except Exception:
            consecutive_failures += 1
            if consecutive_failures >= 20:
                return
            time.sleep(0.25)


def _append_frontend_diagnostic(log_path: Path, entry: dict) -> None:
    allowed = {
        key: entry.get(key)
        for key in ("timestamp", "kind", "message", "stack", "source", "line", "column", "route")
        if entry.get(key) not in (None, "")
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(allowed, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _write_runtime_state(status: str, port: int, **details) -> None:
    state_path = os.getenv("PANELOOM_RUNTIME_STATE_PATH", "").strip()
    if not state_path:
        return
    path = Path(state_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "status": status,
                "pid": os.getpid(),
                "host": "127.0.0.1",
                "port": port,
                **details,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _all_requests_use_runtime_origin(
    requests: list[str], runtime_origin: str, server_url: str
) -> bool:
    runtime_prefix = f"{server_url}/"
    return bool(
        requests
        and all(url.startswith(runtime_prefix) for url in requests)
        and runtime_origin == server_url
    )


def window_smoke(port: int = 0) -> dict:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("pywebview is not installed for native window validation.") from exc

    def elapsed() -> float:
        return round(time.monotonic() - _PROCESS_STARTED_MONOTONIC, 3)

    timeline = {"t0_launcher_started": 0.0, "t1_backend_starting": elapsed()}
    app = create_desktop_app()
    from backend.app.config import APP_CACHE_DIR

    server = LocalDesktopServer(app, port=port)
    server.start()
    timeline["t2_backend_ready"] = elapsed()
    result = {
        "loaded": False,
        "root_rendered": False,
        "interactive": False,
        "url": "",
        "runtime_origin": "",
        "api_base_text": "",
        "api_requests": [],
        "all_api_requests_use_runtime_origin": False,
        "interaction_hash": "",
        "error": "",
    }
    completed = threading.Event()
    window = webview.create_window(
        "Paneloom Desktop Smoke",
        f"{server.url}/#dashboard",
        width=1100,
        height=760,
        min_size=(900, 600),
    )

    def shown_window() -> None:
        timeline.setdefault("t3_window_shown", elapsed())

    def closed_window() -> None:
        timeline.setdefault("t7_webview_closed", elapsed())

    def loaded_window() -> None:
        try:
            result["loaded"] = True
            result["url"] = str(window.get_current_url() or "")
            deadline = time.monotonic() + 15
            ui_state = {}
            while time.monotonic() < deadline:
                ui_state = window.evaluate_js(
                    """
                    (() => ({
                      rootRendered: Boolean(document.querySelector('#root')?.children.length),
                      backendOnline: Boolean(document.querySelector('.status-pill.online')),
                      apiBaseText: document.querySelector('.status-pill')?.parentElement?.querySelector('code')?.textContent || '',
                      navReady: document.querySelectorAll('.nav-item').length >= 5,
                      origin: window.location.origin,
                      requests: performance.getEntriesByType('resource')
                        .map((entry) => entry.name)
                        .filter((url) => url.includes('/health') || url.includes('/projects')),
                    }))()
                    """
                ) or {}
                if (
                    ui_state.get("rootRendered")
                    and ui_state.get("backendOnline")
                    and ui_state.get("navReady")
                    and any(url.endswith("/projects") for url in ui_state.get("requests", []))
                ):
                    break
                time.sleep(0.1)

            result["root_rendered"] = bool(ui_state.get("rootRendered"))
            timeline["t4_react_first_render"] = elapsed()
            result["runtime_origin"] = str(ui_state.get("origin") or "")
            result["api_base_text"] = str(ui_state.get("apiBaseText") or "")
            result["api_requests"] = list(ui_state.get("requests") or [])
            result["all_api_requests_use_runtime_origin"] = _all_requests_use_runtime_origin(
                result["api_requests"], result["runtime_origin"], server.url
            )

            clicked = bool(
                window.evaluate_js(
                    """
                    (() => {
                      const button = document.querySelectorAll('.nav-item')[1];
                      if (!button) return false;
                      button.click();
                      return true;
                    })()
                    """
                )
            )
            interaction_deadline = time.monotonic() + 5
            while clicked and time.monotonic() < interaction_deadline:
                result["interaction_hash"] = str(
                    window.evaluate_js("window.location.hash") or ""
                )
                if result["interaction_hash"] == "#projects":
                    break
                time.sleep(0.05)
            result["interactive"] = bool(
                clicked
                and result["interaction_hash"] == "#projects"
                and result["all_api_requests_use_runtime_origin"]
            )
            timeline["t5_ui_interactive"] = elapsed()
        except Exception as exc:  # pywebview surfaces browser failures as runtime exceptions.
            result["error"] = str(exc)
        finally:
            timeline["t6_close_requested"] = elapsed()
            completed.set()
            window.destroy()

    window.events.shown += shown_window
    window.events.loaded += loaded_window
    window.events.closed += closed_window

    def watchdog() -> None:
        if not completed.wait(timeout=60):
            window.destroy()

    try:
        webview.start(
            watchdog,
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(APP_CACHE_DIR / "webview-smoke"),
            icon=str(DESKTOP_ICON),
        )
        timeline.setdefault("t7_webview_closed", elapsed())
    finally:
        server.stop()
        timeline["t8_backend_stopped"] = elapsed()
    return {
        "ok": bool(
            result["loaded"]
            and result["root_rendered"]
            and result["interactive"]
            and result["all_api_requests_use_runtime_origin"]
        ),
        "host": "127.0.0.1",
        "port": server.port,
        "window_loaded": result["loaded"],
        "react_root_rendered": result["root_rendered"],
        "ui_interactive": result["interactive"],
        "url": result["url"],
        "runtime_origin": result["runtime_origin"],
        "api_base_text": result["api_base_text"],
        "api_requests": result["api_requests"],
        "all_api_requests_use_runtime_origin": result["all_api_requests_use_runtime_origin"],
        "interaction_hash": result["interaction_hash"],
        "error": result["error"],
        "timeline_seconds": timeline,
        "server_stopped": not server.thread.is_alive(),
    }


def main() -> int:
    global _HARD_EXIT_REQUIRED
    parser = argparse.ArgumentParser(description="Paneloom local desktop runtime prototype")
    parser.add_argument("--runtime-smoke", action="store_true")
    parser.add_argument("--window-smoke", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-single-instance", action="store_true")
    args = parser.parse_args()
    instance = None
    try:
        if not args.no_single_instance:
            instance = WindowsSingleInstance()
        if args.window_smoke:
            result = window_smoke(args.port)
            print(json.dumps(result, ensure_ascii=False))
            if not result["ok"]:
                raise RuntimeError("The production desktop window did not render the React application.")
            # WebView2 can retain non-daemon cache workers after the test window closes.
            # The server and window are already stopped; force only this smoke process to exit.
            _HARD_EXIT_REQUIRED = True
        elif args.runtime_smoke:
            print(json.dumps(runtime_smoke(args.port), ensure_ascii=False))
        else:
            run_window(args.port)
        return 0
    except (FileNotFoundError, RuntimeError, TimeoutError, OSError) as exc:
        message = f"Paneloom desktop startup failed: {exc}"
        print(message, file=sys.stderr)
        _record_startup_failure(message)
        if (
            not args.runtime_smoke
            and not args.window_smoke
            and os.name == "nt"
        ):
            ctypes.windll.user32.MessageBoxW(None, message, "Paneloom", 0x10)
        return 1
    finally:
        if instance:
            instance.close()


def _record_startup_failure(message: str) -> None:
    app_data = Path(
        os.getenv(
            "PANELOOM_APP_DATA_DIR",
            str(Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Paneloom"),
        )
    )
    log_path = app_data / "logs" / "desktop-startup.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as file:
            file.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
    except OSError:
        pass


if __name__ == "__main__":
    exit_code = main()
    if _HARD_EXIT_REQUIRED:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
    raise SystemExit(exit_code)
