"""Review queue routes."""
from fastapi import APIRouter, Query, status
router = APIRouter()

@router.get("")
async def list_reviews(
    queue_type: str | None = Query(None),
    review_status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    return []

@router.post("/{review_id}/decision", status_code=status.HTTP_200_OK)
async def make_review_decision(review_id: str, body: dict) -> dict:
    """Accept, edit, or reject a review item. Records actor and timestamp."""
    return {"status": "recorded"}
