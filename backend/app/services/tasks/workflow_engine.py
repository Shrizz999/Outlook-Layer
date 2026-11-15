"""Automated Manufacturing Workflow & Dependency Coordination Engine.

Implements autonomous analysis, task creation, and dependency graph generation
without human intervention. Enforces full traceability across the 13-stage
manufacturing order lifecycle:
Customer Enquiry -> Swapnali registers -> Ganesh checks part details ->
Engineering confirms technical specs -> Swapnali prepares quotation ->
Customer approves quotation -> Ganesh verifies customer PO ->
Vaibhav coordinates SO booking -> PPC checks material availability ->
Procurement arranges shortage material -> Stores confirms material receipt ->
Production completes work -> Quality checks finished goods ->
Dispatch ships order.

Identifies active bottlenecks and holding employees with full auditability.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog

from app.domain.enums import Priority
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.email import SourceMessageRead
from app.schemas.task import TaskDependencyCreate
from app.services.context.employee_resolver import EmployeeResolver

logger = structlog.get_logger(__name__)

MANUFACTURING_WORKFLOW_STAGES = [
    {
        "stage": "ENQUIRY_REGISTRATION",
        "title": "Register Customer Enquiry & Extract Line Items",
        "default_owner": "Swapnali",
        "department": "Sales Operations",
        "priority": "HIGH",
        "duration_days": 1,
    },
    {
        "stage": "PART_DETAILS_CHECK",
        "title": "Check Part Details, OEM Codes & Catalogue References",
        "default_owner": "Ganesh",
        "department": "Sales Operations",
        "priority": "HIGH",
        "duration_days": 1,
    },
    {
        "stage": "ENGINEERING_CONFIRMATION",
        "title": "Confirm Technical Specifications & Drawing Tolerances",
        "default_owner": "Frank Engineering",
        "department": "Engineering",
        "priority": "NORMAL",
        "duration_days": 2,
    },
    {
        "stage": "QUOTATION_PREPARATION",
        "title": "Prepare Commercial Quotation & Submit to Customer",
        "default_owner": "Swapnali",
        "department": "Sales Operations",
        "priority": "HIGH",
        "duration_days": 1,
    },
    {
        "stage": "CUSTOMER_APPROVAL",
        "title": "Customer Quotation Review & Commercial Approval",
        "default_owner": "Customer",
        "department": "Sales Operations",
        "priority": "NORMAL",
        "duration_days": 3,
    },
    {
        "stage": "PO_VERIFICATION",
        "title": "Verify Customer Purchase Order (PO) vs Quotation",
        "default_owner": "Ganesh",
        "department": "Sales Operations",
        "priority": "HIGH",
        "duration_days": 1,
    },
    {
        "stage": "SO_BOOKING",
        "title": "Coordinate Sales Order (SO) Booking & Capacity Allocation",
        "default_owner": "Vaibhav",
        "department": "Sales Operations",
        "priority": "CRITICAL",
        "duration_days": 1,
    },
    {
        "stage": "PPC_MATERIAL_CHECK",
        "title": "Check Material Availability & Schedule Assembly Capacity",
        "default_owner": "Bob PPC",
        "department": "PPC",
        "priority": "HIGH",
        "duration_days": 1,
    },
    {
        "stage": "PROCUREMENT_SHORTAGE",
        "title": "Arrange Shortage Raw Material & Vendor Procurement",
        "default_owner": "Alice Purchase",
        "department": "Purchase",
        "priority": "HIGH",
        "duration_days": 3,
    },
    {
        "stage": "STORES_RECEIPT",
        "title": "Confirm Material Receipt & Allocate Free Usable Stock",
        "default_owner": "Stores Desk",
        "department": "Stores",
        "priority": "NORMAL",
        "duration_days": 1,
    },
    {
        "stage": "PRODUCTION_EXECUTION",
        "title": "Complete Machining, Cutting & Assembly Production",
        "default_owner": "Carol Production",
        "department": "Production",
        "priority": "NORMAL",
        "duration_days": 4,
    },
    {
        "stage": "QUALITY_INSPECTION",
        "title": "Inspect Finished Goods & Issue Quality Test Certificate",
        "default_owner": "David Quality",
        "department": "Quality",
        "priority": "HIGH",
        "duration_days": 1,
    },
    {
        "stage": "DISPATCH_SHIPPING",
        "title": "Ship Order, Delivery Challan & Logistics Dispatch",
        "default_owner": "Emma Dispatch",
        "department": "Dispatch",
        "priority": "NORMAL",
        "duration_days": 1,
    },
]


class WorkflowCoordinationEngine:
    """Coordinates automated task creation, dependencies, and bottleneck identification."""

    def __init__(
        self,
        task_repo: TaskRepository | None = None,
        master_repo: MasterDataRepository | None = None,
    ) -> None:
        self._task_repo = task_repo or TaskRepository()
        self._master_repo = master_repo or MasterDataRepository()

    async def auto_orchestrate_from_email(
        self,
        message: SourceMessageRead,
        business_case_id: UUID,
        extracted_line_items: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Automatically analyzes the email and its attachments, creates workflow tasks
        and dependencies without human intervention, updates completion states,
        and identifies the active operational bottleneck.
        """
        log = logger.bind(message_id=str(message.id), case_id=str(business_case_id))
        log.info("Auto-orchestrating manufacturing workflow from email")

        # 1. Check existing tasks for this Business Case
        existing_tasks = await self._task_repo.list_legacy_tasks(case_id=business_case_id, limit=100)

        # Build part & reference context summary
        line_summary = []
        if extracted_line_items:
            for item in extracted_line_items[:10]:
                part = item.get("part_number") or ""
                qty = item.get("quantity") or ""
                uom = item.get("uom") or "Nos"
                if part:
                    line_summary.append(f"{part} (Qty: {qty} {uom})")

        part_context_str = "; ".join(line_summary) if line_summary else (message.subject or "Manufacturing Order Item")

        # Extract explicit deadline from email body if mentioned (e.g. "by 10-Nov", "till 15-Dec")
        extracted_deadline = self._extract_deadline_from_text(f"{message.subject or ''} {message.body_preprocessed or ''}")

        created_tasks: list[dict[str, Any]] = []

        # 2. Case A: Initialize full workflow if no tasks exist yet
        if not existing_tasks:
            created_tasks = await self._instantiate_full_workflow(
                business_case_id=business_case_id,
                message=message,
                part_context=part_context_str,
                extracted_deadline=extracted_deadline,
            )
            return created_tasks

        # 3. Case B: Workflow already exists -> Progress workflow or add inter-employee directives
        await self._progress_existing_workflow(
            existing_tasks=existing_tasks,
            message=message,
            business_case_id=business_case_id,
            extracted_deadline=extracted_deadline,
        )

        return [t.model_dump() for t in await self._task_repo.list_legacy_tasks(case_id=business_case_id, limit=100)]

    async def _instantiate_full_workflow(
        self,
        business_case_id: UUID,
        message: SourceMessageRead,
        part_context: str,
        extracted_deadline: str | None,
    ) -> list[dict[str, Any]]:
        """Instantiates all 13 stages of the manufacturing workflow with strict sequential dependencies."""
        today = date.today()
        cumulative_date = today

        created_tasks = []
        previous_task_id: str | None = None

        # Determine who received or sent the email
        recipient_emp = EmployeeResolver.resolve_by_text(str(message.to_recipients)) or EmployeeResolver.resolve_by_name("Swapnali")
        sender_emp = EmployeeResolver.resolve_by_email(message.sender_address) or EmployeeResolver.resolve_by_text(message.signature_text)

        assigner_name = sender_emp["name"] if sender_emp else (message.sender_display_name or message.sender_address or "Customer")

        for idx, stage_def in enumerate(MANUFACTURING_WORKFLOW_STAGES):
            task_id = self._task_repo.generate_task_id()
            duration = stage_def["duration_days"]
            target_deadline = (today + timedelta(days=duration)).isoformat() if idx == 0 and extracted_deadline else (cumulative_date + timedelta(days=duration)).isoformat()
            cumulative_date += timedelta(days=duration)

            owner_name = stage_def["default_owner"]
            if idx == 0 and recipient_emp:
                owner_name = recipient_emp["name"]

            # Initial status: Stage 0 is completed (enquiry received/registered),
            # Stage 1 is in_progress (active bottleneck),
            # Subsequent stages are pending (blocked by predecessor)
            if idx == 0:
                task_status = "completed"
            elif idx == 1:
                task_status = "in_progress"
            else:
                task_status = "pending"

            full_desc = f"{stage_def['title']} | Context: {part_context}"

            task_dict = {
                "task_id": task_id,
                "date": today.isoformat(),
                "description": full_desc,
                "assigned_to": owner_name,
                "assigned_by": assigner_name if idx == 0 else MANUFACTURING_WORKFLOW_STAGES[idx - 1]["default_owner"],
                "department": stage_def["department"],
                "deadline": extracted_deadline if (idx == 0 and extracted_deadline) else target_deadline,
                "priority": stage_def["priority"],
                "status": task_status,
                "reason": f"Workflow Stage {idx + 1}/13: {stage_def['stage']}",
                "source": message.subject or f"Email {message.id}",
                "business_case_id": business_case_id,
                "verification_status": "VERIFIED" if task_status == "completed" else "UNVERIFIED",
            }

            created_task = await self._task_repo.create_task_raw(task_dict)
            created_tasks.append(created_task)

            # Link Dependency: previous_task -> current_task
            if previous_task_id:
                dep_data = TaskDependencyCreate(
                    predecessor_type="TASK",
                    predecessor_task_id=previous_task_id,
                    successor_type="TASK",
                    successor_task_id=task_id,
                    dependency_type="FINISH_TO_START",
                    is_blocking=True,
                    reason=f"{owner_name} cannot start '{stage_def['stage']}' until {MANUFACTURING_WORKFLOW_STAGES[idx - 1]['default_owner']} completes '{MANUFACTURING_WORKFLOW_STAGES[idx - 1]['stage']}'",
                )
                await self._task_repo.create_dependency(dep_data)

            previous_task_id = task_id

        logger.info(
            "Created full 13-stage manufacturing workflow dependencies automatically",
            case_id=str(business_case_id),
            tasks_count=len(created_tasks),
        )
        return created_tasks

    async def _progress_existing_workflow(
        self,
        existing_tasks: list[Any],
        message: SourceMessageRead,
        business_case_id: UUID,
        extracted_deadline: str | None,
    ) -> None:
        """
        Advances task completion or injects cross-employee directives when subsequent
        emails arrive within the same Business Case.
        """
        body_lower = (message.body_preprocessed or message.body_text or "").lower()
        sender_emp = EmployeeResolver.resolve_by_email(message.sender_address) or EmployeeResolver.resolve_by_text(message.signature_text or message.body_preprocessed)
        sender_name = sender_emp["name"] if sender_emp else (message.sender_display_name or "Internal Staff")

        # 1. Detect if email claims completion of a stage
        completion_signals = [
            ("stock check completed", "STORES_RECEIPT", "Stores Desk"),
            ("drawing approved", "ENGINEERING_CONFIRMATION", "Frank Engineering"),
            ("part verified", "PART_DETAILS_CHECK", "Ganesh"),
            ("quotation submitted", "QUOTATION_PREPARATION", "Swapnali"),
            ("po verified", "PO_VERIFICATION", "Ganesh"),
            ("so booked", "SO_BOOKING", "Vaibhav"),
            ("capacity confirmed", "PPC_MATERIAL_CHECK", "Bob PPC"),
            ("material received", "STORES_RECEIPT", "Stores Desk"),
            ("machining completed", "PRODUCTION_EXECUTION", "Carol Production"),
            ("inspection passed", "QUALITY_INSPECTION", "David Quality"),
            ("order dispatched", "DISPATCH_SHIPPING", "Emma Dispatch"),
        ]

        completed_any = False
        for signal_text, stage_key, owner_hint in completion_signals:
            if signal_text in body_lower or (owner_hint.lower() in sender_name.lower() and any(w in body_lower for w in ["completed", "done", "confirmed", "passed"])):
                # Locate matching task
                for t in existing_tasks:
                    if stage_key in (t.reason or "") and t.status != "completed":
                        await self._task_repo.update_task_status(t.task_id, "completed")
                        completed_any = True
                        logger.info("Marked workflow task completed via email evidence", task_id=t.task_id, stage=stage_key)
                        break

        # 2. Advance next dependent task to 'in_progress'
        if completed_any:
            # Re-fetch tasks to see new state
            updated_tasks = await self._task_repo.list_legacy_tasks(case_id=business_case_id, limit=100)
            deps = await self._task_repo.list_dependencies()
            for t in updated_tasks:
                if t.status == "pending":
                    # Check if all predecessors are completed
                    pred_task_ids = [d.predecessor_task_id for d in deps if d.successor_task_id == t.task_id and d.status == "ACTIVE"]
                    all_preds_done = all(
                        any(p.task_id == pid and p.status in ("completed", "completed_reported", "completed_verified") for p in updated_tasks)
                        for pid in pred_task_ids
                    )
                    if all_preds_done and pred_task_ids:
                        await self._task_repo.update_task_status(t.task_id, "in_progress")
                        logger.info("Advanced dependent task to in_progress", task_id=t.task_id, owner=t.assigned_to)
                        break

        # 3. Detect internal inter-employee delegated directives (e.g. "PPC: confirm sequence by 10-Nov")
        for directive_match in re.finditer(r"\b(PPC|Stores|Production|Quality|Engineering|Purchase|Ganesh|Swapnali|Vaibhav)[:\s]+([^.\n\r]+)", message.body_preprocessed or "", re.IGNORECASE):
            target_role = directive_match.group(1).strip()
            instruction = directive_match.group(2).strip()
            target_emp = EmployeeResolver.resolve_by_name(target_role) or EmployeeResolver.get_employee_for_stage(target_role)

            if target_emp and len(instruction) > 10:
                directive_task_id = self._task_repo.generate_task_id()
                await self._task_repo.create_task_raw({
                    "task_id": directive_task_id,
                    "date": date.today().isoformat(),
                    "description": f"Direct Directive: {instruction}",
                    "assigned_to": target_emp["name"],
                    "assigned_by": sender_name,
                    "department": target_emp["department"],
                    "deadline": extracted_deadline or (date.today() + timedelta(days=2)).isoformat(),
                    "priority": "HIGH",
                    "status": "in_progress",
                    "reason": f"Inter-employee task delegated from {sender_name} to {target_emp['name']}",
                    "source": message.subject or f"Directive from {sender_name}",
                    "business_case_id": business_case_id,
                    "verification_status": "UNVERIFIED",
                })
                logger.info("Created inter-employee delegated task", task_id=directive_task_id, assigned_to=target_emp["name"], assigned_by=sender_name)

    async def get_workflow_traceability(self, business_case_id: UUID) -> dict[str, Any]:
        """
        Calculates end-to-end workflow traceability, identifying which tasks are completed,
        which are pending, and which employee is currently holding up the pipeline (the bottleneck).
        """
        tasks = await self._task_repo.list_legacy_tasks(case_id=business_case_id, limit=100)
        if not tasks:
            return {
                "business_case_id": str(business_case_id),
                "total_tasks": 0,
                "completed_tasks": 0,
                "progress_percentage": 0,
                "active_bottleneck": None,
                "timeline": [],
            }

        deps = await self._task_repo.list_dependencies()
        dep_map = {d.successor_task_id: d.predecessor_task_id for d in deps if d.status == "ACTIVE"}

        completed_count = 0
        active_bottleneck = None
        timeline = []

        for t in tasks:
            is_done = t.status in ("completed", "completed_reported", "completed_verified")
            if is_done:
                completed_count += 1
            elif not active_bottleneck and t.status in ("in_progress", "blocked", "pending"):
                active_bottleneck = {
                    "task_id": t.task_id,
                    "title": t.description,
                    "bottleneck_employee": t.assigned_to,
                    "department": t.department,
                    "status": t.status,
                    "deadline": t.deadline,
                    "reason": f"{t.assigned_to} is currently working on this task; downstream departments are waiting for completion.",
                }

            timeline.append({
                "task_id": t.task_id,
                "description": t.description,
                "assigned_to": t.assigned_to,
                "assigned_by": t.assigned_by,
                "department": t.department,
                "status": t.status,
                "deadline": t.deadline,
                "is_completed": is_done,
                "predecessor_task_id": dep_map.get(t.task_id),
            })

        progress_pct = int((completed_count / len(tasks)) * 100) if tasks else 0

        return {
            "business_case_id": str(business_case_id),
            "total_tasks": len(tasks),
            "completed_tasks": completed_count,
            "progress_percentage": progress_pct,
            "active_bottleneck": active_bottleneck,
            "timeline": timeline,
        }

    async def get_active_bottlenecks_across_cases(self) -> list[dict[str, Any]]:
        """Collect active bottlenecks across all active business cases."""
        tasks = await self._task_repo.list_legacy_tasks(limit=500)
        case_ids = set()
        for t in tasks:
            if t.business_case_id:
                case_ids.add(t.business_case_id)

        bottlenecks = []
        for cid in case_ids:
            trace = await self.get_workflow_traceability(cid)
            if trace.get("active_bottleneck"):
                b = trace["active_bottleneck"]
                b["business_case_id"] = str(cid)
                b["progress_percentage"] = trace.get("progress_percentage", 0)
                bottlenecks.append(b)
        return bottlenecks

    def _extract_deadline_from_text(self, text: str) -> str | None:
        """Extract explicit dates such as '10-Nov', '2026-11-15', 'by Friday'."""
        # Match standard ISO format
        m_iso = re.search(r"\b(202\d-\d{2}-\d{2})\b", text)
        if m_iso:
            return m_iso.group(1)

        # Match e.g. '10-Nov' or '15-Dec'
        m_month = re.search(r"\b(\d{1,2})[-\s](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", text, re.IGNORECASE)
        if m_month:
            day = int(m_month.group(1))
            month_str = m_month.group(2).capitalize()[:3]
            months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
            m_num = months.get(month_str, 11)
            return f"2026-{m_num:02d}-{day:02d}"

        return None
