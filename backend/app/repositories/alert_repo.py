"""Alerts & Monitoring Repository."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import AlertStatus
from app.repositories.store import get_store, get_supabase_client
from app.schemas.alert import MonitoringAlertCreate, MonitoringAlertRead


class AlertRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    async def create_or_update_alert(self, data: MonitoringAlertCreate) -> MonitoringAlertRead:
        """Create an alert or update an existing one if dedup_key matches."""
        now = datetime.now(UTC)

        # Check existing by dedup_key
        if data.dedup_key:
            if self._client:
                res = self._client.table("bi_monitoring_alerts").select("*").eq("dedup_key", data.dedup_key).execute()
                if res.data:
                    existing_id = res.data[0]["id"]
                    self._client.table("bi_monitoring_alerts").update({
                        "description": data.description,
                        "severity": data.severity,
                        "suggested_action": data.suggested_action,
                        "updated_at": now.isoformat(),
                    }).eq("id", existing_id).execute()
                    res_up = self._client.table("bi_monitoring_alerts").select("*").eq("id", existing_id).execute()
                    return MonitoringAlertRead(**res_up.data[0])
            else:
                for a in self._store.bi_monitoring_alerts.values():
                    if a.get("dedup_key") == data.dedup_key:
                        a["description"] = data.description
                        a["severity"] = data.severity
                        a["suggested_action"] = data.suggested_action
                        a["updated_at"] = now
                        return MonitoringAlertRead(**a)

        # New alert
        alert_id = uuid4()
        record = {
            "id": alert_id,
            "alert_type": data.alert_type,
            "severity": data.severity,
            "business_case_id": data.business_case_id,
            "task_id": data.task_id,
            "so_id": data.so_id,
            "description": data.description,
            "evidence": data.evidence,
            "suggested_action": data.suggested_action,
            "owner_employee_id": data.owner_employee_id,
            "status": AlertStatus.OPEN.value,
            "acknowledged_by_employee_id": None,
            "acknowledged_at": None,
            "resolved_by_employee_id": None,
            "resolved_at": None,
            "resolution_notes": None,
            "dedup_key": data.dedup_key,
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            payload = {
                **record,
                "id": str(alert_id),
                "business_case_id": str(data.business_case_id) if data.business_case_id else None,
                "so_id": str(data.so_id) if data.so_id else None,
                "owner_employee_id": str(data.owner_employee_id) if data.owner_employee_id else None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            res = self._client.table("bi_monitoring_alerts").insert(payload).execute()
            return MonitoringAlertRead(**res.data[0])

        self._store.bi_monitoring_alerts[str(alert_id)] = record
        return MonitoringAlertRead(**record)

    async def list_alerts(
        self,
        *,
        status: str | None = None,
        alert_type: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MonitoringAlertRead]:
        if self._client:
            q = self._client.table("bi_monitoring_alerts").select("*")
            if status:
                q = q.eq("status", status)
            if alert_type:
                q = q.eq("alert_type", alert_type)
            if severity:
                q = q.eq("severity", severity)
            res = q.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
            return [MonitoringAlertRead(**row) for row in res.data]

        results = [
            MonitoringAlertRead(**a)
            for a in self._store.bi_monitoring_alerts.values()
            if (not status or a["status"] == status)
            and (not alert_type or a["alert_type"] == alert_type)
            and (not severity or a["severity"] == severity)
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def acknowledge_alert(self, alert_id: UUID, employee_id: UUID | None = None) -> None:
        now = datetime.now(UTC)
        aid = str(alert_id)
        if self._client:
            self._client.table("bi_monitoring_alerts").update({
                "status": AlertStatus.ACKNOWLEDGED.value,
                "acknowledged_by_employee_id": str(employee_id) if employee_id else None,
                "acknowledged_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", aid).execute()
        elif aid in self._store.bi_monitoring_alerts:
            self._store.bi_monitoring_alerts[aid]["status"] = AlertStatus.ACKNOWLEDGED.value
            self._store.bi_monitoring_alerts[aid]["acknowledged_by_employee_id"] = employee_id
            self._store.bi_monitoring_alerts[aid]["acknowledged_at"] = now
            self._store.bi_monitoring_alerts[aid]["updated_at"] = now

    async def resolve_alert(self, alert_id: UUID, notes: str | None = None, employee_id: UUID | None = None) -> None:
        now = datetime.now(UTC)
        aid = str(alert_id)
        if self._client:
            self._client.table("bi_monitoring_alerts").update({
                "status": AlertStatus.RESOLVED.value,
                "resolved_by_employee_id": str(employee_id) if employee_id else None,
                "resolved_at": now.isoformat(),
                "resolution_notes": notes,
                "updated_at": now.isoformat(),
            }).eq("id", aid).execute()
        elif aid in self._store.bi_monitoring_alerts:
            self._store.bi_monitoring_alerts[aid]["status"] = AlertStatus.RESOLVED.value
            self._store.bi_monitoring_alerts[aid]["resolved_by_employee_id"] = employee_id
            self._store.bi_monitoring_alerts[aid]["resolved_at"] = now
            self._store.bi_monitoring_alerts[aid]["resolution_notes"] = notes
            self._store.bi_monitoring_alerts[aid]["updated_at"] = now
