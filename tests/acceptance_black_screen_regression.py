from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from desktop.launcher import LocalDesktopServer, create_desktop_app
from backend.app.config import APP_CACHE_DIR


ROUTES = ("dashboard", "projects", "storyboard", "schedule", "settings")


def run_regression(iterations: int) -> dict:
    import webview

    server = LocalDesktopServer(create_desktop_app())
    server.start()
    completed = threading.Event()
    result: dict = {
        "ok": False,
        "iterations": iterations,
        "url": "",
        "routes": [],
        "diagnostics": [],
        "static_asset_failures": [],
        "project_switch": {},
        "controlled_fetch_failure": {},
        "offline_ui": {},
        "page_failure_recovery": {},
        "global_failure_recovery": {},
        "window_transitions": [],
        "error": "",
    }
    window = webview.create_window(
        "Paneloom Black Screen Regression",
        f"{server.url}/?desktop-test=1#dashboard",
        width=1200,
        height=800,
        min_size=(1024, 700),
    )

    def snapshot() -> dict:
        return window.evaluate_js(
            r"""
            (() => ({
              url: window.location.href,
              readyState: document.readyState,
              rootMountedFlag: window.__PANELOOM_REACT_ROOT_MOUNTED__ === true,
              rootChildren: document.querySelector('#root')?.children.length || 0,
              navCount: document.querySelectorAll('.nav-item').length,
              diagnostics: window.__PANELOOM_RUNTIME_DIAGNOSTICS__?.snapshot?.() || [],
              staticAssetFailures: performance.getEntriesByType('resource')
                .filter((entry) => entry.name.includes('/assets/') && entry.duration === 0)
                .map((entry) => entry.name),
              mainBundleLoaded: performance.getEntriesByType('resource')
                .some((entry) => /\/assets\/index-[^/]+\.js/.test(entry.name)),
              cssLoaded: performance.getEntriesByType('resource')
                .some((entry) => /\/assets\/index-[^/]+\.css/.test(entry.name)),
              errorFallbackVisible: Boolean(document.querySelector('.error-fallback')),
              offlineAlertVisible: Boolean(document.querySelector('.main-panel > .alert')),
            }))()
            """
        ) or {}

    def run_checks() -> None:
        try:
            deadline = time.monotonic() + 15
            state = {}
            while time.monotonic() < deadline:
                state = snapshot()
                if state.get("navCount") == 5:
                    break
                time.sleep(0.1)
            result["url"] = str(window.get_current_url() or "")
            for iteration in range(iterations):
                for route in ROUTES:
                    clicked = window.evaluate_js(
                        f"document.querySelector('[data-page=\"{route}\"]')?.click(); true"
                    )
                    time.sleep(0.25)
                    state = snapshot()
                    result["routes"].append(
                        {
                            "iteration": iteration + 1,
                            "route": route,
                            "clicked": bool(clicked),
                            "hash": str(window.evaluate_js("window.location.hash") or ""),
                            "ready_state": state.get("readyState"),
                            "root_mounted": state.get("rootMountedFlag"),
                            "root_children": state.get("rootChildren"),
                            "nav_count": state.get("navCount"),
                        }
                    )
                    if state.get("navCount") != 5 or state.get("rootChildren", 0) == 0:
                        result["diagnostics"] = state.get("diagnostics") or []
                        result["static_asset_failures"] = state.get("staticAssetFailures") or []
                        result["main_bundle_loaded"] = bool(state.get("mainBundleLoaded"))
                        result["css_loaded"] = bool(state.get("cssLoaded"))
                        return
                window.maximize()
                time.sleep(0.1)
                window.restore()
                time.sleep(0.1)
                window.minimize()
                time.sleep(0.1)
                window.restore()
                result["window_transitions"].append({"iteration": iteration + 1, "ok": True})

            project_switch = window.evaluate_js(
                """
                (() => {
                  const select = document.querySelector('.project-picker select');
                  if (!select || select.options.length < 3) return { attempted: false };
                  const before = select.value;
                  const after = [...select.options].map((item) => item.value)
                    .find((value) => value && value !== before);
                  select.value = after;
                  select.dispatchEvent(new Event('change', { bubbles: true }));
                  return { attempted: true, before, after };
                })()
                """
            ) or {}
            time.sleep(0.5)
            project_state = snapshot()
            project_switch.update(
                {
                    "root_children": project_state.get("rootChildren"),
                    "nav_count": project_state.get("navCount"),
                }
            )
            result["project_switch"] = project_switch

            fetch_setup = window.evaluate_js(
                """
                (() => {
                  window.__PANELOOM_ORIGINAL_FETCH__ = window.fetch;
                  window.fetch = () => Promise.reject(new TypeError('Controlled offline request failure'));
                  const select = document.querySelector('.project-picker select');
                  if (!select || select.options.length < 3) return false;
                  const next = [...select.options].map((item) => item.value)
                    .find((value) => value && value !== select.value);
                  select.value = next;
                  select.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                })()
                """
            )
            time.sleep(0.5)
            fetch_state = snapshot()
            window.evaluate_js(
                "window.fetch = window.__PANELOOM_ORIGINAL_FETCH__; delete window.__PANELOOM_ORIGINAL_FETCH__;"
            )
            result["controlled_fetch_failure"] = {
                "attempted": bool(fetch_setup),
                "root_children": fetch_state.get("rootChildren"),
                "nav_count": fetch_state.get("navCount"),
                "diagnostic_count": len(fetch_state.get("diagnostics") or []),
            }

            window.evaluate_js(
                """
                Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false });
                window.dispatchEvent(new Event('offline'));
                """
            )
            time.sleep(0.2)
            offline_state = snapshot()
            window.evaluate_js(
                """
                Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => true });
                window.dispatchEvent(new Event('online'));
                """
            )
            result["offline_ui"] = {
                "root_children": offline_state.get("rootChildren"),
                "nav_count": offline_state.get("navCount"),
                "alert_visible": bool(offline_state.get("offlineAlertVisible")),
            }

            boundary_triggered = window.evaluate_js(
                "window.__PANELOOM_TRIGGER_PAGE_ERROR__?.(); true"
            )
            time.sleep(0.3)
            failure_state = snapshot()
            returned = window.evaluate_js(
                "document.querySelector('.error-fallback .secondary')?.click(); true"
            )
            time.sleep(0.3)
            recovered_state = snapshot()
            result["page_failure_recovery"] = {
                "triggered": bool(boundary_triggered),
                "fallback_visible": bool(failure_state.get("errorFallbackVisible")),
                "nav_preserved": failure_state.get("navCount") == 5,
                "return_clicked": bool(returned),
                "recovered_hash": str(window.evaluate_js("window.location.hash") or ""),
                "recovered_root_children": recovered_state.get("rootChildren"),
                "recovered_nav_count": recovered_state.get("navCount"),
            }

            page_diagnostics = failure_state.get("diagnostics") or []
            global_triggered = window.evaluate_js(
                "window.__PANELOOM_TRIGGER_GLOBAL_ERROR__?.(); true"
            )
            time.sleep(0.3)
            global_failure_state = snapshot()
            global_returned = window.evaluate_js(
                "document.querySelector('.global-error-fallback .secondary')?.click(); true"
            )
            recovery_deadline = time.monotonic() + 15
            global_recovered_state = {}
            while time.monotonic() < recovery_deadline:
                time.sleep(0.2)
                global_recovered_state = snapshot()
                if global_recovered_state.get("navCount") == 5:
                    break
            result["global_failure_recovery"] = {
                "triggered": bool(global_triggered),
                "fallback_visible": bool(global_failure_state.get("errorFallbackVisible")),
                "return_clicked": bool(global_returned),
                "recovered_hash": str(window.evaluate_js("window.location.hash") or ""),
                "recovered_root_children": global_recovered_state.get("rootChildren"),
                "recovered_nav_count": global_recovered_state.get("navCount"),
            }
            final = snapshot()
            result["diagnostics"] = page_diagnostics + (global_failure_state.get("diagnostics") or [])
            result["static_asset_failures"] = final.get("staticAssetFailures") or []
            result["main_bundle_loaded"] = bool(final.get("mainBundleLoaded"))
            result["css_loaded"] = bool(final.get("cssLoaded"))
            unexpected_diagnostics = [
                entry
                for entry in result["diagnostics"]
                if not any(
                    marker in str(entry.get("message", ""))
                    for marker in (
                        "Controlled page render failure",
                        "Controlled global render failure",
                    )
                )
            ]
            result["ok"] = not unexpected_diagnostics and all(
                item["root_children"] > 0 and item["nav_count"] == 5
                for item in result["routes"]
            ) and all(
                (
                    result["project_switch"].get("root_children", 0) > 0,
                    result["project_switch"].get("nav_count") == 5,
                    result["controlled_fetch_failure"].get("root_children", 0) > 0,
                    result["controlled_fetch_failure"].get("nav_count") == 5,
                    result["offline_ui"].get("alert_visible") is True,
                    result["page_failure_recovery"].get("fallback_visible") is True,
                    result["page_failure_recovery"].get("nav_preserved") is True,
                    result["page_failure_recovery"].get("recovered_hash") == "#dashboard",
                    result["page_failure_recovery"].get("recovered_nav_count") == 5,
                    result["global_failure_recovery"].get("fallback_visible") is True,
                    result["global_failure_recovery"].get("recovered_hash") == "#dashboard",
                    result["global_failure_recovery"].get("recovered_nav_count") == 5,
                )
            )
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            completed.set()
            window.destroy()

    checks_started = threading.Event()

    def loaded() -> None:
        if checks_started.is_set():
            return
        checks_started.set()
        threading.Thread(target=run_checks, name="paneloom-route-regression", daemon=True).start()

    window.events.loaded += loaded

    def watchdog() -> None:
        if not completed.wait(300):
            result["error"] = "WebView regression watchdog timed out."
            window.destroy()

    try:
        webview.start(
            watchdog,
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(APP_CACHE_DIR / "webview-black-screen-regression"),
        )
    finally:
        server.stop()
    result["server_stopped"] = not server.thread.is_alive()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_regression(max(1, args.iterations))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, flush=True)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
