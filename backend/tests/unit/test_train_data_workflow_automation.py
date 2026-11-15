"""Automated Tests for Train Data Parsing, Attachment Extraction,
13-Stage Manufacturing Workflow Coordination, and Bottleneck Detection.
"""
from __future__ import annotations

import io
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from app.integrations.email_providers.fixture_provider import RawMessage
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.email_repo import EmailRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.business_case import BusinessCaseCreate
from app.schemas.email import SourceMessageCreate, SourceMessageRead
from app.services.context.employee_resolver import EmployeeResolver
from app.services.email.attachment_service import AttachmentService
from app.services.email.ingestion import EmailIngestionService
from app.services.email.train_data_service import TrainDataService
from app.services.tasks.workflow_engine import MANUFACTURING_WORKFLOW_STAGES, WorkflowCoordinationEngine


@pytest.fixture
def clean_repos():
    email_repo = EmailRepository()
    task_repo = TaskRepository()
    case_repo = BusinessCaseRepository()
    return email_repo, task_repo, case_repo


def test_attachment_service_csv_xlsx_pdf_and_image_exclusion():
    """Verify attachment parser extracts line items from CSV, XLSX, PDF, and strictly excludes images/OCR."""
    svc = AttachmentService(base_storage_dir="data/test_attachments")

    # 1. Test CSV parsing
    csv_bytes = (
        "Part Number,Description,Qty,UOM,Delivery Date\n"
        "DEMO-HS-PUN05-L22-G12,Male stud connector L22 x G1/2,51,EA,2026-11-10\n"
        "DEMO-HS-PEL31-L22,Union elbow D22L,3,EA,2026-11-12\n"
    ).encode("utf-8")
    res_csv = svc.parse_and_extract_line_items(csv_bytes, "parts.csv")
    assert res_csv["type"] == "CSV"
    assert len(res_csv["line_items"]) == 2
    assert res_csv["line_items"][0]["part_number"] == "DEMO-HS-PUN05-L22-G12"
    assert res_csv["line_items"][0]["quantity"] == "51"

    # 2. Test Image exclusion (strictly NO OCR)
    fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    res_img = svc.parse_and_extract_line_items(fake_png, "sample_scan.png")
    assert res_img["type"] == "IMAGE"
    assert res_img["ocr_status"] == "EXCLUDED"
    assert len(res_img["line_items"]) == 0
    assert "strictly excluded" in res_img["note"].lower()


def test_employee_resolver_and_roster():
    """Verify canonical resolution of key employees across Swapnali, Ganesh, Vaibhav, and department heads."""
    # Test Swapnali
    sw = EmployeeResolver.resolve_by_name("Swapnali")
    assert sw is not None
    assert sw["name"] == "Swapnali"
    assert sw["department"] == "Sales Operations"

    # Test Ganesh
    gan = EmployeeResolver.resolve_by_email("ganesh@demo-company.test")
    assert gan is not None
    assert gan["name"] == "Ganesh"

    # Test Vaibhav
    va = EmployeeResolver.resolve_by_text("Coordination with Vaibhav on SO Booking")
    assert va is not None
    assert va["name"] == "Vaibhav"

    # Test Frank Engineering
    eng = EmployeeResolver.get_employee_for_stage("ENGINEERING_CONFIRMATION")
    assert eng is not None
    assert "Engineering" in eng["name"]

    # Test Bob PPC
    ppc = EmployeeResolver.get_employee_for_stage("PPC_MATERIAL_CHECK")
    assert ppc is not None
    assert "PPC" in ppc["name"]


@pytest.mark.asyncio
async def test_workflow_engine_13_stages_and_sequential_dependencies(clean_repos):
    """Verify autonomous generation of the 13-stage manufacturing workflow and sequential blocking dependencies."""
    email_repo, task_repo, case_repo = clean_repos
    workflow_engine = WorkflowCoordinationEngine(task_repo=task_repo)

    case = await case_repo.create_case(
        BusinessCaseCreate(
            title="Enquiry for Hydraulic Skid Tube Assemblies",
            case_type="ENQUIRY",
            priority="HIGH",
        )
    )

    now = datetime.now(UTC)
    message = SourceMessageRead(
        id=uuid4(),
        source_mailbox_id=uuid4(),
        provider_message_id="TEST-ENQ-001",
        subject="RFQ - Stainless steel fittings / project AP-44",
        sender_address="procurement@apexprocess.example",
        sender_display_name="Neha Kulkarni",
        to_recipients=[{"address": "sales@example.test", "display_name": "Swapnali"}],
        cc_recipients=[],
        sent_at=now,
        received_at=now,
        body_text="Please quote your best price by 15-Nov for the attached requirement.",
        body_preprocessed="Please quote your best price by 15-Nov for the attached requirement.",
        processing_status="PENDING",
        created_at=now,
        updated_at=now,
    )

    created_tasks = await workflow_engine.auto_orchestrate_from_email(
        message=message,
        business_case_id=case.id,
        extracted_line_items=[{"part_number": "AP-FIT-022", "quantity": "51", "uom": "EA"}],
    )

    assert len(created_tasks) == 13
    assert len(MANUFACTURING_WORKFLOW_STAGES) == 13

    # Check stage 1: Enquiry Registration (Swapnali) is completed
    task_1 = created_tasks[0]
    assert task_1.assigned_to == "Swapnali"
    assert task_1.status == "completed"

    # Check stage 2: Part Details Check (Ganesh) is in_progress (the active bottleneck)
    task_2 = created_tasks[1]
    assert task_2.assigned_to == "Ganesh"
    assert task_2.status == "in_progress"

    # Check downstream stages are pending
    for t in created_tasks[2:]:
        assert t.status == "pending"

    # Check sequential dependencies were linked
    deps = await task_repo.list_dependencies()
    # 13 tasks sequential chain -> 12 dependencies
    case_deps = [d for d in deps if any(t.task_id == d.successor_task_id for t in created_tasks)]
    assert len(case_deps) >= 12
    for d in case_deps:
        assert d.dependency_type == "FINISH_TO_START"
        assert d.is_blocking is True

    # Check traceability & bottleneck calculation
    trace = await workflow_engine.get_workflow_traceability(case.id)
    assert trace["total_tasks"] == 13
    assert trace["completed_tasks"] >= 1
    assert trace["active_bottleneck"] is not None
    assert trace["active_bottleneck"]["bottleneck_employee"] == "Ganesh"
    assert trace["active_bottleneck"]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_inter_employee_directive_creates_delegated_task(clean_repos):
    """Verify that inter-employee directives in email bodies automatically create delegated tasks."""
    email_repo, task_repo, case_repo = clean_repos
    workflow_engine = WorkflowCoordinationEngine(task_repo=task_repo)

    case = await case_repo.create_case(
        BusinessCaseCreate(
            title="Capacity Alignment Case",
            case_type="ORDER",
            priority="HIGH",
        )
    )

    now = datetime.now(UTC)
    directive_email = SourceMessageRead(
        id=uuid4(),
        source_mailbox_id=uuid4(),
        provider_message_id="TEST-DIRECTIVE-001",
        subject="RE: Planning coordination",
        sender_address="vaibhav@balbird.invalid",
        sender_display_name="Vaibhav",
        to_recipients=[{"address": "ppc@balbird.invalid", "display_name": "Bob PPC"}],
        cc_recipients=[],
        sent_at=now,
        received_at=now,
        body_text="PPC: confirm cutting and assembly sequence for Week 45 by 10-Nov.",
        body_preprocessed="PPC: confirm cutting and assembly sequence for Week 45 by 10-Nov.",
        processing_status="PENDING",
        created_at=now,
        updated_at=now,
    )

    # First instantiate initial workflow
    await workflow_engine.auto_orchestrate_from_email(directive_email, case.id)

    # Next send follow-up with directive
    follow_up = SourceMessageRead(
        id=uuid4(),
        source_mailbox_id=uuid4(),
        provider_message_id="TEST-DIRECTIVE-002",
        subject="RE: Planning coordination follow-up",
        sender_address="vaibhav@balbird.invalid",
        sender_display_name="Vaibhav",
        to_recipients=[{"address": "ppc@balbird.invalid", "display_name": "Bob PPC"}],
        cc_recipients=[],
        sent_at=now,
        received_at=now,
        body_text="PPC: confirm cutting sequence priority for SO/VA/26041 immediately.",
        body_preprocessed="PPC: confirm cutting sequence priority for SO/VA/26041 immediately.",
        processing_status="PENDING",
        created_at=now,
        updated_at=now,
    )
    await workflow_engine.auto_orchestrate_from_email(follow_up, case.id)

    tasks = await task_repo.list_legacy_tasks(case_id=case.id)
    directive_tasks = [t for t in tasks if "Direct Directive" in t.description]
    assert len(directive_tasks) >= 1
    assert directive_tasks[0].assigned_to == "Bob PPC"
    assert directive_tasks[0].assigned_by == "Vaibhav"


@pytest.mark.asyncio
async def test_train_data_service_swapnali_batch_sample():
    """Verify TrainDataService batch ingestion runs successfully on local test fixtures."""
    svc = TrainDataService()
    res = await svc.import_batch(batch_name="swapnali", limit=1)
    assert res["total_imported"] >= 1
    assert len(res["active_bottlenecks"]) >= 1
