"""Email Ingestion Service."""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import structlog

from app.integrations.email_providers.fixture_provider import RawMessage
from app.repositories.email_repo import EmailRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.schemas.email import EmailRecipient, SourceMessageCreate, SourceMessageRead
from app.services.email.preprocessor import EmailPreprocessor
from app.services.intelligence.analyser import EmailAnalysisService

logger = structlog.get_logger(__name__)


@dataclass
class IngestionResult:
    imported_count: int
    duplicate_count: int
    imported_messages: list[SourceMessageRead]
    duplicate_messages: list[str]


class EmailIngestionService:
    SHARED_MAILBOX_PREFIXES = (
        "sales@", "purchase@", "orders@", "support@", "info@", "contact@",
        "commercial@", "dispatch@", "procurement@", "admin@"
    )

    def __init__(
        self,
        email_repo: EmailRepository | None = None,
        auto_analyse: bool = True,
        master_repo: MasterDataRepository | None = None,
    ) -> None:
        self._repo = email_repo or EmailRepository()
        self._master_repo = master_repo or MasterDataRepository()
        self._preprocessor = EmailPreprocessor()
        self._auto_analyse = auto_analyse
        self._analyser = EmailAnalysisService(email_repo=self._repo) if auto_analyse else None

    async def ingest_raw_message(self, mailbox_id: UUID, raw: RawMessage) -> tuple[SourceMessageRead | None, bool]:
        """
        Ingest a single raw message through the unified pipeline:
        Parsing -> Normalization -> Deduplication -> Thread association -> AI analysis ->
        Identity attribution -> Business Case matching -> Task proposals -> Human review.
        """
        log = logger.bind(mailbox_id=str(mailbox_id), provider_id=raw.provider_message_id)

        # 1. Deduplication check by provider_message_id
        existing = await self._repo.find_message_by_provider_id(mailbox_id, raw.provider_message_id)
        if existing:
            log.info("Duplicate message detected by provider_message_id")
            return existing, True

        # 2. Preprocess body & extract structures
        prep = self._preprocessor.preprocess(raw.body_text, raw.sender_address)

        # 3. Deduplication check by body_hash
        existing_hash = await self._repo.find_message_by_body_hash(mailbox_id, prep.body_hash)
        if existing_hash:
            log.info("Duplicate message detected by body_hash", body_hash=prep.body_hash)
            return existing_hash, True

        # 4. Thread association (In-Reply-To, References, Subject, or Thread ID)
        parent_msg = await self._repo.find_parent_thread_message(
            in_reply_to=raw.in_reply_to,
            references=raw.references,
            subject=raw.subject,
            provider_conversation_id=raw.provider_conversation_id,
        )
        conversation_id = parent_msg.conversation_id if parent_msg else None

        # 5. Map recipients
        to_recipients = [
            EmailRecipient(address=r.get("address", ""), display_name=r.get("display_name"))
            for r in raw.to_recipients
            if r.get("address")
        ]
        cc_recipients = [
            EmailRecipient(address=r.get("address", ""), display_name=r.get("display_name"))
            for r in raw.cc_recipients
            if r.get("address")
        ]

        # 6. Persist Message
        create_data = SourceMessageCreate(
            source_mailbox_id=mailbox_id,
            provider_message_id=raw.provider_message_id,
            internet_message_id=raw.internet_message_id.strip("<>") if raw.internet_message_id else None,
            provider_conversation_id=raw.provider_conversation_id,
            in_reply_to=raw.in_reply_to.strip("<>") if raw.in_reply_to else None,
            references=[r.strip("<>") for r in (raw.references or []) if r],
            subject=raw.subject,
            sender_address=raw.sender_address,
            sender_display_name=raw.sender_display_name,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            sent_at=raw.sent_at,
            received_at=raw.received_at,
            body_text=raw.body_text,
            body_preprocessed=prep.cleaned_body,
            quoted_history_text=prep.quoted_history,
            signature_text=prep.signature,
            body_hash=prep.body_hash,
            has_attachments=raw.has_attachments or bool(raw.attachments_metadata),
            is_automated_notification=prep.is_automated,
            fixture_path=raw.source_fixture_path,
            source_type=getattr(raw, "source_type", "EML"),
            attachments_metadata=raw.attachments_metadata,
            meeting_info=raw.meeting_info,
            parsed_tables=raw.parsed_tables or prep.extracted_tables,
        )

        msg = await self._repo.create_source_message(create_data)
        log.info("Message ingested successfully", message_id=str(msg.id))

        # 7. Identity Attribution for Senders & Recipients
        from app.services.context.employee_resolver import EmployeeResolver
        from app.services.email.attachment_service import AttachmentService

        attributed_emp_id = None
        attributed_emp_name = None
        conf = 0.0
        evidence = None

        sender_addr = (raw.sender_address or "").lower()
        is_shared = any(sender_addr.startswith(p) for p in self.SHARED_MAILBOX_PREFIXES)

        if is_shared:
            name_hint = prep.signature_name_hint or raw.sender_display_name
            if name_hint:
                employees = await self._master_repo.list_employees()
                for emp in employees:
                    if emp.is_active:
                        emp_parts = emp.name.lower().split()
                        hint_parts = name_hint.lower().split()
                        if any(hp in emp_parts for hp in hint_parts):
                            attributed_emp_id = emp.id
                            attributed_emp_name = emp.name
                            conf = 0.88
                            evidence = f"Shared mailbox '{sender_addr}' attributed to employee '{emp.name}' via sign-off signature hint '{name_hint}'"
                            break

                if not attributed_emp_name:
                    resolved_hint = EmployeeResolver.resolve_by_name(name_hint)
                    if resolved_hint:
                        attributed_emp_name = resolved_hint["name"]
                        conf = 0.88
                        evidence = f"Shared mailbox '{sender_addr}' attributed to {attributed_emp_name} via sign-off signature hint '{name_hint}'"
        else:
            resolved_sender = EmployeeResolver.resolve_by_email(sender_addr)
            if resolved_sender:
                attributed_emp_name = resolved_sender["name"]
                conf = 0.95
                evidence = f"Sender email '{sender_addr}' matched canonical employee roster for {attributed_emp_name}"

        # If recipient is an employee, match employee id if possible
        employees = await self._master_repo.list_employees()
        if attributed_emp_name and not attributed_emp_id:
            for emp in employees:
                if emp.name.lower() == attributed_emp_name.lower():
                    attributed_emp_id = emp.id
                    break

        if attributed_emp_name or attributed_emp_id:
            await self._repo.update_message_identity_attribution(
                msg.id, attributed_emp_id, attributed_emp_name, conf, evidence
            )
            msg.attributed_employee_id = attributed_emp_id
            msg.attributed_employee_name = attributed_emp_name
            msg.attribution_confidence = conf
            msg.attribution_evidence = evidence

        # 8. Attachment Storage & Line Item Extraction
        attachment_service = AttachmentService()
        extracted_line_items: list[dict[str, Any]] = []

        if raw.attachments_metadata:
            for att in raw.attachments_metadata:
                fname = att.get("filename") or "attachment.dat"
                payload = att.get("payload")
                storage_path = ""
                if payload:
                    try:
                        saved_path = attachment_service.save_attachment(msg.id, fname, payload)
                        storage_path = str(saved_path)
                    except Exception as exc:
                        log.warning("Failed to save attachment payload", filename=fname, error=str(exc))

                # Parse and extract line items from CSV, XLSX, text PDF
                parsed_res = att.get("parsed_data")
                if payload and not parsed_res:
                    parsed_res = attachment_service.parse_and_extract_line_items(payload, fname)

                if parsed_res and isinstance(parsed_res, dict):
                    items = parsed_res.get("line_items", [])
                    if items:
                        extracted_line_items.extend(items)

                # Persist attachment record to bi_source_attachments
                await self._repo.create_attachment_record(
                    message_id=msg.id,
                    filename=fname,
                    content_type=att.get("content_type", "application/octet-stream"),
                    size_bytes=att.get("size_bytes", len(payload) if payload else 0),
                    storage_path=storage_path,
                    parsed_data=parsed_res,
                )

        # 9. Auto-trigger AI Analysis, Business Case Linking & Autonomous Workflow Orchestration
        if self._auto_analyse and self._analyser:
            try:
                log.info("Auto-triggering AI analysis on newly ingested message", message_id=str(msg.id))
                analysis = await self._analyser.analyse_message(msg)
                msg.latest_analysis = analysis

                # Connect to Business Case
                from app.services.context.context_engine import BusinessContextEngine
                from app.services.tasks.task_service import TaskCoordinationService
                from app.services.tasks.workflow_engine import WorkflowCoordinationEngine
                from app.repositories.business_case_repo import BusinessCaseRepository
                from app.repositories.order_repo import OrderRepository
                from app.repositories.task_repo import TaskRepository

                case_repo = BusinessCaseRepository()
                order_repo = OrderRepository()
                task_repo = TaskRepository()
                context_engine = BusinessContextEngine(case_repo=case_repo, order_repo=order_repo)
                task_service = TaskCoordinationService(task_repo=task_repo)
                workflow_engine = WorkflowCoordinationEngine(task_repo=task_repo, master_repo=self._master_repo)

                match_result = await context_engine.resolve_context(msg, analysis, parent_message=parent_msg)
                if match_result and match_result.business_case:
                    case = match_result.business_case
                    await self._repo.update_message_business_case(msg.id, case.id, case.case_number)
                    msg.business_case_id = case.id
                    msg.business_case_number = case.case_number

                    # Orchestrate 13-stage manufacturing workflow tasks and dependencies autonomously
                    await workflow_engine.auto_orchestrate_from_email(
                        message=msg,
                        business_case_id=case.id,
                        extracted_line_items=extracted_line_items,
                    )

                    # Generate any additional specialized task proposals
                    await task_service.generate_proposals_from_analysis(msg, analysis, business_case_id=case.id)

                    # Check for completion suggestions in email body
                    await self._detect_completion_suggestions(msg, prep.cleaned_body, case.id, task_repo)

            except Exception as e:
                log.warning("Auto-analysis / pipeline failed during ingestion", error=str(e), message_id=str(msg.id))

        return msg, False

        return msg, False

    async def _detect_completion_suggestions(self, msg: SourceMessageRead, body: str, case_id: UUID, task_repo: Any) -> None:
        """Detect if email claims completion of existing tasks and propose verification."""
        body_lower = body.lower()
        completion_signals = ["dispatched", "completed", "inspected", "machined", "assembled", "delivered", "finished", "shipped"]
        if not any(sig in body_lower for sig in completion_signals):
            return

        open_tasks = await task_repo.list_legacy_tasks(case_id=case_id)
        for t in open_tasks:
            if t.status not in ("completed", "completed_reported", "completed_verified", "cancelled"):
                # Propose task completion verification
                from app.schemas.task import TaskProposalCreate
                await task_repo.create_proposal(
                    TaskProposalCreate(
                        source_message_id=msg.id,
                        business_case_id=case_id,
                        title=f"Verify completion of Task {t.task_id} ({t.description})",
                        description=f"Email claims work completed. Evidence in message: '{body[:150]}...'",
                        task_type="VERIFICATION",
                        suggested_department=t.department or "Quality",
                        priority="HIGH",
                        action_evidence=f"Completion mentioned in email: {msg.subject}",
                        confidence=0.85,
                        proposal_status="PENDING",
                    )
                )

    async def ingest_batch(self, mailbox_id: UUID, raw_messages: list[RawMessage]) -> IngestionResult:
        imported: list[SourceMessageRead] = []
        duplicates: list[str] = []

        for raw in raw_messages:
            msg, is_dup = await self.ingest_raw_message(mailbox_id, raw)
            if is_dup:
                duplicates.append(raw.provider_message_id)
            elif msg:
                imported.append(msg)

        return IngestionResult(
            imported_count=len(imported),
            duplicate_count=len(duplicates),
            imported_messages=imported,
            duplicate_messages=duplicates,
        )
