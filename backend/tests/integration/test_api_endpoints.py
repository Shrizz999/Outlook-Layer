"""Integration tests for FastAPI REST API Endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.repositories.store import get_store


@pytest.fixture(autouse=True)
def clean_store():
    get_store().clear()


@pytest.mark.asyncio
async def test_health_and_ready_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_health = await ac.get("/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "ok"

        r_ready = await ac.get("/ready")
        assert r_ready.status_code == 200
        assert r_ready.json()["status"] in ("ready", "degraded")


@pytest.mark.asyncio
async def test_business_cases_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create case
        payload = {
            "title": "API Test Case",
            "case_type": "ENQUIRY",
            "status": "NEW",
            "priority": "HIGH",
            "summary": "Testing API",
        }
        res = await ac.post("/api/v1/business-cases", json=payload)
        assert res.status_code == 201
        created = res.json()
        assert created["title"] == "API Test Case"
        assert created["case_number"].startswith("CASE-2026-")
        case_id = created["id"]

        # Get case
        res_get = await ac.get(f"/api/v1/business-cases/{case_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == case_id

        # List cases
        res_list = await ac.get("/api/v1/business-cases")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1


@pytest.mark.asyncio
async def test_dashboard_summary_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/admin/dashboard-summary")
        assert res.status_code == 200
        data = res.json()
        assert "metrics" in data
        assert "open_cases_count" in data["metrics"]
        assert "department_workload" in data
