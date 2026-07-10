from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.models.schemas import (
    ApiResponse,
    ReviewRequest,
    SchedulePlanRequest,
    ScheduleTaskUpdate,
    SocialFeedbackCreate,
    SocialFeedbackScreenshotRequest,
    TimeLogCreate,
)
from backend.app.services.schedule_service import (
    add_social_feedback,
    add_time_log,
    generate_review,
    generate_schedule,
    get_schedule,
    update_task,
)
from backend.app.services.project_service import require_project
from backend.app.services.social_feedback_ocr_service import (
    MAX_FEEDBACK_SCREENSHOT_BYTES,
    extract_social_feedback_from_image,
)

router = APIRouter(prefix="/projects/{project_id}/schedule", tags=["schedule"])


@router.get("")
def get_project_schedule(project_id: str) -> ApiResponse:
    try:
        data = get_schedule(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Schedule loaded.", data=data)


@router.post("/plan")
def post_schedule_plan(project_id: str, payload: SchedulePlanRequest) -> ApiResponse:
    try:
        data = generate_schedule(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Schedule plan generated.", data=data)


@router.patch("/tasks/{task_id}")
def patch_schedule_task(
    project_id: str,
    task_id: str,
    payload: ScheduleTaskUpdate,
) -> ApiResponse:
    try:
        task = update_task(project_id, task_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Task updated.", data=task)


@router.post("/time-logs")
def post_time_log(project_id: str, payload: TimeLogCreate) -> ApiResponse:
    try:
        row = add_time_log(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Time logged.", data=row)


@router.post("/feedback")
def post_social_feedback(project_id: str, payload: SocialFeedbackCreate) -> ApiResponse:
    try:
        row = add_social_feedback(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Social feedback saved.", data=row)


@router.post("/feedback/extract-screenshot")
async def extract_social_feedback_screenshot(
    project_id: str,
    file: UploadFile = File(...),
    platform: str = Form(""),
    publish_date: str = Form(""),
    content_id: str = Form(""),
    use_ai: bool = Form(True),
) -> ApiResponse:
    try:
        require_project(project_id)
        require_payload = SocialFeedbackScreenshotRequest(
            platform=platform,
            publish_date=publish_date,
            content_id=content_id,
            use_ai=use_ai,
        )
        content = await file.read(MAX_FEEDBACK_SCREENSHOT_BYTES + 1)
        data = extract_social_feedback_from_image(
            filename=file.filename or "screenshot",
            content=content,
            mime_type=file.content_type or "image/png",
            platform=require_payload.platform,
            publish_date=require_payload.publish_date,
            content_id=require_payload.content_id,
            use_ai=require_payload.use_ai,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Social screenshot extracted.", data=data)


@router.post("/review")
def post_review(project_id: str, payload: ReviewRequest) -> ApiResponse:
    try:
        review = generate_review(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message=f"{payload.period.title()} review generated.", data=review)
