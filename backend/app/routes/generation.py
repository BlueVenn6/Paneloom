from concurrent.futures import ThreadPoolExecutor
import time
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.models.schemas import (
    ApiResponse,
    BatchGenerateRequest,
    ImageGenerationRequest,
    ReferenceConceptRequest,
    ReferenceStyleAnalysisRequest,
)
from backend.app.services.aspect_service import get_aspect_presets
from backend.app.services.image_service import (
    MAX_REFERENCE_BYTES,
    analyze_reference_style,
    delete_reference_image,
    edit_shot_with_reference,
    generate_reference_concepts,
    generate_project_batch,
    generate_shot_image,
    list_reference_images,
    save_reference_image,
)
from backend.app.services.project_service import utc_now
from backend.app.services.project_service import require_project
from backend.app.services.shotlist_service import get_shot

router = APIRouter(prefix="/projects/{project_id}/generate", tags=["generation"])

_GENERATION_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_GENERATION_JOBS: dict[str, dict] = {}
_REFERENCE_JOBS: dict[str, dict] = {}
MAX_RETAINED_JOBS = 200


def _prune_jobs(jobs: dict[str, dict]) -> None:
    if len(jobs) < MAX_RETAINED_JOBS:
        return
    completed = sorted(
        (
            job
            for job in jobs.values()
            if job.get("status") in {"done", "failed", "cancelled"}
        ),
        key=lambda item: item.get("updated_at", ""),
    )
    for job in completed[: max(1, len(jobs) - MAX_RETAINED_JOBS + 1)]:
        jobs.pop(job.get("job_id", ""), None)


def _job_snapshot(job_id: str) -> dict:
    return _safe_job_snapshot(_GENERATION_JOBS.get(job_id, {}))


def _reference_job_snapshot(job_id: str) -> dict:
    return _safe_job_snapshot(_REFERENCE_JOBS.get(job_id, {}))


def _safe_job_snapshot(job: dict) -> dict:
    snapshot = {key: value for key, value in job.items() if not key.startswith("_")}
    started = job.get("_started_monotonic")
    if started:
        snapshot["duration_seconds"] = round(
            job.get("duration_seconds") or (time.monotonic() - started),
            1,
        )
    return snapshot


def interrupt_active_jobs_for_desktop_shutdown() -> bool:
    """Mark active jobs retryable before the desktop process terminates their worker threads."""
    active = False
    for jobs in (_GENERATION_JOBS, _REFERENCE_JOBS):
        for job in jobs.values():
            if job.get("status") not in {"queued", "running"}:
                continue
            active = True
            job.update(
                {
                    "status": "cancelled",
                    "progress": "desktop_shutdown",
                    "error": "desktop_shutdown",
                    "error_message": "The desktop application closed while this AI task was running.",
                    "updated_at": utc_now(),
                }
            )
    if active:
        from backend.app.services.shotlist_service import recover_interrupted_generation_states

        recover_interrupted_generation_states()
    return active


def _run_generation_job(job_id: str, project_id: str, shot_id: str, payload: ImageGenerationRequest) -> None:
    job = _GENERATION_JOBS[job_id]
    job.update(
        {
            "status": "running",
            "progress": "submitted_to_image_provider",
            "updated_at": utc_now(),
        }
    )
    try:
        result = generate_shot_image(project_id, shot_id, payload)
        ok = result.get("status") == "done" and bool(result.get("output_path") or result.get("outputs"))
        job.update(
            {
                "status": "done" if ok else "failed",
                "progress": "completed" if ok else "failed",
                "result": result,
                "error": "",
                "error_message": "",
                "updated_at": utc_now(),
                "duration_seconds": round(time.monotonic() - job["_started_monotonic"], 1),
            }
        )
    except Exception as exc:  # noqa: BLE001 - keep background job observable in the UI
        job.update(
            {
                "status": "failed",
                "progress": "failed",
                "result": None,
                "error": type(exc).__name__,
                "error_message": str(exc),
                "updated_at": utc_now(),
                "duration_seconds": round(time.monotonic() - job["_started_monotonic"], 1),
            }
        )


def _run_reference_job(job_id: str, project_id: str, payload: ReferenceConceptRequest) -> None:
    job = _REFERENCE_JOBS[job_id]
    job.update(
        {
            "status": "running",
            "progress": "generating_reference_assets",
            "updated_at": utc_now(),
        }
    )
    try:
        result = generate_reference_concepts(
            project_id,
            script=payload.script,
            categories=payload.categories,
            refinement_prompt=payload.refinement_prompt,
        )
        ok = result.get("status") in {"done", "partial"}
        job.update(
            {
                "status": "done" if ok else "failed",
                "progress": (
                    "completed_with_errors"
                    if result.get("status") == "partial"
                    else "completed"
                    if ok
                    else "failed"
                ),
                "result": result,
                "error": result.get("error", "") if not ok else "",
                "error_message": result.get("error_message", "") if not ok else "",
                "updated_at": utc_now(),
                "duration_seconds": round(time.monotonic() - job["_started_monotonic"], 1),
            }
        )
    except Exception as exc:  # noqa: BLE001 - keep background job observable in the UI
        job.update(
            {
                "status": "failed",
                "progress": "failed",
                "result": None,
                "error": type(exc).__name__,
                "error_message": str(exc),
                "updated_at": utc_now(),
                "duration_seconds": round(time.monotonic() - job["_started_monotonic"], 1),
            }
        )


@router.get("/aspect-presets")
def aspect_presets(project_id: str) -> ApiResponse:
    try:
        require_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Aspect presets loaded.", data=get_aspect_presets())


@router.post("/batch")
def generate_batch(project_id: str, payload: BatchGenerateRequest) -> ApiResponse:
    try:
        result = generate_project_batch(
            project_id,
            shot_ids=payload.shot_ids,
            only_pending=payload.only_pending,
            stop_on_error=payload.stop_on_error,
            aspect_presets=payload.aspect_presets,
            reference_filenames=payload.reference_filenames,
            visual_format=payload.visual_format,
            panel_gutter_style=payload.panel_gutter_style,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message=f"Processed {result['processed']} shots.", data=result)


@router.get("/jobs/{job_id}")
def get_generation_job(project_id: str, job_id: str) -> ApiResponse:
    job = _GENERATION_JOBS.get(job_id)
    if not job or job.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    return ApiResponse(ok=True, message="Generation job loaded.", data=_job_snapshot(job_id))


@router.get("/references")
def get_references(project_id: str) -> ApiResponse:
    try:
        references = list_reference_images(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Reference images loaded.", data=references)


@router.post("/references")
async def upload_reference(project_id: str, file: UploadFile = File(...)) -> ApiResponse:
    try:
        content = await file.read(MAX_REFERENCE_BYTES + 1)
        reference = save_reference_image(project_id, file.filename or "reference.png", content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Reference image uploaded.", data=reference)


@router.delete("/references/{reference_filename}")
def delete_reference(project_id: str, reference_filename: str) -> ApiResponse:
    try:
        data = delete_reference_image(project_id, reference_filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Reference image deleted.", data=data)


@router.post("/references/concepts")
def generate_reference_concept_images(
    project_id: str,
    payload: ReferenceConceptRequest,
) -> ApiResponse:
    try:
        result = generate_reference_concepts(
            project_id,
            script=payload.script,
            categories=payload.categories,
            refinement_prompt=payload.refinement_prompt,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    ok = result.get("status") in {"done", "partial"}
    return ApiResponse(
        ok=ok,
        message="Reference concepts generated." if ok else result.get("error", "reference_generation_failed"),
        data=result,
    )


@router.post("/references/concepts/job")
def start_reference_concept_job(
    project_id: str,
    payload: ReferenceConceptRequest,
) -> ApiResponse:
    try:
        require_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _prune_jobs(_REFERENCE_JOBS)
    job_id = f"ref-job-{uuid4().hex[:12]}"
    _REFERENCE_JOBS[job_id] = {
        "job_id": job_id,
        "project_id": project_id,
        "status": "queued",
        "progress": "queued",
        "result": None,
        "error": "",
        "error_message": "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "_started_monotonic": time.monotonic(),
    }
    _GENERATION_EXECUTOR.submit(_run_reference_job, job_id, project_id, payload)
    return ApiResponse(ok=True, message="Reference generation job started.", data=_reference_job_snapshot(job_id))


@router.get("/references/jobs/{job_id}")
def get_reference_concept_job(project_id: str, job_id: str) -> ApiResponse:
    job = _REFERENCE_JOBS.get(job_id)
    if not job or job.get("project_id") != project_id:
        raise HTTPException(status_code=404, detail="Reference generation job not found.")
    return ApiResponse(ok=True, message="Reference generation job loaded.", data=_reference_job_snapshot(job_id))


@router.post("/references/style-analysis")
def analyze_reference_image_style(
    project_id: str,
    payload: ReferenceStyleAnalysisRequest,
) -> ApiResponse:
    try:
        result = analyze_reference_style(
            project_id,
            reference_filename=payload.reference_filename,
            apply_to_bible=payload.apply_to_bible,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Reference style analyzed.", data=result)


@router.post("/{shot_id}/edit-with-reference/{reference_filename}")
def edit_with_reference(
    project_id: str,
    shot_id: str,
    reference_filename: str,
    payload: ImageGenerationRequest | None = None,
) -> ApiResponse:
    try:
        result = edit_shot_with_reference(project_id, shot_id, reference_filename, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    ok = result.get("status") == "done"
    return ApiResponse(
        ok=ok,
        message="Image edited from reference." if ok else result.get("error", "image_edit_failed"),
        data=result,
    )


@router.post("/{shot_id}")
def generate_single_shot(
    project_id: str,
    shot_id: str,
    payload: ImageGenerationRequest | None = None,
) -> ApiResponse:
    try:
        result = generate_shot_image(project_id, shot_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    status = result.get("status")
    ok = status == "done" and bool(result.get("output_path") or result.get("outputs"))
    if status == "generated_url_download_failed":
        message = "Image URL returned, but local download failed."
    elif ok:
        message = "Image generated."
    else:
        message = (
            result.get("error")
            or result.get("short_error")
            or result.get("error_code")
            or result.get("error_message")
            or "image_generation_failed"
        )
    return ApiResponse(ok=ok, message=message, data=result)


@router.post("/{shot_id}/job")
def start_generation_job(
    project_id: str,
    shot_id: str,
    payload: ImageGenerationRequest | None = None,
) -> ApiResponse:
    try:
        require_project(project_id)
        if not get_shot(project_id, shot_id):
            raise FileNotFoundError(f"Shot not found: {shot_id}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _prune_jobs(_GENERATION_JOBS)
    job_id = f"job-{uuid4().hex[:12]}"
    request_payload = payload or ImageGenerationRequest()
    _GENERATION_JOBS[job_id] = {
        "job_id": job_id,
        "project_id": project_id,
        "shot_id": shot_id,
        "status": "queued",
        "progress": "queued",
        "result": None,
        "error": "",
        "error_message": "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "_started_monotonic": time.monotonic(),
    }
    _GENERATION_EXECUTOR.submit(_run_generation_job, job_id, project_id, shot_id, request_payload)
    return ApiResponse(ok=True, message="Generation job started.", data=_job_snapshot(job_id))
