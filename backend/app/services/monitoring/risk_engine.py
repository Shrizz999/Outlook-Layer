"""Monitoring and Risk Engine."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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

    async def evaluate_tasks(self, warning_window_hours: int = 48) -> list[MonitoringAlertRead]:
        """Scans tasks for overdue deadlines, early warnings (48h), blockers, and unassigned status."""
        today = date.today()
        today_str = today.isoformat()
        warning_deadline = (today + timedelta(hours=warning_window_hours)).isoformat()

        tasks = await self._task_repo.list_legacy_tasks(limit=200)
        raised_alerts: list[MonitoringAlertRead] = []

        for t in tasks:
            is_completed = (t.status or "").lower() in ("completed", "completed_reported", "completed_verified", "cancelled")

            # 1. Overdue task check
            if t.deadline and t.deadline < today_str and not is_completed:
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

            # 2. Early delay warning check (within configurable window e.g. 48h)
            elif t.deadline and today_str <= t.deadline <= warning_deadline and not is_completed:
                if (t.progress_percentage or 0) < 50:
                    dedup_key = f"EARLY_WARNING_{t.task_id}"
                    alert = await self._alert_repo.create_or_update_alert(
                        MonitoringAlertCreate(
                            alert_type="EARLY_WARNING",
                            severity=Priority.HIGH.value,
                            task_id=t.task_id,
                            business_case_id=t.business_case_id,
                            description=f"Task {t.task_id} ('{t.description}') deadline is in <{warning_window_hours}h ({t.deadline}) but progress is only {t.progress_percentage or 0}%",
                            suggested_action=f"Check progress with {t.assigned_to or 'assignee'} before deadline breaches",
                            dedup_key=dedup_key,
                        )
                    )
                    raised_alerts.append(alert)

            # 3. Blocked task check
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

            # 4. Unassigned task check
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

    async def calculate_department_risk_scores(self) -> dict[str, Any]:
        """Calculates operational risk score (0-100) per department based on open alerts, overdues, and shortages."""
        tasks = await self._task_repo.list_legacy_tasks(limit=300)
        alerts = await self._alert_repo.list_alerts(status="OPEN")

        standard_depts = ["Engineering", "Purchase", "Stores", "Production", "Quality", "Dispatch", "Sales"]
        dept_scores: dict[str, dict[str, Any]] = {}
        for dept in standard_depts:
            dept_scores[dept] = {
                "department": dept,
                "risk_score": 0,
                "active_tasks_count": 0,
                "overdue_count": 0,
                "blocked_count": 0,
                "open_alerts_count": 0,
                "risk_level": "LOW",
            }

        for t in tasks:
            dept_name = (t.department or "General").capitalize()
            if dept_name not in dept_scores:
                dept_scores[dept_name] = {
                    "department": dept_name,
                    "risk_score": 0,
                    "active_tasks_count": 0,
                    "overdue_count": 0,
                    "blocked_count": 0,
                    "open_alerts_count": 0,
                    "risk_level": "LOW",
                }
            if t.status not in ("completed", "completed_reported", "completed_verified"):
                dept_scores[dept_name]["active_tasks_count"] += 1

        from datetime import date
        today_str = date.today().isoformat()
        for t in tasks:
            dept_name = (t.department or "General").capitalize()
            if t.deadline and t.deadline < today_str and t.status not in ("completed", "completed_reported", "completed_verified"):
                dept_scores[dept_name]["overdue_count"] += 1
            if t.status == "blocked":
                dept_scores[dept_name]["blocked_count"] += 1

        for a in alerts:
            points = 25 if a.severity == "CRITICAL" else (15 if a.severity == "HIGH" else 5)
            matched_dept = "Sales"
            if a.task_id:
                t = next((tk for tk in tasks if tk.task_id == a.task_id), None)
                if t and t.department:
                    matched_dept = t.department.capitalize()
            if matched_dept in dept_scores:
                dept_scores[matched_dept]["open_alerts_count"] += 1
                dept_scores[matched_dept]["risk_score"] = min(100, dept_scores[matched_dept]["risk_score"] + points)

        for d, data in dept_scores.items():
            score = data["risk_score"] + (data["overdue_count"] * 20) + (data["blocked_count"] * 15)
            score = min(100, score)
            data["risk_score"] = score
            data["risk_level"] = "CRITICAL" if score >= 75 else ("HIGH" if score >= 50 else ("MEDIUM" if score >= 25 else "LOW"))

        return dept_scores
