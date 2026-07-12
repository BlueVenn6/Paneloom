import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.models.schemas import (
    ApiResponse,
    ProjectBibleAnalyzeRequest,
    ProjectBiblePayload,
    ProjectCreate,
    ProjectBackupRequest,
    ProjectMigrationRequest,
    ProjectPathRequest,
    ProjectRestoreRequest,
    ProjectUpdate,
    ProjectWorkspacePayload,
)
from backend.app.services.bible_analysis_service import analyze_project_bible
from backend.app.services.project_service import (
    create_project,
    delete_project,
    duplicate_project,
    get_project_bible,
    get_project_workspace,
    get_project_export_dir,
    get_project_generated_dir,
    get_project_reference_dir,
    open_project_directory,
    list_projects,
    save_project_bible,
    save_project_workspace,
    update_project,
)
from backend.app.services.project_portability_service import (
    create_project_backup,
    migrate_legacy_project,
    restore_project_backup,
)
from backend.app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


def _desktop_dialog(dialog_type: str) -> str:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("Native folder dialogs are available in desktop mode only.") from exc
    if not webview.windows:
        raise RuntimeError("No active desktop window is available for the native dialog.")
    window = webview.windows[0]
    if dialog_type == "backup":
        selected = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Paneloom Backup (*.paneloom.zip)", "ZIP Archive (*.zip)"),
        )
    else:
        selected = window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=False)
    return str(selected[0]) if selected else ""


def _desktop_save_dialog(suggested_filename: str) -> str:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("Native save dialogs are available in desktop mode only.") from exc
    if not webview.windows:
        raise RuntimeError("No active desktop window is available for the native save dialog.")
    safe_name = Path(suggested_filename).name or "paneloom-export"
    suffix = Path(safe_name).suffix
    file_types = (f"{suffix.lstrip('.').upper()} file (*{suffix})",) if suffix else ()
    selected = webview.windows[0].create_file_dialog(
        webview.SAVE_DIALOG,
        save_filename=safe_name,
        file_types=file_types,
    )
    if isinstance(selected, (list, tuple)):
        return str(selected[0]) if selected else ""
    return str(selected or "")


@router.get("/storage")
def get_project_storage() -> ApiResponse:
    return ApiResponse(
        ok=True,
        message="Project storage loaded.",
        data={"default_projects_home": str(project_service.PROJECTS_HOME)},
    )


@router.post("/choose-folder")
def choose_project_folder() -> ApiResponse:
    try:
        path = _desktop_dialog("folder")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=bool(path), message="Folder selected." if path else "Folder selection cancelled.", data={"path": path})


@router.post("/choose-backup")
def choose_backup_file() -> ApiResponse:
    try:
        path = _desktop_dialog("backup")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=bool(path), message="Backup selected." if path else "Backup selection cancelled.", data={"path": path})


@router.post("/{project_id}/desktop-save")
def save_desktop_export(
    project_id: str,
    file: UploadFile = File(...),
    suggested_filename: str = Form("paneloom-export"),
) -> ApiResponse:
    try:
        project = project_service.require_project(project_id)
        safe_name = Path(suggested_filename).name or "paneloom-export"
        destination_text = _desktop_save_dialog(safe_name)
        if not destination_text:
            return ApiResponse(ok=False, message="Save cancelled.", data={"cancelled": True})
        content = file.file.read(100 * 1024 * 1024 + 1)
        if len(content) > 100 * 1024 * 1024:
            raise ValueError("The export exceeds the 100 MB desktop save limit.")
        destination = Path(destination_text)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(
        ok=True,
        message="File saved.",
        data={
            "path": str(destination),
            "filename": destination.name,
            "size": len(content),
            "project_id": project["project_id"],
        },
    )


@router.post("/open")
def open_project(payload: ProjectPathRequest) -> ApiResponse:
    try:
        project = open_project_directory(payload.path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project opened.", data=project)


@router.post("/restore")
def restore_project(payload: ProjectRestoreRequest) -> ApiResponse:
    try:
        project = restore_project_backup(
            payload.backup_path,
            payload.destination_parent,
            payload.restored_name,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project restored as a new project.", data=project)


@router.get("")
def get_projects() -> ApiResponse:
    return ApiResponse(ok=True, message="Projects loaded.", data=list_projects())


@router.post("")
def post_project(payload: ProjectCreate) -> ApiResponse:
    try:
        project = create_project(payload)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project created.", data=project)


@router.patch("/{project_id}")
def patch_project(project_id: str, payload: ProjectUpdate) -> ApiResponse:
    try:
        project = update_project(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project updated.", data=project)


@router.post("/{project_id}/duplicate")
def post_duplicate_project(project_id: str) -> ApiResponse:
    try:
        project = duplicate_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project duplicated.", data=project)


@router.post("/{project_id}/migrate")
def migrate_project(project_id: str, payload: ProjectMigrationRequest) -> ApiResponse:
    try:
        result = migrate_legacy_project(project_id, payload.destination_parent)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Legacy project migrated without modifying its source.", data=result)


@router.post("/{project_id}/backup")
def backup_project(project_id: str, payload: ProjectBackupRequest) -> ApiResponse:
    try:
        result = create_project_backup(
            project_id,
            payload.destination_directory,
            payload.include_exports,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project backup created and verified.", data=result)


@router.get("/{project_id}/files/{category}/{filename}")
def get_project_file(project_id: str, category: str, filename: str):
    try:
        require_project = project_service.require_project
        require_project(project_id)
        bases = {
            "generated": get_project_generated_dir,
            "references": get_project_reference_dir,
            "exports": get_project_export_dir,
        }
        if category not in bases or Path(filename).name != filename:
            raise ValueError("Invalid project file path.")
        base = bases[category](project_id).resolve()
        path = (base / filename).resolve()
        path.relative_to(base)
        if not path.is_file():
            raise FileNotFoundError("Project file not found.")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(path)


@router.delete("/{project_id}")
def remove_project(project_id: str) -> ApiResponse:
    try:
        result = delete_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project moved to recoverable trash.", data=result)


@router.get("/{project_id}/workspace")
def get_workspace(project_id: str) -> ApiResponse:
    try:
        workspace = get_project_workspace(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project workspace loaded.", data=workspace)


@router.put("/{project_id}/workspace")
def put_workspace(project_id: str, payload: ProjectWorkspacePayload) -> ApiResponse:
    try:
        workspace = save_project_workspace(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project workspace saved.", data=workspace)


@router.get("/{project_id}/bible")
def get_bible(project_id: str) -> ApiResponse:
    try:
        bible = get_project_bible(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project bible loaded.", data=bible)


@router.put("/{project_id}/bible")
def put_bible(project_id: str, payload: ProjectBiblePayload) -> ApiResponse:
    try:
        bible = save_project_bible(project_id, payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Project bible saved.", data=bible)


@router.post("/{project_id}/bible/analyze")
def analyze_bible(project_id: str, payload: ProjectBibleAnalyzeRequest) -> ApiResponse:
    try:
        result = analyze_project_bible(
            project_id,
            script=payload.script,
            use_ai=payload.use_ai,
            replace_existing=payload.replace_existing,
            output_language=payload.output_language,
        )
        if result.get("ok") and isinstance(result.get("bible"), dict):
            result["bible"] = save_project_bible(project_id, result["bible"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(
        ok=bool(result.get("ok")),
        message=(
            "Project bible analyzed."
            if result.get("ok")
            else result.get("error_message", "AI project bible analysis failed.")
        ),
        data=result,
    )
