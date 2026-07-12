from fastapi import APIRouter, HTTPException

from backend.app.models.schemas import (
    ApiResponse,
    ScriptBreakdownRequest,
    ShotCreate,
    ShotMergeNextRequest,
    ShotPairMergeRequest,
    ShotReorderRequest,
    ShotRewriteRequest,
    ShotUpdate,
    StoryOptimizationRequest,
)
from backend.app.services.project_service import require_project
from backend.app.services.planning_service import breakdown_script, rewrite_existing_storyboard
from backend.app.services.story_optimization_service import optimize_story
from backend.app.services.shotlist_service import (
    add_shot,
    add_shots,
    delete_shot,
    list_shots,
    merge_adjacent_shot_pairs,
    merge_shot_with_next,
    patch_shot,
    reorder_shots,
    select_shot_version,
)

router = APIRouter(prefix="/projects/{project_id}/shots", tags=["shots"])


@router.get("")
def get_shots(project_id: str) -> ApiResponse:
    try:
        require_project(project_id)
        shots = list_shots(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Shots loaded.", data=shots)


@router.post("")
def post_shot(project_id: str, payload: ShotCreate) -> ApiResponse:
    try:
        shot = add_shot(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Shot added.", data=shot)


@router.patch("/{shot_id}")
def patch_project_shot(project_id: str, shot_id: str, payload: ShotUpdate) -> ApiResponse:
    try:
        shot = patch_shot(project_id, shot_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Shot updated.", data=shot)


@router.delete("/{shot_id}")
def delete_project_shot(project_id: str, shot_id: str) -> ApiResponse:
    try:
        deleted = delete_shot(project_id, shot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Shot deleted.", data=deleted)


@router.post("/reorder")
def reorder_project_shots(project_id: str, payload: ShotReorderRequest) -> ApiResponse:
    try:
        shots = reorder_shots(project_id, payload.shot_ids)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Shots reordered.", data=shots)


@router.post("/{shot_id}/merge-next")
def merge_project_shot_with_next(
    project_id: str,
    shot_id: str,
    payload: ShotMergeNextRequest,
) -> ApiResponse:
    try:
        result = merge_shot_with_next(project_id, shot_id, payload.next_shot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Adjacent panels merged.", data=result)


@router.post("/merge-pairs")
def merge_project_shot_pairs(project_id: str, payload: ShotPairMergeRequest) -> ApiResponse:
    try:
        result = merge_adjacent_shot_pairs(project_id, payload.shot_ids)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Adjacent panel pairs merged.", data=result)


@router.post("/{shot_id}/versions/{version_id}/select")
def select_project_shot_version(project_id: str, shot_id: str, version_id: str) -> ApiResponse:
    try:
        shot = select_shot_version(project_id, shot_id, version_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Shot version selected.", data=shot)


@router.post("/from-script")
def post_shots_from_script(project_id: str, payload: ScriptBreakdownRequest) -> ApiResponse:
    try:
        require_project(project_id)
        breakdown = breakdown_script(payload)
        shots = add_shots(project_id, breakdown["shots"]) if breakdown.get("ok", True) else []
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ApiResponse(
        ok=bool(breakdown.get("ok", True)),
        message=(
            f"Created {len(shots)} storyboard shots from script."
            if breakdown.get("ok", True)
            else breakdown.get("error_message", "AI storyboard generation failed.")
        ),
        data={
            "source": breakdown["source"],
            "warnings": breakdown["warnings"],
            "error": breakdown.get("error", ""),
            "error_message": breakdown.get("error_message", ""),
            "shots": shots,
        },
    )


@router.post("/rewrite-storyboard")
def rewrite_project_storyboard(project_id: str, payload: ShotRewriteRequest) -> ApiResponse:
    try:
        result = rewrite_existing_storyboard(project_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(
        ok=bool(result.get("ok", True)),
        message=(
            f"Rewritten {len(result['shots'])} storyboard shots."
            if result.get("ok", True)
            else result.get("error_message", "AI storyboard rewrite failed.")
        ),
        data=result,
    )


@router.post("/optimize-story")
def optimize_project_story(project_id: str, payload: StoryOptimizationRequest) -> ApiResponse:
    try:
        require_project(project_id)
        result = optimize_story(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(
        ok=bool(result.get("ok")),
        message=(
            "Story optimization completed."
            if result.get("ok")
            else result.get("error_message", "AI story optimization failed.")
        ),
        data=result,
    )
