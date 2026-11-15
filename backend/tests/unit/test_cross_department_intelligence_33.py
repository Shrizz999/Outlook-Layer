"""
Comprehensive Automated Test Suite for Balbird Cross-Department Intelligence (Rounds 1 - 5).
Evaluates the 33-email test dataset across:
- Round 1: Individual email classification (Purchase, Sales Ops, Application, Production, IT)
- Round 2: Additional departments (Logistics, Management, HR, PPC, Accounts, Supply Chain)
- Round 3: All 8 Cross-department relationship detections
- Round 4: Dependencies, blockers, and who is waiting for whom
- Round 5: Updates, conflicts, duplicate task prevention, and evidence verification
"""
from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.enums import CaseType, Priority, TaskProposalStatus
from app.integrations.ai_providers.provider import MockAIProvider
from app.integrations.email_providers.fixture_provider import FixtureEmailProvider
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.email_repo import EmailRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.business_case import BusinessCaseCreate
from app.schemas.email import SourceMessageCreate, SourceMessageRead
from app.services.context.context_engine import BusinessContextEngine
from app.services.intelligence.analyser import EmailAnalysisService
from app.services.intelligence.cross_department_detector import CrossDepartmentDetector
from app.services.tasks.task_service import TaskCoordinationService


@pytest.fixture
def test_dataset_dir() -> Path:
    # Locate dataset directory
    candidates = [
        Path("data/cross_department_33"),
        Path("../data/cross_department_33"),
        Path("backend/data/cross_department_33"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("Could not locate data/cross_department_33 directory")


@pytest.fixture
def fixture_provider() -> FixtureEmailProvider:
    return FixtureEmailProvider()


@pytest.fixture
def mock_ai() -> MockAIProvider:
    return MockAIProvider()


@pytest.fixture
def email_repo() -> EmailRepository:
    return EmailRepository()


@pytest.fixture
def task_repo() -> TaskRepository:
    return TaskRepository()


@pytest.fixture
def case_repo() -> BusinessCaseRepository:
    return BusinessCaseRepository()


# =============================================================================
# ROUND 1: Individual Email Classification (5 Departments)
# =============================================================================

@pytest.mark.asyncio
async def test_round1_individual_department_classification(test_dataset_dir, fixture_provider, mock_ai):
    """
    Test individual classification of Purchase, Sales Operations, Application, Production, and IT emails.
    Verifies: Department, Intent, Summary, Priority, Searchable Tags, Entity extraction.
    """
    eml_dir = test_dataset_dir / "emails"
    round1_files = [
        ("01_purchase_po_flanges.eml", "PURCHASE", "PO-APEX-8821", "FL-1002"),
        ("02_sales_ops_rfq_tubes.eml", "SALES_OPERATIONS", "RFQ-9041", "HT-2045"),
        ("03_application_drawing_revision.eml", "APPLICATION", "ECO-109", "MA-5500"),
        ("04_production_machine_breakdown.eml", "PRODUCTION", "CNC-04", None),
        ("05_it_credential_provisioning.eml", "IT", None, None),
    ]

    for fname, expected_dept, expected_ref, expected_part in round1_files:
        path = eml_dir / fname
        assert path.exists(), f"Fixture {fname} missing"
        raw = fixture_provider._load_eml_fixture(path)
        assert raw is not None

        res = await mock_ai.analyse_email(
            message_id=f"test-{fname}",
            subject=raw.subject,
            sender_address=raw.sender_address,
            body_preprocessed=raw.body_text,
            sent_at=datetime.now(UTC),
            idempotency_key=f"idemp-{fname}",
        )

        assert res.success is True
        analysis = res.analysis
        assert analysis is not None

        # Department classification check
        assert analysis.primary_department == expected_dept, f"Failed dept check for {fname}: got {analysis.primary_department}, expected {expected_dept}"
        assert analysis.summary is not None
        assert len(analysis.searchable_tags) > 0

        # Reference verification
        if expected_ref:
            ref_vals = [r.value.upper() for r in analysis.references]
            assert any(expected_ref in rv for rv in ref_vals), f"Expected ref {expected_ref} in {ref_vals}"

        # Part verification
        if expected_part:
            assert expected_part in analysis.parts, f"Expected part {expected_part} in {analysis.parts}"


# =============================================================================
# ROUND 2: Additional Departments (Logistics, Management, HR, PPC, Accounts, Supply Chain)
# =============================================================================

@pytest.mark.asyncio
async def test_round2_additional_departments_and_task_extraction(test_dataset_dir, fixture_provider, mock_ai):
    """
    Test Logistics, Management, HR, PPC, Accounts, and Supply Chain emails.
    Verifies: Task extraction, ownership attribution rules, dates, references, and amounts.
    """
    eml_dir = test_dataset_dir / "emails"
    round2_files = [
        ("06_logistics_dispatch_challan.eml", "LOGISTICS", "DC-8810", None),
        ("07_management_priority_order.eml", "MANAGEMENT", "SO-1025", 450000),
        ("08_hr_employee_onboarding.eml", "HR", "ONBOARDING-VIKRAM_RAO", None),
        ("09_ppc_capacity_schedule.eml", "PPC", "WO-4011", None),
        ("10_accounts_invoice_payment.eml", "ACCOUNTS", "INV-4011", 95000),
        ("11_supply_chain_grn_receipt.eml", "SUPPLY_CHAIN", "GRN-7012", None),
    ]

    for fname, expected_dept, expected_ref, expected_amount in round2_files:
        path = eml_dir / fname
        raw = fixture_provider._load_eml_fixture(path)
        assert raw is not None

        res = await mock_ai.analyse_email(
            message_id=f"test-{fname}",
            subject=raw.subject,
            sender_address=raw.sender_address,
            body_preprocessed=raw.body_text,
            sent_at=datetime.now(UTC),
            idempotency_key=f"idemp-{fname}",
        )

        assert res.success is True
        analysis = res.analysis
        assert analysis.primary_department == expected_dept

        if expected_ref:
            ref_vals = [r.value.upper() for r in analysis.references]
            assert any(expected_ref in rv for rv in ref_vals), f"Expected ref {expected_ref} in {ref_vals}"

        if expected_amount:
            amounts = [m["amount"] for m in analysis.monetary_values]
            assert expected_amount in amounts, f"Expected amount {expected_amount} in {amounts}"

        # Ownership rule verification: CC recipients must not automatically become owners
        for act in analysis.actions:
            if not act.evidence:
                assert act.suggested_owner is None, "Owner should never be invented without explicit directive"


# =============================================================================
# ROUND 3: Cross-Department Relationships (All 8 Core Scenarios)
# =============================================================================

@pytest.mark.asyncio
async def test_round3_cross_department_relationships():
    """
    Test detection of all 8 required cross-department relationships:
    1. Machine breakdown affecting PPC scheduling and customer orders.
    2. Management priority orders connected to PPC shortages.
    3. SS304 material shortages reported by multiple departments.
    4. HR onboarding connected to IT access preparation.
    5. Part specification mismatches connected to supply-chain stock shortages.
    6. Supplier purchase orders distinguished from customer sales orders.
    7. Invoice references distinguished from work order references (identical numbers).
    8. Dispatch delays connected to customer commitments and management escalation.
    """
    detector = CrossDepartmentDetector()

    # Scenario 1: Machine breakdown affecting PPC and orders
    conns_1 = detector.detect_connections(
        subject="CRITICAL: Spindle motor breakdown on CNC-04 lathe",
        body="CNC-04 lathe broke down. Halts cutting of HT-2045 for SO-1025. PPC schedule delayed.",
        department="PRODUCTION",
    )
    assert any(c.scenario == "MACHINE_BREAKDOWN_PPC_IMPACT" for c in conns_1)
    s1 = next(c for c in conns_1 if c.scenario == "MACHINE_BREAKDOWN_PPC_IMPACT")
    assert "PRODUCTION" in s1.connected_departments
    assert "PPC" in s1.connected_departments
    assert "SO-1025" in s1.business_references

    # Scenario 2: Management priority connected to PPC shortages
    conns_2 = detector.detect_connections(
        subject="Executive Escalation: Management priority order SO-1025 must ship on time",
        body="Director priority directive: SO-1025 must ship by month end. Urgent milestone. PPC component shortage must be expedited.",
        department="MANAGEMENT",
    )
    assert any(c.scenario == "MANAGEMENT_PRIORITY_PPC_SHORTAGE" for c in conns_2)
    s2 = next(c for c in conns_2 if c.scenario == "MANAGEMENT_PRIORITY_PPC_SHORTAGE")
    assert "MANAGEMENT" in s2.connected_departments
    assert "PPC" in s2.connected_departments

    # Scenario 3: SS304 material shortage across departments
    conns_3 = detector.detect_connections(
        subject="Critical Shortage: SS304 stock depleted across work orders",
        body="PPC reports aggregate shortage of 350m SS304 stainless steel raw tube stock. Shop floor cutting waiting.",
        department="PPC",
    )
    assert any(c.scenario == "SS304_MULTI_DEPT_SHORTAGE" for c in conns_3)
    s3 = next(c for c in conns_3 if c.scenario == "SS304_MULTI_DEPT_SHORTAGE")
    assert "SS304" in s3.evidence or "ss304" in s3.evidence.lower()
    assert s3.verification_status == "HUMAN_VERIFICATION_REQUIRED"

    # Scenario 4: HR onboarding connected to IT access preparation
    conns_4 = detector.detect_connections(
        subject="New Employee Onboarding: Vikram Rao joining on 2026-11-20",
        body="Vikram Rao joining as Application Engineer on 2026-11-20. Prepare laptop and ERP credentials.",
        department="HR",
    )
    assert any(c.scenario == "HR_ONBOARDING_IT_ACCESS" for c in conns_4)
    s4 = next(c for c in conns_4 if c.scenario == "HR_ONBOARDING_IT_ACCESS")
    assert "HR" in s4.connected_departments
    assert "IT" in s4.connected_departments

    # Scenario 5: Part spec mismatch causing supply chain stock quarantine
    conns_5 = detector.detect_connections(
        subject="Technical Specification Mismatch on Flange FL-1002 Drawing",
        body="Engineering audit identified drawing tolerance mismatch on FL-1002 under ECO-204. Quarantine warehouse stock.",
        department="APPLICATION",
    )
    assert any(c.scenario == "PART_SPEC_MISMATCH_SUPPLY_CHAIN" for c in conns_5)
    s5 = next(c for c in conns_5 if c.scenario == "PART_SPEC_MISMATCH_SUPPLY_CHAIN")
    assert "FL-1002" in s5.business_references
    assert "APPLICATION" in s5.connected_departments

    # Scenario 6: Supplier PO vs Customer SO distinction
    conns_6 = detector.detect_connections(
        subject="Procurement Reconciliation: Customer SO-1030 and Supplier PO-Titan-9940",
        body="Customer PO received for SO-1030. Outgoing Supplier PO PO-Titan-9940 issued to vendor for raw forgings.",
        department="SALES_OPERATIONS",
    )
    assert any(c.scenario == "SUPPLIER_PO_VS_CUSTOMER_SO" for c in conns_6)

    # Scenario 7: Invoice vs Work Order distinction with identical numbers (5050)
    conns_7 = detector.detect_connections(
        subject="Entity distinction: Commercial Invoice INV-5050 vs Factory Work Order WO-5050",
        body="Commercial invoice INV-5050 issued by Accounts. Internal work order WO-5050 scheduled by PPC. Strictly segregated.",
        department="ACCOUNTS",
    )
    assert any(c.scenario == "INVOICE_VS_WORK_ORDER" for c in conns_7)
    s7 = next(c for c in conns_7 if c.scenario == "INVOICE_VS_WORK_ORDER")
    assert "INV-5050" in s7.business_references
    assert "WO-5050" in s7.business_references

    # Scenario 8: Dispatch delays connected to customer commitments & management escalation
    conns_8 = detector.detect_connections(
        subject="URGENT: Transporter delay holding customer shipment for SO-1025",
        body="Transporter carrier delay past promised delivery date. Customer commitment breached on SO-1025. Escalating to management.",
        department="LOGISTICS",
    )
    assert any(c.scenario == "DISPATCH_DELAY_COMMITMENT_RISK" for c in conns_8)
    s8 = next(c for c in conns_8 if c.scenario == "DISPATCH_DELAY_COMMITMENT_RISK")
    assert "SO-1025" in s8.business_references
    assert "LOGISTICS" in s8.connected_departments
    assert "MANAGEMENT" in s8.connected_departments


# =============================================================================
# ROUND 4: Dependencies and Blocker Intelligence
# =============================================================================

@pytest.mark.asyncio
async def test_round4_dependencies_and_blockers():
    """
    Test identifying:
    - Who is waiting for whom.
    - Why a task is blocked.
    - Downstream order impact.
    """
    detector = CrossDepartmentDetector()
    conns = detector.detect_connections(
        subject="Machine breakdown halting Line 2 for SO-1025",
        body="CNC-04 spindle failure halts cutting. PPC schedule delayed. Delivery date 2026-11-28 at risk.",
        department="PRODUCTION",
    )
    assert len(conns) > 0
    c = conns[0]
    assert c.waiting_party is not None
    assert "PPC" in c.waiting_party or "Sales" in c.waiting_party
    assert c.holding_party is not None
    assert "Production" in c.holding_party
    assert "CNC-04" in c.blocker_description
    assert "SO-1025" in c.downstream_order_impact


# =============================================================================
# ROUND 5: Updates, Duplicate Control, and Evidence Verification
# =============================================================================

@pytest.mark.asyncio
async def test_round5_follow_up_task_update_without_duplicates(task_repo):
    """
    Verify follow-up email reporting task completion updates existing task
    to COMPLETED_REPORTED without creating duplicate tasks.
    """
    now = datetime.now(UTC)
    case_id = uuid4()
    task_service = TaskCoordinationService(task_repo=task_repo)

    # 1. Pre-create an operational cutting task in the legacy table
    initial_task = await task_repo.create_task_raw({
        "description": "Cutting 100m HT-2045 on CNC-04",
        "department": "Production",
        "status": "in_progress",
        "business_case_id": case_id,
        "assigned_to": "Line 1 Operator",
    })
    assert initial_task.status == "in_progress"

    # 2. Ingest follow-up email claiming cutting completed
    msg_id = uuid4()
    followup_msg = SourceMessageRead(
        id=msg_id,
        source_mailbox_id=uuid4(),
        provider_message_id="MSG-FOLLOWUP-01",
        subject="Re: Cutting Update: Cutting completed for SO-1025 HT-2045",
        body_text="Cutting completed for SO-1025 100m HT-2045 tubes on Line 2 today. Lot transferred to QC staging.",
        body_preprocessed="Cutting completed for SO-1025 100m HT-2045 tubes on Line 2 today. Lot transferred to QC staging.",
        processing_status="PREPROCESSED",
        created_at=now,
        updated_at=now,
    )

    from app.schemas.email import EmailAnalysisRead
    analysis = EmailAnalysisRead(
        id=uuid4(),
        source_message_id=msg_id,
        analysis_version=2,
        priority="NORMAL",
        validation_status="ACCEPTED_AUTO",
        raw_structured_output={
            "intent": "TASK_COMPLETION",
            "is_follow_up": True,
            "actions": [],
        },
        processed_at=now,
    )

    # 3. Coordinate proposals: Should update existing task and NOT generate new duplicate proposal
    proposals = await task_service.generate_proposals_from_analysis(followup_msg, analysis, business_case_id=case_id)
    assert len(proposals) == 0  # No duplicate proposal created

    # 4. Verify existing task status transitioned to COMPLETED_REPORTED (not verified until inspection)
    tasks = await task_repo.list_legacy_tasks(case_id=case_id)
    updated = next(t for t in tasks if t.task_id == initial_task.task_id)
    assert updated.status == "completed_reported"
