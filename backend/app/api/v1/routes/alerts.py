"""Alerts & Risk Engine API Routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.repositories.alert_repo import AlertRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.alert import MonitoringAlertCreate, MonitoringAlertRead
from app.services.monitoring.risk_engine import MonitoringRiskEngine

router = APIRouter()
alert_repo = AlertRepository()
risk_engine = MonitoringRiskEngine(alert_repo=alert_repo)


class ResolveAlertRequest(BaseModel):
    notes: str | None = None
    employee_id: UUID | None = None


@router.get("", response_model=list[MonitoringAlertRead])
async def list_alerts(
    status: str | None = Query(None),
    alert_type: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[MonitoringAlertRead]:
    return await alert_repo.list_alerts(
        status=status,
        alert_type=alert_type,
        severity=severity,
        limit=limit,
        offset=offset,
    )


@router.post("/evaluate-tasks", response_model=list[MonitoringAlertRead])
async def trigger_task_evaluation() -> list[MonitoringAlertRead]:
    """Runs a sweep of all tasks to detect overdue deadlines, blockers, and unassigned status."""
    return await risk_engine.evaluate_tasks()


@router.post("/evaluate-shortage", response_model=MonitoringAlertRead | None)
async def trigger_shortage_evaluation(so_number: str, part_number: str) -> MonitoringAlertRead | None:
    """Checks SO vs MRP stock and raises an alert if shortage is found."""
    return await risk_engine.evaluate_material_shortage(so_number, part_number)


@router.post("/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_alert(alert_id: UUID, employee_id: UUID | None = None) -> dict:
    await alert_repo.acknowledge_alert(alert_id, employee_id=employee_id)
    return {"status": "acknowledged", "alert_id": str(alert_id)}


@router.post("/{alert_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_alert(alert_id: UUID, req: ResolveAlertRequest) -> dict:
    await alert_repo.resolve_alert(alert_id, notes=req.notes, employee_id=req.employee_id)
    return {"status": "resolved", "alert_id": str(alert_id)}
