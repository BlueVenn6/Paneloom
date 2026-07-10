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


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
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

    def stop(self, timeout: float = 10.0) -> None:
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout)
        if self.thread.is_alive():
            raise RuntimeError("The local desktop service did not stop cleanly.")


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
    from backend.app.config import APP_CACHE_DIR

    server = LocalDesktopServer(app, port=port)
    server.start()
    _write_runtime_state("ready", server.port)
    try:
        window = webview.create_window(
            "Paneloom",
            f"{server.url}/#dashboard",
            width=1440,
            height=920,
            min_size=(1024, 700),
        )
        window.events.shown += lambda: _write_runtime_state("window_ready", server.port)
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(APP_CACHE_DIR / "webview"),
        )
    finally:
        server.stop()
        from backend.app.routes.generation import interrupt_active_jobs_for_desktop_shutdown

        _HARD_EXIT_REQUIRED = interrupt_active_jobs_for_desktop_shutdown()
        _write_runtime_state("stopped", server.port, active_jobs_interrupted=_HARD_EXIT_REQUIRED)


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


def window_smoke(port: int = 0) -> dict:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("pywebview is not installed for native window validation.") from exc

    app = create_desktop_app()
    from backend.app.config import APP_CACHE_DIR

    server = LocalDesktopServer(app, port=port)
    server.start()
    result = {"loaded": False, "root_rendered": False, "url": ""}
    completed = threading.Event()
    window = webview.create_window(
        "Paneloom Desktop Smoke",
        f"{server.url}/#dashboard",
        width=1100,
        height=760,
        min_size=(900, 600),
    )

    def loaded_window() -> None:
        try:
            result["loaded"] = True
            result["root_rendered"] = bool(
                window.evaluate_js(
                    "Boolean(document.querySelector('#root') && document.querySelector('#root').children.length)"
                )
            )
            result["url"] = str(window.get_current_url() or "")
        finally:
            completed.set()
            window.destroy()

    window.events.loaded += loaded_window

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
        )
    finally:
        server.stop()
    return {
        "ok": bool(result["loaded"] and result["root_rendered"]),
        "host": "127.0.0.1",
        "port": server.port,
        "window_loaded": result["loaded"],
        "react_root_rendered": result["root_rendered"],
        "url": result["url"],
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
