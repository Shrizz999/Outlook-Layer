"""Monitoring and Risk Engine."""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import structlog

from app.domain.enums import AlertType, Priority
from app.repositories.alert_repo import AlertRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.alert import MonitoringAlertCreate, MonitoringAlertRead

logger = structlog.get_logger(__name__)


class MonitoringRiskEngine:
    def __init__(
        self,
        alert_repo: AlertRepository | None = None,
        task_repo: TaskRepository | None = None,
        order_repo: OrderRepository | None = None,
    ) -> None:
        self._alert_repo = alert_repo or AlertRepository()
        self._task_repo = task_repo or TaskRepository()
        self._order_repo = order_repo or OrderRepository()

    async def evaluate_material_shortage(
        self,
        so_number: str,
        part_number: str,
        business_case_id: UUID | None = None,
    ) -> MonitoringAlertRead | None:
        """
        Compares SO required quantity against available MRP stock.
        Raises a MATERIAL_SHORTAGE alert if stock is insufficient.
        """
        so = await self._order_repo.get_sales_order_by_number(so_number)
        if not so:
            return None

        # Find line matching part_number
        target_line = None
        for line in so.lines:
            if line.source_part_number and line.source_part_number.upper() == part_number.upper():
                target_line = line
                break

        if not target_line or not target_line.ordered_quantity:
            return None

        mrp = await self._order_repo.get_latest_mrp_for_part(part_number)
        if not mrp or mrp.available_stock is None:
            return None

        required = target_line.ordered_quantity
        available = mrp.available_stock

        if available < required:
            shortage = required - available
            shortage_display = int(shortage) if float(shortage).is_integer() else shortage
            dedup_key = f"SHORTAGE_{so.so_number}_{part_number}"
            alert = await self._alert_repo.create_or_update_alert(
                MonitoringAlertCreate(
                    alert_type=AlertType.MATERIAL_SHORTAGE.value,
                    severity=Priority.HIGH.value,
                    business_case_id=business_case_id,
                    so_id=so.id,
                    description=f"Material shortage of {shortage_display} units detected for part {part_number} on {so.so_number} (Required: {required}, Available: {available})",
                    evidence={
                        "so_number": so.so_number,
                        "part_number": part_number,
                        "required_quantity": float(required),
                        "available_stock": float(available),
                        "shortage_quantity": float(shortage),
                    },
                    suggested_action=f"Release Purchase Order for {shortage_display} units of {part_number}",
                    dedup_key=dedup_key,
                )
            )
            logger.info("Material shortage alert raised", so_number=so.so_number, shortage=float(shortage))
            return alert

        return None

    async def evaluate_tasks(self) -> list[MonitoringAlertRead]:
        """Scans tasks for overdue deadlines, blockers, and unassigned status."""
        today_str = date.today().isoformat()
        tasks = await self._task_repo.list_legacy_tasks(limit=200)
        raised_alerts: list[MonitoringAlertRead] = []

        for t in tasks:
            # Overdue task check
            if t.deadline and t.deadline < today_str and t.status not in ("completed", "completed_reported", "completed_verified", "cancelled"):
                dedup_key = f"OVERDUE_{t.task_id}"
                alert = await self._alert_repo.create_or_update_alert(
                    MonitoringAlertCreate(
                        alert_type=AlertType.OVERDUE_TASK.value,
                        severity=Priority.CRITICAL.value,
                        task_id=t.task_id,
                        business_case_id=t.business_case_id,
                        description=f"Task {t.task_id} ('{t.description}') is overdue since {t.deadline}",
                        suggested_action=f"Follow up with {t.assigned_to or 'department head'} regarding delay reason",
                        dedup_key=dedup_key,
                    )
                )
                raised_alerts.append(alert)

            # Blocked task check
            if t.status == "blocked":
                dedup_key = f"BLOCKED_{t.task_id}"
                alert = await self._alert_repo.create_or_update_alert(
                    MonitoringAlertCreate(
                        alert_type=AlertType.BLOCKED.value,
                        severity=Priority.HIGH.value,
                        task_id=t.task_id,
                        business_case_id=t.business_case_id,
                        description=f"Task {t.task_id} is blocked: {t.delay_reason or t.reason or 'No reason provided'}",
                        suggested_action="Resolve prerequisite dependency blocker",
                        dedup_key=dedup_key,
                    )
                )
                raised_alerts.append(alert)

            # Unassigned task check
            if not t.assigned_to or t.assigned_to.lower() in ("unassigned", "pending"):
                dedup_key = f"NO_OWNER_{t.task_id}"
                alert = await self._alert_repo.create_or_update_alert(
                    MonitoringAlertCreate(
                        alert_type=AlertType.NO_OWNER.value,
                        severity=Priority.NORMAL.value,
                        task_id=t.task_id,
                        business_case_id=t.business_case_id,
                        description=f"Task {t.task_id} ('{t.description}') has no assigned employee",
                        suggested_action=f"Assign task to qualified employee in {t.department or 'department'}",
                        dedup_key=dedup_key,
                    )
                )
                raised_alerts.append(alert)

        return raised_alerts
