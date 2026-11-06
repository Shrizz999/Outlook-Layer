"""
Repeatable Synthetic Demo Data Seeder for Balbird Intelligence.
Generates deterministic synthetic master data, sales orders, MRP snapshots,
emails, business cases, tasks, dependencies, and risk alerts.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.enums import BIRole, CaseType, Priority, TaskProposalStatus, TaskStatus
from app.integrations.email_providers.fixture_provider import RawMessage
from app.repositories.alert_repo import AlertRepository
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.email_repo import EmailRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.alert import MonitoringAlertCreate
from app.schemas.business_case import BusinessCaseCreate, CaseLinkCreate
from app.schemas.master_data import CustomerCreate, DepartmentCreate, PartCreate, SupplierCreate
from app.schemas.order import MRPRecordBase, SalesOrderCreate, SalesOrderLineBase
from app.schemas.task import TaskDependencyCreate, TaskProposalCreate
from app.services.email.ingestion import EmailIngestionService
from app.services.intelligence.analyser import EmailAnalysisService
from app.services.monitoring.risk_engine import MonitoringRiskEngine


async def seed_all() -> None:
    print("--- Seeding Balbird Intelligence Synthetic Demo Dataset ---")

    master_repo = MasterDataRepository()
    case_repo = BusinessCaseRepository()
    email_repo = EmailRepository()
    order_repo = OrderRepository()
    task_repo = TaskRepository()
    alert_repo = AlertRepository()

    ingestion_service = EmailIngestionService(email_repo)
    analysis_service = EmailAnalysisService(email_repo=email_repo)
    risk_engine = MonitoringRiskEngine(alert_repo=alert_repo, task_repo=task_repo, order_repo=order_repo)

    # 1. Departments
    print("1. Seeding Departments...")
    dept_codes = [
        ("SALES", "Sales & Commercial"),
        ("PURCHASE", "Procurement & Sourcing"),
        ("PPC", "Production Planning & Control"),
        ("PRODUCTION", "Manufacturing & Assembly"),
        ("QUALITY", "Quality Assurance & QC"),
        ("DISPATCH", "Warehouse & Logistics"),
    ]
    created_depts: dict[str, UUID] = {}
    for code, name in dept_codes:
        dept = await master_repo.create_department(DepartmentCreate(code=code, name=name))
        created_depts[code] = dept.id

    # 2. Employees (Legacy table employees)
    print("2. Seeding Employees...")
    employees_data = [
        {"name": "John Sales", "department": "SALES", "email": "john.sales@balbird.invalid", "employee_number": 1001},
        {"name": "Alice Purchase", "department": "PURCHASE", "email": "alice.purchase@balbird.invalid", "employee_number": 1002},
        {"name": "Bob PPC", "department": "PPC", "email": "bob.ppc@balbird.invalid", "employee_number": 1003},
        {"name": "Carol Production", "department": "PRODUCTION", "email": "carol.prod@balbird.invalid", "employee_number": 1004},
        {"name": "David Quality", "department": "QUALITY", "email": "david.qc@balbird.invalid", "employee_number": 1005},
        {"name": "Emma Dispatch", "department": "DISPATCH", "email": "emma.dispatch@balbird.invalid", "employee_number": 1006},
        {"name": "Frank Engineering", "department": "ENGINEERING", "email": "frank.eng@balbird.invalid", "employee_number": 1007},
        {"name": "Grace Operations Head", "department": "MANAGEMENT", "email": "grace.mgmt@balbird.invalid", "employee_number": 1008},
    ]
    created_emps: dict[str, UUID] = {}
    for emp_raw in employees_data:
        emp = await master_repo.create_employee_raw(emp_raw)
        created_emps[emp.name] = emp.id

    # 3. Customers
    print("3. Seeding Customers...")
    customers_data = [
        ("CUST-101", "Acme Engineering Ltd", ["Acme", "Acme Eng"]),
        ("CUST-102", "Global Fluid Systems", ["GFS", "Global Fluid"]),
        ("CUST-103", "Pacific Hydro Tech", ["Pacific Hydro", "PHT"]),
    ]
    created_customers: dict[str, UUID] = {}
    for code, name, aliases in customers_data:
        c = await master_repo.create_customer(CustomerCreate(customer_code=code, name=name, aliases=aliases))
        created_customers[name] = c.id

    # 4. Suppliers
    print("4. Seeding Suppliers...")
    suppliers_data = [
        ("SUP-201", "Apex Tube Mills", ["Apex", "Apex Tubes"]),
        ("SUP-202", "Pioneer Sealing Solutions", ["Pioneer Seals", "PSS"]),
        ("SUP-203", "Titan Forgings Corp", ["Titan", "Titan Forgings"]),
    ]
    created_suppliers: dict[str, UUID] = {}
    for code, name, aliases in suppliers_data:
        s = await master_repo.create_supplier(SupplierCreate(supplier_code=code, name=name, aliases=aliases))
        created_suppliers[name] = s.id

    # 5. Parts
    print("5. Seeding Parts...")
    parts_data = [
        ("HT-2045", "Hydraulic Tube 20x4.5mm Seamless", "CS-ST52", "MTR"),
        ("FL-1002", "SAE Flange 3000 PSI 1/2 Inch", "AISI-316", "EA"),
        ("SE-5011", "NBR O-Ring Seal 50mm ID", "NBR-70", "EA"),
        ("CL-0042", "Standard Series Tube Clamp DIN 3015", "PP", "EA"),
        ("VA-9001", "High Pressure Ball Valve DN20", "CS-A105", "EA"),
        ("CO-3021", "Quick Release Coupling 1/4 Inch", "BRASS", "EA"),
        ("EL-1100", "90 Deg Forged Elbow 1 Inch NPT", "CS-A105", "EA"),
        ("TE-2200", "Equal Tee Coupling 25mm", "CS-ST52", "EA"),
        ("RE-3300", "Swaged Reducer 1 Inch to 1/2 Inch", "CS-A105", "EA"),
        ("HO-4400", "Hydraulic 2-Wire Braided Hose 10m", "RUBBER", "MTR"),
        ("MA-5500", "Custom 4-Port Manifold Block", "AL-6061", "EA"),
        ("GA-6600", "Glycerin Filled Pressure Gauge 0-400 bar", "SS-304", "EA"),
    ]
    created_parts: dict[str, UUID] = {}
    for p_num, desc, mat, uom in parts_data:
        p = await master_repo.create_part(PartCreate(part_number=p_num, description=desc, material_code=mat, unit_of_measure=uom))
        created_parts[p_num] = p.id

    # 6. Sales Orders
    print("6. Seeding Sales Orders...")
    so_1025 = await order_repo.create_sales_order(
        SalesOrderCreate(
            so_number="SO-1025",
            customer_id=created_customers["Acme Engineering Ltd"],
            source_customer_name="Acme Engineering Ltd",
            order_date=date(2026, 11, 1),
            requested_delivery_date=date(2026, 11, 28),
            status="OPEN",
            lines=[
                SalesOrderLineBase(
                    line_number=1,
                    part_id=created_parts["HT-2045"],
                    source_part_number="HT-2045",
                    description="Hydraulic Tube 20x4.5mm Seamless",
                    ordered_quantity=Decimal("100"),
                    unit_of_measure="MTR",
                    delivery_date=date(2026, 11, 28),
                ),
                SalesOrderLineBase(
                    line_number=2,
                    part_id=created_parts["FL-1002"],
                    source_part_number="FL-1002",
                    description="SAE Flange 3000 PSI 1/2 Inch",
                    ordered_quantity=Decimal("50"),
                    unit_of_measure="EA",
                    delivery_date=date(2026, 11, 28),
                ),
            ],
        )
    )

    so_1026 = await order_repo.create_sales_order(
        SalesOrderCreate(
            so_number="SO-1026",
            customer_id=created_customers["Global Fluid Systems"],
            source_customer_name="Global Fluid Systems",
            order_date=date(2026, 11, 3),
            requested_delivery_date=date(2026, 12, 5),
            status="OPEN",
            lines=[
                SalesOrderLineBase(
                    line_number=1,
                    part_id=created_parts["VA-9001"],
                    source_part_number="VA-9001",
                    description="High Pressure Ball Valve DN20",
                    ordered_quantity=Decimal("20"),
                    unit_of_measure="EA",
                    delivery_date=date(2026, 12, 5),
                )
            ],
        )
    )

    # 7. MRP Snapshot & Shortage Detection
    print("7. Seeding MRP Snapshot...")
    mrp_records = [
        MRPRecordBase(
            source_part_number="HT-2045",
            part_id=created_parts["HT-2045"],
            available_stock=Decimal("60"),
            reserved_stock=Decimal("10"),
            required_quantity=Decimal("100"),
            pending_purchase_quantity=Decimal("0"),
            shortage_quantity_computed=Decimal("40"),
            shortage_method="COMPUTED",
            unit_of_measure="MTR",
            planning_date=date(2026, 11, 6),
        ),
        MRPRecordBase(
            source_part_number="FL-1002",
            part_id=created_parts["FL-1002"],
            available_stock=Decimal("150"),
            reserved_stock=Decimal("20"),
            required_quantity=Decimal("50"),
            shortage_quantity_computed=Decimal("0"),
            shortage_method="COMPUTED",
            unit_of_measure="EA",
            planning_date=date(2026, 11, 6),
        ),
    ]
    await order_repo.create_mrp_snapshot("MRP_Snapshot_2026-11-06.xlsx", mrp_records)

    # 8. Mailbox and Synthetic Emails
    print("8. Ingesting Synthetic Emails...")
    mailbox_id = await email_repo.get_or_create_default_mailbox("FIXTURE", "Central Pilot Mailbox")

    synthetic_emails = [
        RawMessage(
            provider_message_id="MSG-001",
            internet_message_id="<msg001@acme.invalid>",
            provider_conversation_id="CONV-1025",
            subject="Enquiry: Requirement for 100m HT-2045 Tubes (Ref: SO-1025)",
            sender_address="procurement@acme.invalid",
            sender_display_name="Robert Acme",
            to_recipients=[{"address": "sales@balbird.invalid", "display_name": "Balbird Sales"}],
            cc_recipients=[],
            sent_at=datetime(2026, 11, 1, 9, 30, tzinfo=UTC),
            received_at=datetime(2026, 11, 1, 9, 31, tzinfo=UTC),
            body_text=(
                "Hello Sales Team,\n\n"
                "Please confirm if you can supply 100 meters of HT-2045 hydraulic tubing by 28 November.\n"
                "This is for our priority project. Reference: SO-1025.\n\n"
                "Kind regards,\nRobert Acme"
            ),
            has_attachments=False,
        ),
        RawMessage(
            provider_message_id="MSG-002",
            internet_message_id="<msg002@apextubes.invalid>",
            provider_conversation_id="CONV-1025",
            subject="Re: Material Order for HT-2045 Tubes - Delivery Confirmation",
            sender_address="sales@apextubes.invalid",
            sender_display_name="Apex Sales Team",
            to_recipients=[{"address": "purchase@balbird.invalid", "display_name": "Balbird Purchase"}],
            cc_recipients=[],
            sent_at=datetime(2026, 11, 4, 14, 15, tzinfo=UTC),
            received_at=datetime(2026, 11, 4, 14, 16, tzinfo=UTC),
            body_text=(
                "Dear Purchase,\n\n"
                "We acknowledge receipt of your order for 40 meters of HT-2045 tubing.\n"
                "We are pleased to confirm that material will be dispatched by 20 November.\n\n"
                "Best regards,\nApex Tube Mills"
            ),
            has_attachments=False,
        ),
        RawMessage(
            provider_message_id="MSG-003",
            internet_message_id="<msg003@gfs.invalid>",
            provider_conversation_id="CONV-1026",
            subject="Urgent: Revised required date for SO-1026",
            sender_address="orders@gfs.invalid",
            sender_display_name="Karen Global Fluid",
            to_recipients=[{"address": "sales@balbird.invalid", "display_name": "Balbird Sales"}],
            cc_recipients=[],
            sent_at=datetime(2026, 11, 5, 11, 0, tzinfo=UTC),
            received_at=datetime(2026, 11, 5, 11, 1, tzinfo=UTC),
            body_text=(
                "Hi Team,\n\n"
                "We need the 20 units of VA-9001 on SO-1026 expedited to 25 November instead of 5 December.\n"
                "Please confirm feasibility ASAP.\n\n"
                "Regards,\nKaren"
            ),
            has_attachments=False,
        ),
    ]

    ingested_res = await ingestion_service.ingest_batch(mailbox_id, synthetic_emails)
    print(f"   Ingested {ingested_res.imported_count} emails ({ingested_res.duplicate_count} duplicates).")

    # 9. AI Analysis on Messages
    print("9. Running AI Intelligence Analysis...")
    for msg in ingested_res.imported_messages:
        analysis = await analysis_service.analyse_message(msg)

    # 10. Business Case & Linking
    print("10. Creating Business Case & Linking...")
    bc_1025 = await case_repo.create_case(
        BusinessCaseCreate(
            title="Acme Hydraulic Tube Order (SO-1025)",
            case_type=CaseType.ORDER.value,
            priority=Priority.HIGH.value,
            primary_customer_id=created_customers["Acme Engineering Ltd"],
            primary_owner_employee_id=created_emps["John Sales"],
            summary="100m HT-2045 tubing order with potential raw material shortage of 40m.",
        )
    )

    await case_repo.add_case_link(
        bc_1025.id,
        CaseLinkCreate(
            linked_object_type="SO",
            linked_object_id=str(so_1025.id),
            relationship_type="PRIMARY",
            match_method="EXACT_SO",
            match_confidence=1.0,
        ),
    )

    # 11. Tasks & Operational Task Orch Bridge
    print("11. Generating Task Proposals & Approving Operational Tasks...")
    prop_1 = await task_repo.create_proposal(
        TaskProposalCreate(
            title="Clarify technical pressure rating for HT-2045 with customer",
            task_type="TECHNICAL_CLARIFICATION",
            suggested_department="SALES",
            priority=Priority.NORMAL.value,
            due_date=date(2026, 11, 10),
            business_case_id=bc_1025.id,
        )
    )
    t_clarify = await task_repo.approve_proposal(
        prop_1.id,
        reviewer_id=created_emps["Grace Operations Head"],
        assigned_to_name="John Sales",
        deadline="2026-11-10",
    )

    prop_2 = await task_repo.create_proposal(
        TaskProposalCreate(
            title="Track supplier Apex delivery of 40m HT-2045 tubes",
            task_type="PURCHASE",
            suggested_department="PURCHASE",
            priority=Priority.HIGH.value,
            due_date=date(2026, 11, 20),
            business_case_id=bc_1025.id,
        )
    )
    t_supplier = await task_repo.approve_proposal(
        prop_2.id,
        reviewer_id=created_emps["Grace Operations Head"],
        assigned_to_name="Alice Purchase",
        deadline="2026-11-20",
    )

    prop_3 = await task_repo.create_proposal(
        TaskProposalCreate(
            title="Schedule tube cutting and assembly in PPC",
            task_type="PPC",
            suggested_department="PPC",
            priority=Priority.HIGH.value,
            due_date=date(2026, 11, 24),
            business_case_id=bc_1025.id,
        )
    )
    t_ppc = await task_repo.approve_proposal(
        prop_3.id,
        reviewer_id=created_emps["Grace Operations Head"],
        assigned_to_name="Bob PPC",
        deadline="2026-11-24",
    )

    # 12. Dependencies & Cycles
    print("12. Creating Task Dependencies...")
    # Production schedule depends on material delivery (t_supplier -> t_ppc)
    await task_repo.create_dependency(
        TaskDependencyCreate(
            predecessor_type="TASK",
            predecessor_task_id=t_supplier.task_id,
            successor_type="TASK",
            successor_task_id=t_ppc.task_id,
            dependency_type="BLOCKS",
            is_blocking=True,
            reason="PPC cutting and manufacturing cannot begin until supplier material arrives",
        ),
        employee_id=created_emps["Grace Operations Head"],
    )

    # 13. Risk & Shortage Alerts
    print("13. Evaluating Risks and Alerts...")
    shortage_alert = await risk_engine.evaluate_material_shortage("SO-1025", "HT-2045", business_case_id=bc_1025.id)
    if shortage_alert:
        print(f"   [ALERT DETECTED]: {shortage_alert.description}")

    print("--- Synthetic Demo Dataset Seeding Completed Successfully! ---")


if __name__ == "__main__":
    asyncio.run(seed_all())
