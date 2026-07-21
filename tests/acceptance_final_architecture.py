import base64
import ctypes
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from ctypes import wintypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_PYTHON = ROOT / ".desktop-venv" / "Scripts" / "python.exe"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def wait_for_json(path: Path, key: str, timeout: float = 180, expected=None) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if key in data and (expected is None or data.get(key) == expected):
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {key}={expected!r} in {path}")


def request(url: str, path: str, method: str = "GET", payload=None, timeout: float = 20):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{url}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content = response.read()
        return json.loads(content.decode("utf-8")) if content else {}


def request_error_status(url: str, path: str, method: str, payload) -> tuple[int, str]:
    try:
        request(url, path, method, payload)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    return 200, ""


def request_bytes(url: str, path: str) -> bytes:
    with urllib.request.urlopen(f"{url}{path}", timeout=20) as response:
        return response.read()


def upload(url: str, path: str, filename: str, content: bytes) -> dict:
    boundary = f"----Paneloom{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("ascii") + content + f"\r\n--{boundary}--\r\n".encode("ascii")
    req = urllib.request.Request(
        f"{url}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_job(url: str, project_id: str, job_id: str, timeout: float = 30) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = request(url, f"/projects/{project_id}/generate/jobs/{job_id}")["data"]
        if job.get("status") in {"done", "failed", "cancelled"}:
            return job
        time.sleep(0.1)
    raise TimeoutError(f"Generation job did not finish: {job_id}")


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


def port_is_closed(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def start_desktop(root: Path, runtime_state: Path, provider_port: int, offline: bool = False):
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
            "IMAGE_RESULT_MODE": "prefer_b64_json",
            "PANELOOM_FORCE_OFFLINE": "1" if offline else "0",
        }
    )
    started = time.monotonic()
    process = subprocess.Popen(
        [str(DESKTOP_PYTHON), str(ROOT / "desktop" / "launcher.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready = wait_for_json(runtime_state, "status", expected="window_ready")
    ready["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return process, ready


def stop_desktop(process, ready: dict, runtime_state: Path) -> dict:
    started = time.monotonic()
    windows_closed = close_native_windows(int(ready["pid"]))
    if windows_closed < 1:
        raise RuntimeError("No native Paneloom window accepted WM_CLOSE.")
    try:
        stdout, stderr = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
        )
        raise TimeoutError("Paneloom did not exit within 60 seconds.")
    if process.returncode != 0:
        raise RuntimeError(f"Paneloom exited with {process.returncode}: {stderr or stdout}")
    state = json.loads(runtime_state.read_text(encoding="utf-8"))
    return {
        "windows_closed": windows_closed,
        "exit_seconds": round(time.monotonic() - started, 3),
        "port_released": port_is_closed(int(ready["port"])),
        "runtime_state": state,
        "process_exited": process.poll() is not None,
    }


def backup_integrity(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as archive:
        names = {item.filename for item in archive.infolist() if not item.is_dir()}
        manifest = json.loads(archive.read("paneloom-backup-manifest.json").decode("utf-8"))
        expected = {item["path"] for item in manifest["files"]}
        missing = sorted(expected - names)
        extra = sorted(names - expected - {"paneloom-backup-manifest.json"})
        size_mismatches = []
        checksum_mismatches = []
        content_scan_passed = True
        unrelated = []
        for entry in manifest["files"]:
            content = archive.read(entry["path"])
            if len(content) != entry["size"]:
                size_mismatches.append(entry["path"])
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                checksum_mismatches.append(entry["path"])
            if b"controlled-test-key" in content or b'"api_key"' in content:
                content_scan_passed = False
            first = entry["path"].split("/", 1)[0].lower()
            if first in {"logs", "cache", "temp", "config"}:
                unrelated.append(entry["path"])
        return {
            "file_count": len(manifest["files"]),
            "total_bytes": sum(item["size"] for item in manifest["files"]),
            "missing": missing,
            "extra": extra,
            "size_mismatches": size_mismatches,
            "checksum_mismatches": checksum_mismatches,
            "content_scan_passed": content_scan_passed,
            "unrelated_global_files": unrelated,
            "valid": not (
                missing
                or extra
                or size_mismatches
                or checksum_mismatches
                or not content_scan_passed
                or unrelated
            ),
        }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="paneloom-final-architecture-", ignore_cleanup_errors=True) as tmp:
        root = Path(tmp)
        provider_state = root / "provider.json"
        provider = subprocess.Popen(
            [sys.executable, str(ROOT / "tests" / "controlled_image_provider.py"), "--state", str(provider_state)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        launches = []
        shutdowns = []
        desktop = None
        try:
            provider_ready = wait_for_json(provider_state, "ready", timeout=30, expected=True)
            provider_port = int(provider_ready["port"])

            desktop, ready = start_desktop(root, root / "runtime-1.json", provider_port)
            launches.append(ready)
            url = f"http://127.0.0.1:{ready['port']}"
            health = request(url, "/health")
            initial_projects = request(url, "/projects")["data"]
            created = request(
                url,
                "/projects",
                "POST",
                {
                    "name": "Final Architecture E2E",
                    "description": "Disposable production-like regression",
                    "parent_directory": str(root / "projects"),
                },
            )["data"]
            project_id = created["project_id"]
            request(url, f"/projects/{project_id}/workspace", "PUT", {"script": "STATE A script"})
            request(
                url,
                f"/projects/{project_id}/bible",
                "PUT",
                {
                    "characters": "Hero: black hair and red coat",
                    "locations": "Rainy station platform",
                    "props": "red umbrella",
                    "visual_style": "clean manga line art",
                },
            )
            character_ref = upload(
                url,
                f"/projects/{project_id}/generate/references",
                "character-hero.png",
                PNG_BYTES,
            )["data"]
            scene_ref = upload(
                url,
                f"/projects/{project_id}/generate/references",
                "scene-station.png",
                PNG_BYTES,
            )["data"]
            shot = request(
                url,
                f"/projects/{project_id}/shots",
                "POST",
                {"scene_id": "S001", "prompt": "Hero waits at the rainy station"},
            )["data"]

            generated_jobs = []
            for prompt in ("version one", "version two"):
                job = request(
                    url,
                    f"/projects/{project_id}/generate/{shot['shot_id']}/job",
                    "POST",
                    {"prompt": prompt, "size": "64x64", "quality": "low"},
                )["data"]
                generated_jobs.append(wait_job(url, project_id, job["job_id"]))
            shots = request(url, f"/projects/{project_id}/shots")["data"]
            shot = next(item for item in shots if item["shot_id"] == shot["shot_id"])
            versions = shot["versions"]
            selected = request(
                url,
                f"/projects/{project_id}/shots/{shot['shot_id']}/versions/{versions[0]['version_id']}/select",
                "POST",
                {},
            )["data"]
            locked = request(
                url,
                f"/projects/{project_id}/shots/{shot['shot_id']}",
                "PATCH",
                {"locked": True, "approval_status": "approved"},
            )["data"]
            provider_before_locked_attempt = wait_for_json(provider_state, "request_count")["request_count"]
            locked_job = request(
                url,
                f"/projects/{project_id}/generate/{shot['shot_id']}/job",
                "POST",
                {"prompt": "must be blocked", "size": "64x64", "quality": "low"},
            )["data"]
            locked_failure = wait_job(url, project_id, locked_job["job_id"])
            provider_after_locked_attempt = wait_for_json(provider_state, "request_count")["request_count"]

            exported = request(url, f"/projects/{project_id}/exports", "POST", {"format": "json"})["data"]
            backup_response = request(
                url,
                f"/projects/{project_id}/backup",
                "POST",
                {"destination_directory": str(root / "backups"), "include_exports": True},
            )["data"]
            backup_path = Path(backup_response["backup_path"])
            backup_check = backup_integrity(backup_path)

            request(url, f"/projects/{project_id}/workspace", "PUT", {"script": "STATE B script"})
            original_dir = root / "projects" / project_id
            first_shutdown = stop_desktop(desktop, ready, root / "runtime-1.json")
            shutdowns.append(first_shutdown)
            desktop = None

            moved_dir = root / "moved projects" / project_id
            moved_dir.parent.mkdir(parents=True)
            shutil.move(str(original_dir), str(moved_dir))

            desktop, ready = start_desktop(root, root / "runtime-2.json", provider_port)
            launches.append(ready)
            url = f"http://127.0.0.1:{ready['port']}"
            reopened = request(url, "/projects/open", "POST", {"path": str(moved_dir)})["data"]
            reopened_workspace = request(url, f"/projects/{project_id}/workspace")["data"]
            reopened_bible = request(url, f"/projects/{project_id}/bible")["data"]
            reopened_refs = request(url, f"/projects/{project_id}/generate/references")["data"]
            reopened_shot = request(url, f"/projects/{project_id}/shots")["data"][0]
            reference_bytes = request_bytes(url, character_ref["url"])
            scene_bytes = request_bytes(url, scene_ref["url"])
            generated_bytes = request_bytes(url, reopened_shot["output_url"])
            export_bytes = request_bytes(url, exported["url"])

            project_count_before_restore = len(request(url, "/projects")["data"])
            restored = request(
                url,
                "/projects/restore",
                "POST",
                {
                    "backup_path": str(backup_path),
                    "destination_parent": str(root / "restored"),
                    "restored_name": "Recovered State A",
                },
            )["data"]
            restored_id = restored["project_id"]
            restored_workspace = request(url, f"/projects/{restored_id}/workspace")["data"]
            restored_shot = request(url, f"/projects/{restored_id}/shots")["data"][0]
            project_count_after_restore = len(request(url, "/projects")["data"])
            second_shutdown = stop_desktop(desktop, ready, root / "runtime-2.json")
            shutdowns.append(second_shutdown)
            desktop = None

            provider_count_before_offline = wait_for_json(provider_state, "request_count")["request_count"]
            desktop, ready = start_desktop(root, root / "runtime-3.json", provider_port, offline=True)
            launches.append(ready)
            url = f"http://127.0.0.1:{ready['port']}"
            offline_health = request(url, "/health")
            offline_projects = request(url, "/projects")["data"]
            offline_created = request(
                url,
                "/projects",
                "POST",
                {"name": "Offline New Project", "parent_directory": str(root / "offline projects")},
            )["data"]
            request(
                url,
                f"/projects/{offline_created['project_id']}/workspace",
                "PUT",
                {"script": "offline script edit"},
            )
            request(
                url,
                f"/projects/{offline_created['project_id']}/bible",
                "PUT",
                {"characters": "offline character", "locations": "offline location"},
            )
            offline_workspace = request(
                url,
                f"/projects/{offline_created['project_id']}/workspace",
            )["data"]
            offline_bible = request(
                url,
                f"/projects/{offline_created['project_id']}/bible",
            )["data"]
            offline_shot = request(
                url,
                f"/projects/{offline_created['project_id']}/shots",
                "POST",
                {"scene_id": "OFFLINE", "prompt": "offline storyboard edit"},
            )["data"]
            offline_job = request(
                url,
                f"/projects/{offline_created['project_id']}/generate/{offline_shot['shot_id']}/job",
                "POST",
                {"size": "64x64", "quality": "low"},
            )["data"]
            offline_failure = wait_job(url, offline_created["project_id"], offline_job["job_id"])
            offline_export = request(
                url,
                f"/projects/{offline_created['project_id']}/exports",
                "POST",
                {"format": "json"},
            )["data"]
            offline_export_bytes = request_bytes(url, offline_export["url"])
            offline_historical_image = request_bytes(url, reopened_shot["output_url"])
            request(
                url,
                f"/projects/{project_id}/shots/{reopened_shot['shot_id']}",
                "PATCH",
                {"locked": False, "approval_status": "draft"},
            )
            offline_selected = request(
                url,
                f"/projects/{project_id}/shots/{reopened_shot['shot_id']}/versions/{reopened_shot['versions'][1]['version_id']}/select",
                "POST",
                {},
            )["data"]
            offline_relocked = request(
                url,
                f"/projects/{project_id}/shots/{reopened_shot['shot_id']}",
                "PATCH",
                {"locked": True, "approval_status": "approved"},
            )["data"]
            provider_count_after_offline = wait_for_json(provider_state, "request_count")["request_count"]
            third_shutdown = stop_desktop(desktop, ready, root / "runtime-3.json")
            shutdowns.append(third_shutdown)
            desktop = None

            cache_released = False
            cache = root / "appdata" / "cache" / "webview"
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    shutil.rmtree(cache)
                    cache_released = True
                    break
                except FileNotFoundError:
                    cache_released = True
                    break
                except PermissionError:
                    time.sleep(0.25)

            result = {
                "ok": True,
                "production_health_ok": health.get("ok") is True,
                "initial_project_count": len(initial_projects),
                "legacy_source_was_not_created": not (root / "nonexistent legacy source").exists(),
                "launches": launches,
                "shutdowns": shutdowns,
                "two_image_jobs_done": all(job.get("status") == "done" for job in generated_jobs),
                "image_version_count": len(versions),
                "image_paths_distinct": len({item["output_path"] for item in versions}) == len(versions),
                "selected_version_persisted": selected["selected_version_id"] == versions[0]["version_id"],
                "shot_locked_approved": locked.get("locked") is True and locked.get("approval_status") == "approved",
                "locked_generation_blocked": locked_failure.get("status") == "failed",
                "locked_generation_provider_not_called": provider_before_locked_attempt == provider_after_locked_attempt,
                "backup": backup_check,
                "project_moved_and_reopened": reopened.get("project_id") == project_id,
                "moved_workspace_state": reopened_workspace.get("script"),
                "moved_bible_preserved": bool(reopened_bible.get("characters") and reopened_bible.get("locations")),
                "reference_count": len(reopened_refs),
                "reference_files_readable": len(reference_bytes) > 0 and len(scene_bytes) > 0,
                "generated_file_readable": len(generated_bytes) > 0,
                "export_file_readable": len(export_bytes) > 0,
                "moved_version_count": len(reopened_shot.get("versions", [])),
                "moved_selected_version": reopened_shot.get("selected_version_id"),
                "moved_locked": reopened_shot.get("locked") is True,
                "restore_created_new_project": restored_id != project_id and project_count_after_restore == project_count_before_restore + 1,
                "restored_state_a": restored_workspace.get("script") == "STATE A script",
                "restored_locked_selection": bool(restored_shot.get("locked") and restored_shot.get("selected_version_id")),
                "offline_health": offline_health,
                "offline_existing_projects": len(offline_projects),
                "offline_create_edit": (
                    offline_workspace.get("script") == "offline script edit"
                    and offline_bible.get("characters") == "offline character"
                ),
                "offline_cloud_job_failed": offline_failure.get("status") == "failed",
                "offline_provider_not_called": provider_count_before_offline == provider_count_after_offline,
                "offline_export_path": offline_export.get("path", ""),
                "offline_export_readable": len(offline_export_bytes) > 0,
                "offline_historical_image_readable": len(offline_historical_image) > 0,
                "offline_version_switch_and_lock": (
                    offline_selected.get("selected_version_id") == reopened_shot["versions"][1]["version_id"]
                    and offline_relocked.get("locked") is True
                    and offline_relocked.get("approval_status") == "approved"
                ),
                "webview_cache_released": cache_released,
            }
            required = [
                result["production_health_ok"],
                result["initial_project_count"] == 0,
                result["legacy_source_was_not_created"],
                result["two_image_jobs_done"],
                result["image_version_count"] >= 2,
                result["image_paths_distinct"],
                result["selected_version_persisted"],
                result["shot_locked_approved"],
                result["locked_generation_blocked"],
                result["locked_generation_provider_not_called"],
                result["backup"]["valid"],
                result["project_moved_and_reopened"],
                result["moved_workspace_state"] == "STATE B script",
                result["moved_bible_preserved"],
                result["reference_count"] >= 2,
                result["reference_files_readable"],
                result["generated_file_readable"],
                result["export_file_readable"],
                result["moved_version_count"] >= 2,
                bool(result["moved_selected_version"]),
                result["moved_locked"],
                result["restore_created_new_project"],
                result["restored_state_a"],
                result["restored_locked_selection"],
                result["offline_health"].get("offline_mode") is True,
                result["offline_health"].get("cloud_ai_available") is False,
                result["offline_create_edit"],
                result["offline_cloud_job_failed"],
                result["offline_provider_not_called"],
                bool(result["offline_export_path"]),
                result["offline_export_readable"],
                result["offline_historical_image_readable"],
                result["offline_version_switch_and_lock"],
                all(item["port_released"] and item["process_exited"] for item in shutdowns),
                result["webview_cache_released"],
            ]
            result["ok"] = all(required)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["ok"] else 1
        finally:
            if desktop and desktop.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(desktop.pid), "/T", "/F"],
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
