"""
Unit & Integration Tests for Employee Management, Department HOD Management,
Handoffs, and Physical Operational Verifications.
"""
import pytest
from uuid import uuid4
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.master_data import (
    DepartmentCreate,
    DepartmentHODCreate,
    EmployeeCreate,
    EmployeeUpdate,
    TaskHandoverCreate,
    TaskHandoverAction,
    PhysicalVerificationCreate,
)


@pytest.mark.asyncio
async def test_employee_crud_and_stats():
    repo = MasterDataRepository()

    # 1. Create Department
    dept = await repo.create_department(DepartmentCreate(code="PRODUCTION", name="Manufacturing & Assembly"))

    # 2. Create Employee
    emp = await repo.create_employee(
        EmployeeCreate(
            name="Carol Production",
            department="PRODUCTION",
            email="carol.prod@balbird.invalid",
            employee_number=1004,
            designation="Production Supervisor",
            role="TEAM_LEADER",
            is_active=True,
        )
    )
    assert emp.id is not None
    assert emp.name == "Carol Production"
    assert emp.department == "PRODUCTION"
    assert emp.designation == "Production Supervisor"
    assert emp.is_active is True

    # 3. List Employees with filters
    all_emps = await repo.list_employees(department="PRODUCTION")
    assert len(all_emps) == 1
    assert all_emps[0].name == "Carol Production"

    search_res = await repo.list_employees(search="supervisor")
    assert len(search_res) == 1

    search_none = await repo.list_employees(search="nonexistent")
    assert len(search_none) == 0

    # 4. Update Employee
    updated = await repo.update_employee(
        emp.id,
        EmployeeUpdate(designation="Senior Production Lead", phone_number="+91-9876543210"),
    )
    assert updated.designation == "Senior Production Lead"
    assert updated.phone_number == "+91-9876543210"

    # 5. Deactivate Employee
    deactivated = await repo.update_employee(emp.id, EmployeeUpdate(is_active=False))
    assert deactivated.is_active is False

    active_only = await repo.list_employees(is_active=True)
    assert len(active_only) == 0


@pytest.mark.asyncio
async def test_hod_assignment_and_history():
    repo = MasterDataRepository()

    # 1. Setup Department & Employees
    dept = await repo.create_department(DepartmentCreate(code="QUALITY", name="Quality Assurance"))
    emp1 = await repo.create_employee(
        EmployeeCreate(
            name="David Quality",
            department="QUALITY",
            email="david.qc@balbird.invalid",
            employee_number=1005,
            designation="QA Engineer",
            is_active=True,
        )
    )
    emp2 = await repo.create_employee(
        EmployeeCreate(
            name="Diana Quality",
            department="QUALITY",
            email="diana.qc@balbird.invalid",
            employee_number=1009,
            designation="Senior QA Lead",
            is_active=True,
        )
    )

    # Initially: HOD NOT ASSIGNED
    initial_hod = await repo.get_department_hod(dept.code)
    assert initial_hod.employee_name == "HOD NOT ASSIGNED"
    assert initial_hod.is_active is False

    # 2. Assign David as HOD
    hod1 = await repo.assign_department_hod(
        dept.code,
        DepartmentHODCreate(employee_id=emp1.id, assigned_by="SYSTEM_ADMIN", notes="Initial assignment"),
    )
    assert hod1.is_active is True
    assert hod1.employee_name == "David Quality"
    assert hod1.employee_id == emp1.id

    # Verify role was upgraded
    david_profile = await repo.get_employee_by_id(emp1.id)
    assert david_profile.role == "DEPT_HEAD"

    # 3. Change HOD to Diana (Audit history must preserve David's previous assignment)
    hod2 = await repo.assign_department_hod(
        dept.code,
        DepartmentHODCreate(employee_id=emp2.id, assigned_by="DIRECTOR", notes="Annual rotation"),
    )
    assert hod2.is_active is True
    assert hod2.employee_name == "Diana Quality"

    # 4. Check Current HOD
    current = await repo.get_department_hod(dept.code)
    assert current.employee_id == emp2.id
    assert current.employee_name == "Diana Quality"

    # 5. Check Audit History
    history = await repo.get_department_hod_history(dept.code)
    assert len(history) == 2
    # One is active, one is revoked with reason
    revoked = [h for h in history if not h.is_active]
    active = [h for h in history if h.is_active]
    assert len(revoked) == 1
    assert len(active) == 1
    assert revoked[0].employee_id == emp1.id
    assert "Replaced by new HOD assignment" in revoked[0].revocation_reason
    assert active[0].employee_id == emp2.id

    # 6. Remove HOD
    removed = await repo.remove_department_hod(dept.code, reason="Temporary restructuring")
    assert removed is True
    post_remove = await repo.get_department_hod(dept.code)
    assert post_remove.employee_name == "HOD NOT ASSIGNED"
    assert post_remove.is_active is False


@pytest.mark.asyncio
async def test_hod_assignment_validations():
    repo = MasterDataRepository()

    dept_sales = await repo.create_department(DepartmentCreate(code="SALES", name="Sales Department"))
    dept_purchase = await repo.create_department(DepartmentCreate(code="PURCHASE", name="Procurement Department"))

    emp_sales = await repo.create_employee(
        EmployeeCreate(name="John Sales", department="SALES", email="john.sales@balbird.invalid", is_active=True)
    )
    emp_inactive = await repo.create_employee(
        EmployeeCreate(name="Inactive Buyer", department="PURCHASE", email="buyer@balbird.invalid", is_active=False)
    )

    # Validation 1: Inactive employee cannot be assigned as HOD
    with pytest.raises(ValueError, match="Cannot assign inactive employee"):
        await repo.assign_department_hod(
            dept_purchase.code,
            DepartmentHODCreate(employee_id=emp_inactive.id),
        )

    # Validation 2: Employee cannot manage a department they do not belong to
    with pytest.raises(ValueError, match="belongs to department"):
        await repo.assign_department_hod(
            dept_purchase.code,
            DepartmentHODCreate(employee_id=emp_sales.id),
        )


@pytest.mark.asyncio
async def test_task_handovers_workflow():
    repo = MasterDataRepository()
    dept_eng = await repo.create_department(DepartmentCreate(code="ENGINEERING", name="Design & Engineering"))
    dept_prod = await repo.create_department(DepartmentCreate(code="PRODUCTION", name="Production"))

    emp_eng = await repo.create_employee(
        EmployeeCreate(name="Frank Engineering", department="ENGINEERING", email="frank@balbird.invalid")
    )
    emp_prod = await repo.create_employee(
        EmployeeCreate(name="Carol Production", department="PRODUCTION", email="carol@balbird.invalid")
    )

    # 1. Initiate Handover
    handover = await repo.create_task_handover(
        TaskHandoverCreate(
            task_id="TASK-00101",
            to_department_code="PRODUCTION",
            to_employee_id=emp_prod.id,
            checklist=[
                {"item": "Drawing approved", "checked": True},
                {"item": "BOM verified", "checked": True},
            ],
            handover_notes="Drawing ECO-109 approved. Ready for machining.",
        ),
        from_employee_id=emp_eng.id,
    )
    assert handover.id is not None
    assert handover.status == "PENDING_ACCEPTANCE"
    assert len(handover.checklist) == 2

    # 2. Reject Handover (with reason)
    rejected = await repo.action_task_handover(
        handover.id,
        TaskHandoverAction(action="REJECT", rejection_reason="Raw material CS-ST52 has not arrived yet"),
    )
    assert rejected.status == "REJECTED"
    assert rejected.rejection_reason == "Raw material CS-ST52 has not arrived yet"

    # 3. Create another handover and Accept
    handover2 = await repo.create_task_handover(
        TaskHandoverCreate(
            task_id="TASK-00101",
            to_department_code="PRODUCTION",
            checklist=[{"item": "Material verified", "checked": True}],
        ),
        from_employee_id=emp_eng.id,
    )
    accepted = await repo.action_task_handover(handover2.id, TaskHandoverAction(action="ACCEPT"))
    assert accepted.status == "ACCEPTED"


@pytest.mark.asyncio
async def test_physical_verification_records():
    repo = MasterDataRepository()

    verification = await repo.create_physical_verification(
        PhysicalVerificationCreate(
            verification_type="DISPATCH_CHALLAN",
            document_reference="DC-9021",
            document_date="2026-11-12",
            related_so_number="SO-1025",
            part_number="HT-2045",
            verified_quantity=100.0,
            unit_of_measure="MTR",
            notes="Physical shipment verified with transporter lorry receipt",
        )
    )
    assert verification.id is not None
    assert verification.is_verified is True
    assert verification.document_reference == "DC-9021"

    records = await repo.list_physical_verifications(so_number="SO-1025")
    assert len(records) >= 1
    assert records[0].part_number == "HT-2045"
