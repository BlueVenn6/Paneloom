import hashlib
import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from backend.app.config import (
    APP_LOG_DIR,
    EXPORTS_DIR,
    GENERATED_ASSETS_DIR,
    PROJECTS_DIR,
    REFERENCE_ASSETS_DIR,
)
from backend.app.models.schemas import ProjectCreate
from backend.app.services import project_service


BACKUP_MANIFEST = "paneloom-backup-manifest.json"
MIGRATION_LOG = APP_LOG_DIR / "project-migrations.jsonl"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_project_files(project_dir: Path, include_exports: bool = True):
    for path in project_dir.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(project_dir)
        if relative.parts and relative.parts[0] == "backups":
            continue
        if not include_exports and relative.parts and relative.parts[0] == "exports":
            continue
        if path.name.startswith(".") and path.name.endswith(".tmp"):
            continue
        yield path, relative


def _manifest_entries(project_dir: Path, include_exports: bool = True) -> list[dict]:
    return [
        {
            "path": relative.as_posix(),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path, relative in _iter_project_files(project_dir, include_exports)
    ]


def _write_zip_atomically(output_path: Path, project_dir: Path, manifest: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr(BACKUP_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
            for entry in manifest["files"]:
                archive.write(project_dir / entry["path"], entry["path"])
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def create_project_backup(
    project_id: str,
    destination_directory: str = "",
    include_exports: bool = True,
) -> dict:
    project = project_service.require_project(project_id)
    if not project_service.is_self_contained_project(project_id):
        raise ValueError("Migrate this legacy project before creating a portable backup.")
    project_dir = project_service.get_project_dir(project_id)
    destination = (
        Path(destination_directory).expanduser().resolve()
        if destination_directory.strip()
        else project_service.get_project_backup_dir(project_id)
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = destination / f"{project_id}-{timestamp}-{uuid.uuid4().hex[:6]}.paneloom.zip"
    manifest = {
        "backup_schema_version": 1,
        "project_schema_version": int(project.get("schema_version") or 0),
        "project_id": project_id,
        "project_name": project.get("name", ""),
        "created_at": project_service.utc_now(),
        "includes_generated": True,
        "includes_exports": include_exports,
        "files": _manifest_entries(project_dir, include_exports),
    }
    _write_zip_atomically(output_path, project_dir, manifest)
    verification = verify_project_backup(output_path)
    return {
        "project_id": project_id,
        "backup_path": str(output_path),
        "file_count": len(manifest["files"]),
        "total_bytes": sum(item["size"] for item in manifest["files"]),
        "verified": verification["verified"],
        "includes_generated": True,
        "includes_exports": include_exports,
    }


def _safe_archive_name(name: str) -> str:
    normalized = PurePosixPath(name.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise ValueError("Backup contains an unsafe file path.")
    return normalized.as_posix()


def verify_project_backup(backup_path: str | Path) -> dict:
    path = Path(backup_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError("Project backup was not found.")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = {_safe_archive_name(item.filename) for item in archive.infolist()}
            if BACKUP_MANIFEST not in names:
                raise ValueError("Backup manifest is missing.")
            manifest = json.loads(archive.read(BACKUP_MANIFEST).decode("utf-8"))
            files = manifest.get("files", []) if isinstance(manifest, dict) else []
            for entry in files:
                name = _safe_archive_name(str(entry.get("path") or ""))
                if name not in names:
                    raise ValueError(f"Backup file is missing: {name}")
                content = archive.read(name)
                if len(content) != int(entry.get("size") or -1):
                    raise ValueError(f"Backup file size mismatch: {name}")
                if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
                    raise ValueError(f"Backup checksum mismatch: {name}")
    except (zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ValueError("Project backup is invalid.") from exc
    return {
        "verified": True,
        "backup_path": str(path),
        "project_id": manifest.get("project_id", ""),
        "project_name": manifest.get("project_name", ""),
        "file_count": len(files),
    }


def restore_project_backup(
    backup_path: str,
    destination_parent: str = "",
    restored_name: str = "",
) -> dict:
    verification = verify_project_backup(backup_path)
    source_id = str(verification["project_id"])
    project_service._validate_project_id(source_id)
    destination = (
        Path(destination_parent).expanduser().resolve()
        if destination_parent.strip()
        else project_service.PROJECTS_HOME.resolve()
    )
    destination.mkdir(parents=True, exist_ok=True)
    restore_id = f"{source_id}-restored-{uuid.uuid4().hex[:8]}"
    staging = destination / f".{restore_id}.restore-{uuid.uuid4().hex}"
    final = destination / restore_id
    if final.exists():
        raise FileExistsError("Restore destination already exists.")
    staging.mkdir(parents=False, exist_ok=False)
    try:
        with zipfile.ZipFile(Path(backup_path).expanduser().resolve(), "r") as archive:
            for item in archive.infolist():
                name = _safe_archive_name(item.filename)
                if name == BACKUP_MANIFEST or item.is_dir():
                    continue
                target = (staging / name).resolve()
                target.relative_to(staging.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        _rewrite_project_json_tree(staging, source_id, restore_id)
        config_path = staging / project_service.PROJECT_CONFIG_FILENAME
        config = project_service._read_json(config_path, {})
        if not isinstance(config, dict):
            raise ValueError("Restored project configuration is invalid.")
        config.update(
            {
                "project_id": restore_id,
                "name": restored_name.strip() or f"{config.get('name', 'Project')} Restored",
                "project_path": ".",
                "schema_version": project_service.SELF_CONTAINED_SCHEMA_VERSION,
                "storage_format": "self_contained",
                "created_at": project_service.utc_now(),
                "updated_at": project_service.utc_now(),
            }
        )
        project_service._write_json(config_path, config)
        _validate_portable_project(staging, restore_id)
        staging.replace(final)
        project_service.register_project_path(restore_id, final)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "project_id": restore_id,
        "name": config["name"],
        "restored_from_project_id": source_id,
        "project_path": ".",
        "restore_directory": str(final),
        "backup_verified": True,
    }


def _legacy_string_to_portable(value: str, project_id: str) -> str:
    normalized = value.replace("\\", "/")
    mappings = [
        (f"/assets/generated/{project_id}/", "generated/"),
        (f"/assets/references/{project_id}/", "assets/references/"),
        (f"/exports/{project_id}/", "exports/"),
        (f"/generated/{project_id}/", "generated/"),
        (f"/references/{project_id}/", "assets/references/"),
    ]
    lower = normalized.lower()
    for marker, replacement in mappings:
        index = lower.rfind(marker.lower())
        if index >= 0:
            suffix = normalized[index + len(marker) :]
            if normalized.startswith("/") and index == 0:
                category = replacement.rstrip("/").split("/")[-1]
                if replacement.startswith("assets/references"):
                    category = "references"
                return project_service.project_file_url(project_id, category, Path(suffix).name)
            return f"{replacement}{suffix}"
    return value


def _rewrite_portable_value(value: object, old_id: str, new_id: str | None = None) -> object:
    target_id = new_id or old_id
    if isinstance(value, list):
        return [_rewrite_portable_value(item, old_id, new_id) for item in value]
    if isinstance(value, dict):
        rewritten = {
            key: "." if key == "project_path" else _rewrite_portable_value(item, old_id, new_id)
            for key, item in value.items()
        }
        if rewritten.get("project_id") == old_id and new_id:
            rewritten["project_id"] = new_id
        return rewritten
    if isinstance(value, str):
        portable = _legacy_string_to_portable(value, old_id)
        return portable.replace(old_id, target_id) if new_id else portable
    return value


def _rewrite_project_json_tree(project_dir: Path, old_id: str, new_id: str | None = None) -> None:
    for path in project_dir.rglob("*.json"):
        if path.name.endswith(".bak"):
            continue
        data = project_service._read_json(path, None)
        if data is None:
            continue
        project_service._write_json(path, _rewrite_portable_value(data, old_id, new_id))


def _absolute_path_fields(value: object, prefix: str = "") -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, str) and (key == "project_path" or key.endswith("_path")):
                if re.match(r"^[A-Za-z]:[\\/]", item) or item.startswith("\\\\"):
                    issues.append(child)
            issues.extend(_absolute_path_fields(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            issues.extend(_absolute_path_fields(item, f"{prefix}[{index}]"))
    return issues


def _validate_portable_project(project_dir: Path, project_id: str) -> dict:
    required = [
        project_service.PROJECT_CONFIG_FILENAME,
        "workspace.json",
        "project_bible.json",
        "shots.json",
    ]
    missing = [name for name in required if not (project_dir / name).is_file()]
    if missing:
        raise ValueError(f"Portable project is missing required files: {', '.join(missing)}")
    config = project_service._read_json(project_dir / project_service.PROJECT_CONFIG_FILENAME, {})
    if not isinstance(config, dict) or config.get("project_id") != project_id:
        raise ValueError("Portable project configuration ID is invalid.")
    absolute_fields: list[str] = []
    for path in project_dir.rglob("*.json"):
        data = project_service._read_json(path, None)
        absolute_fields.extend(
            f"{path.relative_to(project_dir).as_posix()}:{field}"
            for field in _absolute_path_fields(data)
        )
    if absolute_fields:
        raise ValueError(f"Portable project still contains absolute path fields: {absolute_fields[:5]}")
    shots = project_service._read_json(project_dir / "shots.json", [])
    missing_assets = []
    for shot in shots if isinstance(shots, list) else []:
        paths = [shot.get("output_path", "")]
        paths.extend(item.get("output_path", "") for item in shot.get("outputs", []) if isinstance(item, dict))
        for version in shot.get("versions", []) if isinstance(shot.get("versions"), list) else []:
            if isinstance(version, dict):
                paths.append(version.get("output_path", ""))
                paths.extend(item.get("output_path", "") for item in version.get("outputs", []) if isinstance(item, dict))
        for stored in paths:
            if stored and not Path(stored).is_absolute() and not (project_dir / stored).is_file():
                missing_assets.append(stored)
    return {"valid": True, "missing_asset_references": sorted(set(missing_assets))}


def _ensure_legacy_minimum_files(project_dir: Path) -> list[str]:
    added: list[str] = []
    json_defaults = {
        "workspace.json": project_service._default_project_workspace(),
        "project_bible.json": project_service._default_project_bible(),
        "shots.json": [],
        "schedule.json": {},
        "tasks.json": [],
    }
    for filename, fallback in json_defaults.items():
        path = project_dir / filename
        if not path.exists():
            project_service._write_json(path, fallback)
            added.append(filename)
    csv_defaults = {
        "generation_log.csv": project_service.GENERATION_LOG_HEADERS,
        "failed_jobs.csv": project_service.FAILED_JOBS_HEADERS,
        "time_logs.csv": project_service.TIME_LOG_HEADERS,
        "publishing_log.csv": project_service.PUBLISHING_LOG_HEADERS,
    }
    for filename, headers in csv_defaults.items():
        path = project_dir / filename
        if not path.exists():
            project_service._ensure_csv(path, headers)
            added.append(filename)
    return added


def _create_legacy_migration_backup(project_id: str, destination_parent: Path) -> Path:
    source = PROJECTS_DIR / project_id
    backup_dir = destination_parent / "_migration_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    output = backup_dir / f"{project_id}-legacy-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    sources = [
        (source, "project"),
        (GENERATED_ASSETS_DIR / project_id, "generated"),
        (REFERENCE_ASSETS_DIR / project_id, "references"),
        (EXPORTS_DIR / project_id, "exports"),
    ]
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for root, prefix in sources:
                if not root.exists():
                    continue
                for path in root.rglob("*"):
                    if path.is_file() and not path.is_symlink():
                        archive.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def migrate_legacy_project(project_id: str, destination_parent: str = "") -> dict:
    project_service._validate_project_id(project_id)
    source = PROJECTS_DIR / project_id
    config = project_service._read_json(source / project_service.PROJECT_CONFIG_FILENAME, None)
    if not isinstance(config, dict) or config.get("project_id") != project_id:
        raise FileNotFoundError(f"Legacy project not found: {project_id}")
    destination = (
        Path(destination_parent).expanduser().resolve()
        if destination_parent.strip()
        else project_service.PROJECTS_HOME.resolve()
    )
    destination.mkdir(parents=True, exist_ok=True)
    final = destination / project_id
    if final.exists():
        existing = project_service._read_json(final / project_service.PROJECT_CONFIG_FILENAME, None)
        if (
            isinstance(existing, dict)
            and existing.get("project_id") == project_id
            and int(existing.get("schema_version") or 0) >= project_service.SELF_CONTAINED_SCHEMA_VERSION
        ):
            project_service.register_project_path(project_id, final)
            return {
                "project_id": project_id,
                "status": "already_migrated",
                "project_directory": str(final),
            }
        raise FileExistsError(f"Migration destination already exists: {final}")

    backup = _create_legacy_migration_backup(project_id, destination)
    staging = destination / f".{project_id}.migration-{uuid.uuid4().hex}"
    try:
        shutil.copytree(source, staging)
        for source_assets, target_relative in [
            (GENERATED_ASSETS_DIR / project_id, Path("generated")),
            (REFERENCE_ASSETS_DIR / project_id, Path("assets") / "references"),
            (EXPORTS_DIR / project_id, Path("exports")),
        ]:
            target = staging / target_relative
            target.mkdir(parents=True, exist_ok=True)
            if source_assets.exists():
                shutil.copytree(source_assets, target, dirs_exist_ok=True)
        (staging / "backups").mkdir(parents=True, exist_ok=True)
        (staging / "metadata").mkdir(parents=True, exist_ok=True)
        compatibility_files_added = _ensure_legacy_minimum_files(staging)
        for stale_backup in staging.rglob("*.bak"):
            stale_backup.unlink()
        _rewrite_project_json_tree(staging, project_id)
        migrated_config = project_service._read_json(
            staging / project_service.PROJECT_CONFIG_FILENAME,
            {},
        )
        migrated_config.update(
            {
                "project_path": ".",
                "schema_version": project_service.SELF_CONTAINED_SCHEMA_VERSION,
                "storage_format": "self_contained",
                "migrated_at": project_service.utc_now(),
            }
        )
        project_service._write_json(
            staging / project_service.PROJECT_CONFIG_FILENAME,
            migrated_config,
        )
        validation = _validate_portable_project(staging, project_id)
        file_manifest = {
            "schema_version": 1,
            "project_id": project_id,
            "created_at": project_service.utc_now(),
            "files": _manifest_entries(staging),
        }
        project_service._write_json(staging / "metadata" / "file-manifest.json", file_manifest)
        staging.replace(final)
        project_service.register_project_path(project_id, final)
        _append_migration_log(
            {
                "timestamp": project_service.utc_now(),
                "project_id": project_id,
                "status": "migrated",
                "backup_path": str(backup),
                "destination": str(final),
                "missing_asset_references": validation["missing_asset_references"],
                "compatibility_files_added": compatibility_files_added,
            }
        )
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        _append_migration_log(
            {
                "timestamp": project_service.utc_now(),
                "project_id": project_id,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "backup_path": str(backup),
            }
        )
        raise
    return {
        "project_id": project_id,
        "status": "migrated",
        "project_directory": str(final),
        "migration_backup": str(backup),
        "legacy_source_preserved": True,
        "missing_asset_references": validation["missing_asset_references"],
        "compatibility_files_added": compatibility_files_added,
    }


def migrate_all_legacy_projects(destination_parent: str = "") -> list[dict]:
    results = []
    for config_path in PROJECTS_DIR.glob(f"*/{project_service.PROJECT_CONFIG_FILENAME}"):
        config = project_service._read_json(config_path, {})
        if not isinstance(config, dict) or not config.get("project_id"):
            continue
        results.append(migrate_legacy_project(str(config["project_id"]), destination_parent))
    return results


def _append_migration_log(row: dict) -> None:
    MIGRATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with MIGRATION_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
