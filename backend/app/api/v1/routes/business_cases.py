"""Business Case API Routes."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.repositories.business_case_repo import BusinessCaseRepository
from app.schemas.business_case import (
    BusinessCaseCreate,
    BusinessCaseRead,
    CaseLinkCreate,
    CaseLinkRead,
    ThreeWayReconciliationRequest,
    ThreeWayReconciliationResult,
)
from app.services.context.context_engine import BusinessContextEngine

router = APIRouter()
repo = BusinessCaseRepository()
context_engine = BusinessContextEngine(case_repo=repo)


@router.get("", response_model=list[BusinessCaseRead])
async def list_cases(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    customer_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[BusinessCaseRead]:
    return await repo.list_cases(
        status=status,
        priority=priority,
        customer_id=customer_id,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=BusinessCaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(body: BusinessCaseCreate) -> BusinessCaseRead:
    return await repo.create_case(body)


@router.get("/{case_id}", response_model=BusinessCaseRead)
async def get_case(case_id: UUID) -> BusinessCaseRead:
    case = await repo.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business Case not found")
    return case


@router.post("/{case_id}/links", response_model=CaseLinkRead, status_code=status.HTTP_201_CREATED)
async def add_link(case_id: UUID, body: CaseLinkCreate) -> CaseLinkRead:
    case = await repo.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business Case not found")
    return await repo.add_case_link(case_id, body)


@router.patch("/{case_id}/status", status_code=status.HTTP_200_OK)
async def update_status(case_id: UUID, new_status: str = Query(...)) -> dict:
    case = await repo.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business Case not found")
    await repo.update_case_status(case_id, new_status)
    return {"status": "updated", "case_id": str(case_id), "new_status": new_status}


@router.post("/reconcile-3way", response_model=ThreeWayReconciliationResult)
async def reconcile_three_way_order(req: ThreeWayReconciliationRequest) -> ThreeWayReconciliationResult:
    return context_engine.reconcile_three_way_match(
        quote=req.quote,
        po=req.purchase_order,
        so=req.sales_order,
    )

