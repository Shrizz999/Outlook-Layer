"""
Unit Tests: Server-Side RBAC, Data Isolation, and Direct API Tampering Protection.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.main import app
from app.repositories.auth_repo import AuthRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.store import get_store
from app.repositories.task_repo import TaskRepository
from app.schemas.master_data import DepartmentCreate, DepartmentHODCreate, EmployeeCreate
from app.schemas.task import TaskProposalCreate


@pytest.fixture(autouse=True)
def setup_store():
    store = get_store()
    store.clear()
    now = datetime.now(UTC)

    # Pre-seed departments
    sales_id = "701ee07e-aa7d-4253-9c28-73b1769717db"
    store.bi_departments[sales_id] = {
        "id": sales_id,
        "code": "SALES",
        "name": "Sales & Commercial",
        "parent_id": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    purch_id = "c3502e74-5e36-460c-b504-a1913aa44567"
    store.bi_departments[purch_id] = {
        "id": purch_id,
        "code": "PURCHASE",
        "name": "Procurement & Sourcing",
        "parent_id": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    mgmt_id = "f108885a-5475-46e6-aa38-82926d8a026d"
    store.bi_departments[mgmt_id] = {
        "id": mgmt_id,
        "code": "MANAGEMENT",
        "name": "Executive Management",
        "parent_id": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    yield


@pytest.mark.asyncio
async def test_employee_sees_only_own_tasks_and_workflow_tasks():
    auth_repo = AuthRepository()
    task_repo = TaskRepository()
    master_repo = MasterDataRepository()

    # Create Employee Alice (Sales)
    emp_alice = await master_repo.create_employee(
        EmployeeCreate(name="Alice Walker", department="SALES", email="alice.w@balbird.com", employee_number=101)
    )
    user_alice = await auth_repo.create_account({
        "employee_id": emp_alice.id,
        "email": "alice.w@balbird.com",
        "password_hash": hash_password("Password123!"),
        "full_name": "Alice Walker",
        "department": "SALES",
        "approved_position": "EMPLOYEE",
        "account_status": "active",
    })

    wf_id = uuid4()
    wf_other = uuid4()

    # Task 1: Alice's standalone task
    await task_repo.create_task_raw({
        "task_id": "TASK-ALICE-1",
        "description": "Alice Standalone Task",
        "assigned_to": "Alice Walker",
        "department": "SALES",
        "status": "in_progress",
    })

    # Task 2: Bob's unrelated private task
    await task_repo.create_task_raw({
        "task_id": "TASK-BOB-PRIVATE",
        "description": "Bob Private Task",
        "assigned_to": "Bob PPC",
        "department": "PPC",
        "status": "pending",
    })

    # Task 3: Alice's workflow task
    t3 = await task_repo.create_task_raw({
        "task_id": "TASK-ALICE-WF",
        "description": "Alice Step in Shared Workflow",
        "assigned_to": "Alice Walker",
        "department": "SALES",
        "status": "completed",
    })
    # Attach workflow
    store = get_store()
    store.tasks[t3.task_id]["workflow_id"] = wf_id

    # Task 4: Carol's step in the SAME workflow as Alice
    t4 = await task_repo.create_task_raw({
        "task_id": "TASK-CAROL-WF",
        "description": "Carol Step in Shared Workflow",
        "assigned_to": "Carol Production",
        "department": "PRODUCTION",
        "status": "in_progress",
    })
    store.tasks[t4.task_id]["workflow_id"] = wf_id

    # Task 5: Dave's task in a completely different workflow
    t5 = await task_repo.create_task_raw({
        "task_id": "TASK-DAVE-OTHER-WF",
        "description": "Dave in Other Workflow",
        "assigned_to": "Dave Quality",
        "department": "QUALITY",
        "status": "in_progress",
    })
    store.tasks[t5.task_id]["workflow_id"] = wf_other

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Alice logs in
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice.w@balbird.com", "password": "Password123!"},
        )
        token = login_res.json()["session_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Fetch tasks as Alice
        resp = await client.get("/api/v1/tasks", headers=headers)
        assert resp.status_code == 200
        visible_task_ids = [t["task_id"] for t in resp.json()]

        # Alice should see:
        assert "TASK-ALICE-1" in visible_task_ids
        assert "TASK-ALICE-WF" in visible_task_ids
        assert "TASK-CAROL-WF" in visible_task_ids  # Shared workflow subtask

        # Alice should NOT see:
        assert "TASK-BOB-PRIVATE" not in visible_task_ids
        assert "TASK-DAVE-OTHER-WF" not in visible_task_ids

        # 2. Direct access test: Alice tries to fetch Bob's private task by ID
        direct_bob = await client.get("/api/v1/tasks/TASK-BOB-PRIVATE", headers=headers)
        assert direct_bob.status_code == 403
        assert "Access denied" in direct_bob.json()["detail"]

        # Direct access to Dave's other workflow task
        direct_dave = await client.get("/api/v1/tasks/TASK-DAVE-OTHER-WF", headers=headers)
        assert direct_dave.status_code == 403

        # Direct access to her own task
        direct_mine = await client.get("/api/v1/tasks/TASK-ALICE-1", headers=headers)
        assert direct_mine.status_code == 200

        # Direct access to shared workflow task
        direct_shared = await client.get("/api/v1/tasks/TASK-CAROL-WF", headers=headers)
        assert direct_shared.status_code == 200


@pytest.mark.asyncio
async def test_employee_cannot_bypass_isolation_via_query_params():
    auth_repo = AuthRepository()
    task_repo = TaskRepository()
    master_repo = MasterDataRepository()

    emp = await master_repo.create_employee(
        EmployeeCreate(name="Tamper Tester", department="SALES", email="tamper@balbird.com", employee_number=102)
    )
    await auth_repo.create_account({
        "employee_id": emp.id,
        "email": "tamper@balbird.com",
        "password_hash": hash_password("Password123!"),
        "full_name": "Tamper Tester",
        "department": "SALES",
        "approved_position": "EMPLOYEE",
        "account_status": "active",
    })

    # Task for Someone Else
    await task_repo.create_task_raw({
        "task_id": "TASK-SECRET-PURCHASE",
        "description": "Secret Purchase Task",
        "assigned_to": "Secret Buyer",
        "department": "PURCHASE",
        "status": "pending",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "tamper@balbird.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['session_token']}"}

        # Attempt 1: Tamper by passing assigned_to="Secret Buyer"
        r1 = await client.get("/api/v1/tasks?assigned_to=Secret Buyer", headers=headers)
        assert r1.status_code == 200
        ids1 = [t["task_id"] for t in r1.json()]
        assert "TASK-SECRET-PURCHASE" not in ids1

        # Attempt 2: Tamper by passing department="PURCHASE"
        r2 = await client.get("/api/v1/tasks?department=PURCHASE", headers=headers)
        assert r2.status_code == 200
        ids2 = [t["task_id"] for t in r2.json()]
        assert "TASK-SECRET-PURCHASE" not in ids2


@pytest.mark.asyncio
async def test_employee_cannot_access_executive_dashboard_or_directory():
    auth_repo = AuthRepository()
    master_repo = MasterDataRepository()

    emp = await master_repo.create_employee(
        EmployeeCreate(name="Dan Restricted", department="SALES", email="dan@balbird.com", employee_number=103)
    )
    await auth_repo.create_account({
        "employee_id": emp.id,
        "email": "dan@balbird.com",
        "password_hash": hash_password("Password123!"),
        "full_name": "Dan Restricted",
        "department": "SALES",
        "approved_position": "EMPLOYEE",
        "account_status": "active",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "dan@balbird.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['session_token']}"}

        # Cannot view executive dashboard
        dash_res = await client.get("/api/v1/admin/dashboard-summary", headers=headers)
        assert dash_res.status_code == 403
        assert "cannot view executive management dashboards" in dash_res.json()["detail"]

        # Cannot view employee directory
        emp_res = await client.get("/api/v1/employees", headers=headers)
        assert emp_res.status_code == 403
        assert "not authorized to view the employee directory" in emp_res.json()["detail"]

        # Cannot approve task proposals
        prop_res = await client.post(f"/api/v1/tasks/proposals/{uuid4()}/approve", json={}, headers=headers)
        assert prop_res.status_code == 403


@pytest.mark.asyncio
async def test_hod_permissions_and_department_scoping():
    auth_repo = AuthRepository()
    master_repo = MasterDataRepository()
    task_repo = TaskRepository()

    # Create HOD of Purchase
    emp_hod = await master_repo.create_employee(
        EmployeeCreate(name="Paula Purchase HOD", department="PURCHASE", email="paula.hod@balbird.com", employee_number=104)
    )
    await master_repo.assign_department_hod(
        "PURCHASE",
        DepartmentHODCreate(employee_id=emp_hod.id, assigned_by="SYSADMIN"),
    )
    await auth_repo.create_account({
        "employee_id": emp_hod.id,
        "email": "paula.hod@balbird.com",
        "password_hash": hash_password("Password123!"),
        "full_name": "Paula Purchase HOD",
        "department": "PURCHASE",
        "approved_position": "DEPT_HEAD",
        "account_status": "active",
    })

    # Task in Purchase
    await task_repo.create_task_raw({
        "task_id": "TASK-PURCHASE-WORK",
        "description": "Procure Raw Aluminum Pipes",
        "assigned_to": "Buyer Pete",
        "department": "PURCHASE",
        "status": "pending",
    })

    # Task in Sales
    await task_repo.create_task_raw({
        "task_id": "TASK-SALES-WORK",
        "description": "Send Quotation to Client",
        "assigned_to": "Sales Steve",
        "department": "SALES",
        "status": "pending",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "paula.hod@balbird.com", "password": "Password123!"},
        )
        headers = {"Authorization": f"Bearer {login_res.json()['session_token']}"}

        # 1. HOD list tasks -> scoped to PURCHASE
        r = await client.get("/api/v1/tasks", headers=headers)
        assert r.status_code == 200
        ids = [t["task_id"] for t in r.json()]
        assert "TASK-PURCHASE-WORK" in ids
        assert "TASK-SALES-WORK" not in ids

        # 2. HOD direct fetch of other department's task fails
        direct_sales = await client.get("/api/v1/tasks/TASK-SALES-WORK", headers=headers)
        assert direct_sales.status_code == 403
        assert "Task belongs to another department" in direct_sales.json()["detail"]

        # 3. HOD cannot view other department dashboard
        dash_sales = await client.get("/api/v1/departments/SALES/dashboard", headers=headers)
        assert dash_sales.status_code == 403

        # 4. HOD can view own department dashboard
        dash_purch = await client.get("/api/v1/departments/PURCHASE/dashboard", headers=headers)
        assert dash_purch.status_code == 200

        # 5. HOD cannot reassign or remove HODs
        assign_attempt = await client.post("/api/v1/departments/PURCHASE/hod", json={"employee_id": str(emp_hod.id)}, headers=headers)
        assert assign_attempt.status_code == 403


@pytest.mark.asyncio
async def test_admin_user_management_and_role_approval():
    auth_repo = AuthRepository()
    master_repo = MasterDataRepository()

    # 1. Create Admin Account
    admin_emp = await master_repo.create_employee(
        EmployeeCreate(name="Admin Boss", department="MANAGEMENT", email="boss.admin@balbird.com", employee_number=999)
    )
    await auth_repo.create_account({
        "employee_id": admin_emp.id,
        "email": "boss.admin@balbird.com",
        "password_hash": hash_password("Password123!"),
        "full_name": "Admin Boss",
        "department": "MANAGEMENT",
        "approved_position": "SYSADMIN",
        "account_status": "active",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "boss.admin@balbird.com", "password": "Password123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['session_token']}"}

        # 2. A user registers requesting HOD
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Applicant HOD",
                "email": "applicant.hod@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "PURCHASE",
                "position": "HOD",
            },
        )
        assert reg_res.status_code == 201
        user_data = reg_res.json()
        assert user_data["approved_position"] == "EMPLOYEE"
        assert user_data["account_status"] == "pending_approval"

        # 3. Admin lists role requests
        reqs_res = await client.get("/api/v1/auth/admin/role-requests?approval_status=PENDING", headers=admin_headers)
        assert reqs_res.status_code == 200
        reqs = reqs_res.json()
        target_req = next(r for r in reqs if r["user_email"] == "applicant.hod@balbird.com")

        # 4. Admin approves the HOD request
        review_res = await client.post(
            f"/api/v1/auth/admin/role-requests/{target_req['id']}/review",
            json={"approval_status": "APPROVED", "reason": "Qualified for Purchase HOD"},
            headers=admin_headers,
        )
        assert review_res.status_code == 200
        assert review_res.json()["approval_status"] == "APPROVED"

        # 5. Check user account is now DEPT_HEAD and active
        user_check = await client.get("/api/v1/auth/admin/users?search=applicant.hod", headers=admin_headers)
        assert user_check.status_code == 200
        updated_user = user_check.json()[0]
        assert updated_user["approved_position"] == "DEPT_HEAD"
        assert updated_user["account_status"] == "active"

        # 6. Admin suspends account
        susp_res = await client.patch(
            f"/api/v1/auth/admin/users/{updated_user['id']}",
            json={"account_status": "suspended", "rejection_reason": "Policy violation"},
            headers=admin_headers,
        )
        assert susp_res.status_code == 200
        assert susp_res.json()["account_status"] == "suspended"

        # 7. Suspended user attempts to log in -> blocked with 403
        bad_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "applicant.hod@balbird.com", "password": "Password123!"},
        )
        assert bad_login.status_code == 403
        assert "suspended" in bad_login.json()["detail"]

        # 8. Admin reactivates account
        react_res = await client.patch(
            f"/api/v1/auth/admin/users/{updated_user['id']}",
            json={"account_status": "active"},
            headers=admin_headers,
        )
        assert react_res.status_code == 200
        assert react_res.json()["account_status"] == "active"
