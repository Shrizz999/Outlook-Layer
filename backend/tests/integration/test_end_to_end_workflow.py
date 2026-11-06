"""
Canonical End-to-End Workflow Integration Test.
Verifies the complete vertical slice:
Email Ingestion -> AI Analysis -> Context Resolution -> Business Case ->
Task Proposals -> Legacy Task Approval -> Dependencies -> MRP Shortage Alert -> Smart Draft.
"""
import pytest
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.enums import TaskProposalStatus, TaskStatus
from app.integrations.ai_providers.provider import MockAIProvider
from app.integrations.email_providers.fixture_provider import RawMessage
from app.repositories.alert_repo import AlertRepository
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.email_repo import EmailRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.store import get_store
from app.repositories.task_repo import TaskRepository
from app.schemas.order import MRPRecordBase, SalesOrderCreate, SalesOrderLineBase
from app.schemas.task import TaskDependencyCreate, TaskProposalCreate
from app.services.context.context_engine import BusinessContextEngine
from app.services.drafts.draft_service import SmartDraftService
from app.services.email.ingestion import EmailIngestionService
from app.services.intelligence.analyser import EmailAnalysisService
from app.services.monitoring.risk_engine import MonitoringRiskEngine
from app.services.tasks.task_service import TaskCoordinationService


@pytest.fixture(autouse=True)
def clean_store():
    get_store().clear()


@pytest.mark.asyncio
async def test_complete_end_to_end_poc_lifecycle():
    # 0. Initialize Repositories and Services
    email_repo = EmailRepository()
    case_repo = BusinessCaseRepository()
    order_repo = OrderRepository()
    task_repo = TaskRepository()
    alert_repo = AlertRepository()

    ingestion_service = EmailIngestionService(email_repo)
    analysis_service = EmailAnalysisService(ai_provider=MockAIProvider(), email_repo=email_repo)
    context_engine = BusinessContextEngine(case_repo=case_repo, order_repo=order_repo)
    task_service = TaskCoordinationService(task_repo=task_repo)
    risk_engine = MonitoringRiskEngine(alert_repo=alert_repo, task_repo=task_repo, order_repo=order_repo)
    draft_service = SmartDraftService(case_repo=case_repo, order_repo=order_repo)

    # 1. Setup Order & MRP Reference Data
    so = await order_repo.create_sales_order(
        SalesOrderCreate(
            so_number="SO-1025",
            source_customer_name="Acme Engineering Ltd",
            order_date=date(2026, 11, 1),
            requested_delivery_date=date(2026, 11, 28),
            status="OPEN",
            lines=[
                SalesOrderLineBase(
                    line_number=1,
                    source_part_number="HT-2045",
                    description="Hydraulic Tube 20x4.5mm",
                    ordered_quantity=Decimal("100"),
                    unit_of_measure="MTR",
                )
            ],
        )
    )

    await order_repo.create_mrp_snapshot(
        "MRP_Snapshot.xlsx",
        [
            MRPRecordBase(
                source_part_number="HT-2045",
                available_stock=Decimal("60"),
                required_quantity=Decimal("100"),
                shortage_quantity_computed=Decimal("40"),
            )
        ],
    )

    # 2. Ingest Customer Email
    mailbox_id = await email_repo.get_or_create_default_mailbox("FIXTURE")
    raw_email = RawMessage(
        provider_message_id="MSG-E2E-001",
        internet_message_id="<msg-e2e-001@acme.invalid>",
        provider_conversation_id="CONV-1025",
        subject="Enquiry for 100m HT-2045 - SO-1025",
        sender_address="buyer@acme.invalid",
        sender_display_name="Acme Buyer",
        to_recipients=[{"address": "sales@balbird.invalid"}],
        cc_recipients=[],
        sent_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        received_at=datetime(2026, 11, 1, 10, 1, tzinfo=UTC),
        body_text="Hello Sales, please confirm delivery for 100m of HT-2045 on SO-1025. Please confirm ASAP.",
        has_attachments=False,
    )

    msg, is_dup = await ingestion_service.ingest_raw_message(mailbox_id, raw_email)
    assert is_dup is False
    assert msg is not None

    # Idempotency / Duplicate Check
    _, is_dup2 = await ingestion_service.ingest_raw_message(mailbox_id, raw_email)
    assert is_dup2 is True

    # 3. AI Analysis
    analysis = await analysis_service.analyse_message(msg)
    assert analysis.domain is not None
    assert any(r["value"] == "SO-1025" for r in analysis.raw_structured_output.get("references", []))

    # 4. Context Resolution -> Match with SO-1025 & Business Case
    match_result = await context_engine.resolve_context(msg, analysis)
    assert match_result.is_new_case is True
    assert match_result.match_method == "EXACT_SO"
    case = match_result.business_case
    assert case.case_number.startswith("CASE-2026-")

    # 5. Task Proposals Generated
    proposals = await task_service.generate_proposals_from_analysis(msg, analysis, business_case_id=case.id)
    assert len(proposals) > 0
    prop = proposals[0]
    assert prop.proposal_status == TaskProposalStatus.PENDING.value

    # 6. Human Approval -> Creates Authoritative Record in Legacy tasks table
    reviewer_uuid = uuid4()
    approved_task = await task_service.approve_proposal(
        proposal_id=prop.id,
        reviewer_id=reviewer_uuid,
        assigned_to_name="John Sales",
        deadline="2026-11-15",
    )

    assert approved_task.task_id.startswith("TASK-")
    assert approved_task.assigned_to == "John Sales"
    assert approved_task.status == TaskStatus.ASSIGNED.value

    # Verify task exists in legacy tasks table repository
    retrieved_task = await task_repo.get_task_by_id(approved_task.task_id)
    assert retrieved_task is not None
    assert retrieved_task.task_id == approved_task.task_id
    assert retrieved_task.business_case_id == case.id

    # 7. Add PPC Schedule Task & Dependency
    second_prop = await task_repo.create_proposal(
        TaskProposalCreate(
            title="Schedule tube cutting in PPC",
            task_type="PPC",
            suggested_department="PPC",
            business_case_id=case.id,
        )
    )
    ppc_task = await task_service.approve_proposal(
        second_prop.id,
        reviewer_id=reviewer_uuid,
        assigned_to_name="Bob PPC",
    )

    dep = await task_service.add_dependency_with_cycle_check(
        TaskDependencyCreate(
            predecessor_task_id=approved_task.task_id,
            successor_task_id=ppc_task.task_id,
            dependency_type="BLOCKS",
            is_blocking=True,
            reason="PPC schedule depends on technical clarification completion",
        )
    )
    assert dep.id is not None
    assert dep.is_blocking is True

    # 8. MRP Shortage Alert
    alert = await risk_engine.evaluate_material_shortage("SO-1025", "HT-2045", business_case_id=case.id)
    assert alert is not None
    assert alert.alert_type == "MATERIAL_SHORTAGE"
    assert "Material shortage of 40 units" in alert.description

    # 9. Smart Draft for Supplier Follow-up
    draft = await draft_service.generate_supplier_followup_draft(
        case_id=case.id,
        supplier_name="Apex Tube Mills",
        part_number="HT-2045",
        so_number="SO-1025",
    )
    assert "Delivery Status Clarification — Part HT-2045" in draft.subject
    assert "Quantity: 100" in draft.body
    assert draft.template_key == "SUPPLIER_DELIVERY_FOLLOWUP"
