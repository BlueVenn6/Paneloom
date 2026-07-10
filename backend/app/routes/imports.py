from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.models.schemas import ApiResponse
from backend.app.services.document_import_service import (
    MAX_IMPORT_BYTES,
    DocumentImportError,
    import_document,
)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/document")
async def import_script_document(file: UploadFile = File(...)) -> ApiResponse:
    try:
        content = await file.read(MAX_IMPORT_BYTES + 1)
        result = import_document(file.filename or "document", content)
    except DocumentImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(ok=True, message="Document imported.", data=result)
