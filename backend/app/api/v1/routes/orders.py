"""Sales Orders & Lines API Routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.repositories.order_repo import OrderRepository
from app.schemas.order import SalesOrderCreate, SalesOrderRead

router = APIRouter()
repo = OrderRepository()


@router.get("", response_model=list[SalesOrderRead])
async def list_orders(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[SalesOrderRead]:
    return await repo.list_sales_orders(limit=limit, offset=offset)


@router.get("/{so_number}", response_model=SalesOrderRead)
async def get_order_by_number(so_number: str) -> SalesOrderRead:
    order = await repo.get_sales_order_by_number(so_number)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sales Order {so_number} not found")
    return order


@router.post("", response_model=SalesOrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(body: SalesOrderCreate) -> SalesOrderRead:
    return await repo.create_sales_order(body)
