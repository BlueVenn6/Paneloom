from fastapi import APIRouter, HTTPException

from backend.app.models.schemas import ApiResponse, ExportRequest
from backend.app.services.export_service import export_project

router = APIRouter(prefix="/projects/{project_id}/exports", tags=["exports"])


@router.post("")
def post_export(project_id: str, payload: ExportRequest) -> ApiResponse:
    try:
        result = export_project(project_id, payload.format)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(ok=True, message=f"Exported {payload.format}.", data=result)
