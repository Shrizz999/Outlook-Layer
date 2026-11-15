"""
Database and In-Memory Data Store Abstraction.
Allows the application to run against live Supabase or in-memory mock store.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class InMemoryStore:
    """
    In-memory storage engine simulating Supabase tables.
    Used for local testing, CI, and when no live Supabase credentials are provided.
    """

    def __init__(self) -> None:
        self._init_tables()

    def _init_tables(self) -> None:
        # Legacy tables simulation
        self.employees: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.task_history: dict[str, dict[str, Any]] = {}
        self.workflows: dict[str, dict[str, Any]] = {}
        self.task_dependencies: dict[str, dict[str, Any]] = {}
        self.purchase_orders: dict[str, dict[str, Any]] = {}
        self.inventory: dict[str, dict[str, Any]] = {}
        self.part_vendors: dict[str, dict[str, Any]] = {}

        # Balbird Intelligence (bi_*) tables
        self.bi_departments: dict[str, dict[str, Any]] = {}
        self.bi_user_profiles: dict[str, dict[str, Any]] = {}
        self.bi_customers: dict[str, dict[str, Any]] = {}
        self.bi_suppliers: dict[str, dict[str, Any]] = {}
        self.bi_parts: dict[str, dict[str, Any]] = {}
        self.bi_business_cases: dict[str, dict[str, Any]] = {}
        self.bi_case_parties: dict[str, dict[str, Any]] = {}
        self.bi_case_links: dict[str, dict[str, Any]] = {}
        self.bi_source_mailboxes: dict[str, dict[str, Any]] = {}
        self.bi_conversations: dict[str, dict[str, Any]] = {}
        self.bi_source_messages: dict[str, dict[str, Any]] = {}
        self.bi_source_attachments: dict[str, dict[str, Any]] = {}
        self.bi_email_analyses: dict[str, dict[str, Any]] = {}
        self.bi_extracted_facts: dict[str, dict[str, Any]] = {}
        self.bi_commitments: dict[str, dict[str, Any]] = {}
        self.bi_processing_jobs: dict[str, dict[str, Any]] = {}
        self.bi_ai_usage: dict[str, dict[str, Any]] = {}
        self.bi_review_queue: dict[str, dict[str, Any]] = {}
        self.bi_imports: dict[str, dict[str, Any]] = {}
        self.bi_sales_orders: dict[str, dict[str, Any]] = {}
        self.bi_sales_order_lines: dict[str, dict[str, Any]] = {}
        self.bi_rfqs: dict[str, dict[str, Any]] = {}
        self.bi_rfq_lines: dict[str, dict[str, Any]] = {}
        self.bi_purchase_order_ext: dict[str, dict[str, Any]] = {}
        self.bi_purchase_order_lines: dict[str, dict[str, Any]] = {}
        self.bi_mrp_snapshots: dict[str, dict[str, Any]] = {}
        self.bi_mrp_records: dict[str, dict[str, Any]] = {}
        self.bi_task_proposals: dict[str, dict[str, Any]] = {}
        self.bi_task_metadata: dict[str, dict[str, Any]] = {}
        self.bi_task_sources: dict[str, dict[str, Any]] = {}
        self.bi_task_assignment_history: dict[str, dict[str, Any]] = {}
        self.bi_task_updates: dict[str, dict[str, Any]] = {}
        self.bi_dependencies: dict[str, dict[str, Any]] = {}
        self.bi_smart_drafts: dict[str, dict[str, Any]] = {}
        self.bi_monitoring_alerts: dict[str, dict[str, Any]] = {}
        self.bi_audit_events: dict[str, dict[str, Any]] = {}
        self.bi_human_feedback: dict[str, dict[str, Any]] = {}
        self.bi_department_hods: dict[str, dict[str, Any]] = {}
        self.bi_task_handovers: dict[str, dict[str, Any]] = {}
        self.bi_physical_verifications: dict[str, dict[str, Any]] = {}

        # Auth & RBAC tables
        self.user_accounts: dict[str, dict[str, Any]] = {}
        self.role_requests: dict[str, dict[str, Any]] = {}
        self.user_sessions: dict[str, dict[str, Any]] = {}
        self.user_audit_logs: dict[str, dict[str, Any]] = {}
        self.login_rate_limits: dict[str, list[float]] = {}

        # Multi-User Microsoft Outlook tables
        self.microsoft_connections: dict[str, dict[str, Any]] = {}
        self.email_folders: dict[str, dict[str, Any]] = {}
        self.email_messages: dict[str, dict[str, Any]] = {}
        self.email_folder_sync_state: dict[str, dict[str, Any]] = {}
        self.email_sync_runs: dict[str, dict[str, Any]] = {}
        self.email_analysis_results: dict[str, dict[str, Any]] = {}
        self.email_drafts: dict[str, dict[str, Any]] = {}
        self.email_send_audit_events: dict[str, dict[str, Any]] = {}
        self.bi_external_task_mappings: dict[str, dict[str, Any]] = {}

        self._case_seq = 1

    def generate_case_number(self, year: str = "2026") -> str:
        num = f"CASE-{year}-{self._case_seq:05d}"
        self._case_seq += 1
        return num

    def clear(self) -> None:
        """Clear all records (for test isolation)."""
        self._init_tables()


_global_store: InMemoryStore | None = None


def get_store() -> InMemoryStore:
    global _global_store
    if _global_store is None:
        _global_store = InMemoryStore()
    return _global_store


def get_supabase_client():
    """Returns a Supabase client if configured, else None."""
    settings = get_settings()
    if settings.supabase_configured:
        try:
            from supabase import create_client
            key = settings.supabase_service_role_key or settings.supabase_anon_key
            return create_client(settings.supabase_url, key)
        except Exception as exc:
            logger.warning("Failed to create Supabase client", error=str(exc))
    return None
