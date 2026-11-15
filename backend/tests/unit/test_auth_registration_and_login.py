"""
Unit Tests: Registration, Login, Session Management, and Password Security.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.main import app
from app.repositories.auth_repo import AuthRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.store import get_store
from app.schemas.auth import UserRegisterRequest
from datetime import UTC, datetime
from app.schemas.master_data import DepartmentCreate


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
async def test_valid_employee_registration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "jane.emp@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "SALES",
                "position": "Employee",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "jane.emp@balbird.com"
        assert data["full_name"] == "Jane Employee"
        assert data["department"] == "SALES"
        assert data["requested_position"] == "EMPLOYEE"
        assert data["approved_position"] == "EMPLOYEE"
        assert data["account_status"] == "active"
        assert data["employee_id"] is not None
        assert "password_hash" not in data


@pytest.mark.asyncio
async def test_valid_hod_registration_needs_approval():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Harry HOD",
                "email": "harry.hod@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "PURCHASE",
                "position": "HOD",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["requested_position"] == "DEPT_HEAD"
        # Restricted until approved
        assert data["approved_position"] == "EMPLOYEE"
        assert data["account_status"] == "pending_approval"


@pytest.mark.asyncio
async def test_valid_manager_registration_needs_approval():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Mary Manager",
                "email": "mary.mgr@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "MANAGEMENT",
                "position": "Manager",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["requested_position"] == "MANAGEMENT"
        assert data["approved_position"] == "EMPLOYEE"
        assert data["account_status"] == "pending_approval"


@pytest.mark.asyncio
async def test_administrator_registration_never_auto_granted():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Sneaky Admin Attempt",
                "email": "sneaky@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "MANAGEMENT",
                "position": "Administrator",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["requested_position"] == "SYSADMIN"
        # CRITICAL SECURITY RULE: Administrator privileges are NEVER auto-granted!
        assert data["approved_position"] == "EMPLOYEE"
        assert data["account_status"] == "pending_approval"


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "full_name": "Jane Employee",
            "email": "dup@balbird.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "department": "SALES",
            "position": "Employee",
        }
        res1 = await client.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == 201

        res2 = await client.post("/api/v1/auth/register", json=payload)
        assert res2.status_code == 400
        assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_password_mismatch_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "mismatch@balbird.com",
                "password": "Password123!",
                "confirm_password": "DifferentPassword123!",
                "department": "SALES",
                "position": "Employee",
            },
        )
        assert resp.status_code == 400
        assert "do not match" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_weak_password_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Less than 8 chars
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "weak1@balbird.com",
                "password": "Pass1",
                "confirm_password": "Pass1",
                "department": "SALES",
                "position": "Employee",
            },
        )
        assert resp.status_code in (400, 422)

        # Only letters
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "weak2@balbird.com",
                "password": "passwordonlyletters",
                "confirm_password": "passwordonlyletters",
                "department": "SALES",
                "position": "Employee",
            },
        )
        assert resp2.status_code == 400
        assert "number" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_department_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "invaliddept@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "ASTRONOMY_DEPARTMENT_DOES_NOT_EXIST",
                "position": "Employee",
            },
        )
        assert resp.status_code == 400
        assert "Invalid department" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_position_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "invalidpos@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "SALES",
                "position": "SuperSupremeLeader",
            },
        )
        assert resp.status_code == 400
        assert "Invalid position" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_successful_and_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register first
        await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "login_test@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "SALES",
                "position": "Employee",
            },
        )

        # Login
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "login_test@balbird.com", "password": "Password123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_token" in data
        assert data["user"]["email"] == "login_test@balbird.com"
        assert resp.cookies.get("session_token") is not None

        # Call /auth/me with Bearer token
        token = data["session_token"]
        me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "login_test@balbird.com"


@pytest.mark.asyncio
async def test_login_invalid_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Employee",
                "email": "badpwd@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "SALES",
                "position": "Employee",
            },
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "badpwd@balbird.com", "password": "WrongPassword999!"},
        )
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_email():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "does_not_exist@balbird.com", "password": "Password123!"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_suspended_account():
    auth_repo = AuthRepository()
    pwd_hash = hash_password("Password123!")
    account = await auth_repo.create_account({
        "email": "suspended@balbird.com",
        "password_hash": pwd_hash,
        "full_name": "Suspended Person",
        "department": "SALES",
        "account_status": "suspended",
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "suspended@balbird.com", "password": "Password123!"},
        )
        assert resp.status_code == 403
        assert "suspended" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_rate_limiting():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 5 consecutive failed logins
        for _ in range(5):
            r = await client.post(
                "/api/v1/auth/login",
                json={"email": "brute@balbird.com", "password": "WrongPassword!"},
            )
            assert r.status_code == 401

        # 6th attempt is rate limited
        r6 = await client.post(
            "/api/v1/auth/login",
            json={"email": "brute@balbird.com", "password": "WrongPassword!"},
        )
        assert r6.status_code == 429
        assert "Too many failed login attempts" in r6.json()["detail"]


@pytest.mark.asyncio
async def test_logout_invalidates_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register and login
        await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Logout User",
                "email": "logout@balbird.com",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "department": "SALES",
                "position": "Employee",
            },
        )
        l_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout@balbird.com", "password": "Password123!"},
        )
        token = l_resp.json()["session_token"]

        # Logout
        out_resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert out_resp.status_code == 200

        # Now /auth/me should fail with 401
        me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 401
