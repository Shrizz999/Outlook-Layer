"""Admin and Dashboard Diagnostics Routes."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.repositories.alert_repo import AlertRepository
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.email_repo import EmailRepository
from app.repositories.task_repo import TaskRepository

router = APIRouter()


@router.get("/dashboard-summary")
async def get_dashboard_summary() -> dict:
    """Aggregates metrics for the executive and departmental dashboards."""
    case_repo = BusinessCaseRepository()
    email_repo = EmailRepository()
    task_repo = TaskRepository()
    alert_repo = AlertRepository()

    cases = await case_repo.list_cases(limit=100)
    messages = await email_repo.list_messages(limit=100)
    tasks = await task_repo.list_legacy_tasks(limit=100)
    proposals = await task_repo.list_proposals(limit=100)
    alerts = await alert_repo.list_alerts(limit=100)

    open_cases = [c for c in cases if c.status not in ("COMPLETED", "CANCELLED", "ARCHIVED")]
    pending_emails = [m for m in messages if m.processing_status in ("PENDING", "NEEDS_REVIEW")]
    pending_proposals = [p for p in proposals if p.proposal_status == "PENDING"]
    active_tasks = [t for t in tasks if t.status not in ("completed", "completed_reported", "completed_verified", "cancelled")]
    overdue_tasks = [t for t in active_tasks if t.deadline and t.deadline < "2026-11-06"]
    blocked_tasks = [t for t in active_tasks if t.status == "blocked"]
    open_alerts = [a for a in alerts if a.status == "OPEN"]

    # Workload by department
    dept_workload: dict[str, int] = {}
    for t in active_tasks:
        d = t.department or "General"
        dept_workload[d] = dept_workload.get(d, 0) + 1

    return {
        "metrics": {
            "open_cases_count": len(open_cases),
            "pending_emails_count": len(pending_emails),
            "pending_proposals_count": len(pending_proposals),
            "active_tasks_count": len(active_tasks),
            "overdue_tasks_count": len(overdue_tasks),
            "blocked_tasks_count": len(blocked_tasks),
            "open_alerts_count": len(open_alerts),
        },
        "department_workload": dept_workload,
        "recent_alerts": [a.model_dump() for a in open_alerts[:5]],
        "recent_cases": [c.model_dump() for c in open_cases[:5]],
    }


@router.get("/ai-usage")
async def get_ai_usage() -> dict:
    settings = get_settings()
    return {
        "provider": settings.ai_provider,
        "model": settings.openrouter_model if settings.ai_provider == "openrouter" else "N/A (mock)",
        "max_requests_per_day": settings.openrouter_max_requests_per_day,
        "max_requests_per_minute": settings.openrouter_max_requests_per_minute,
        "note": "API keys are protected on the backend and never exposed to the frontend or logs",
    }


@router.get("/system-status")
async def get_system_status() -> dict:
    settings = get_settings()
    return {
        "environment": settings.app_env,
        "ai_provider": settings.ai_provider,
        "email_provider": settings.email_provider,
        "supabase_configured": settings.supabase_configured,
        "version": "0.1.0-poc",
    }
