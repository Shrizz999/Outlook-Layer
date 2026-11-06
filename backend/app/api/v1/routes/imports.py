"""SO/MRP import routes."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

router = APIRouter()


class ImportPreviewResponse(BaseModel):
    file_name: str
    file_hash: str
    detected_sheets: list[str]
    suggested_import_type: str | None
    sample_rows: list[dict]
    detected_columns: list[str]


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    import_type: str = "SO",
) -> ImportPreviewResponse:
    """
    Preview a workbook before import.
    Returns sheet names, columns, and sample rows — does NOT persist data.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Coming in Phase 5")


@router.post("/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_import(body: dict) -> dict:
    """
    Execute a staged import after preview and user confirmation.
    Idempotent: reimporting the same file does not create duplicates.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Coming in Phase 5")


@router.get("")
async def list_imports() -> list[dict]:
    """List all import batches."""
    return []


@router.get("/{import_id}")
async def get_import(import_id: str) -> dict:
    """Get import batch report including error details."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")


@router.post("/{import_id}/confirm", status_code=status.HTTP_202_ACCEPTED)
async def confirm_import(import_id: str) -> dict:
    """Confirm a staged import and begin execution."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Coming in Phase 5")
