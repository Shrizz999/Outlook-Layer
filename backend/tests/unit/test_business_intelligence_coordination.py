"""Unit tests for Business Intelligence, 3-Way Reconciliation, and Critical Path Coordination."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.enums import TaskProposalStatus
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.business_case import BusinessCaseCreate
from app.schemas.task import TaskDependencyCreate, TaskProposalCreate
from app.services.context.context_engine import BusinessContextEngine
from app.services.monitoring.risk_engine import MonitoringRiskEngine
from app.services.tasks.task_service import TaskCoordinationService


@pytest.mark.asyncio
async def test_three_way_reconciliation_matched():
    engine = BusinessContextEngine()

    quote = {
        "part_number": "PART-A100",
        "quantity": 500,
        "unit_price": 45.50,
        "lead_time_days": 14,
    }
    po = {
        "part_number": "PART-A100",
        "quantity": 500,
        "unit_price": 45.50,
        "delivery_date": "2026-12-15",
    }
    so = {
        "part_number": "PART-A100",
        "quantity": 500,
        "unit_price": 45.50,
        "delivery_date": "2026-12-10",
    }

    res = engine.reconcile_three_way_match(quote, po, so)
    assert res.status == "MATCHED"
    assert res.is_reconciled is True
    assert len(res.discrepancies) == 0
    assert "part_number" in res.matched_fields
    assert "quantity" in res.matched_fields
    assert "unit_price" in res.matched_fields


@pytest.mark.asyncio
async def test_three_way_reconciliation_critical_discrepancies():
    engine = BusinessContextEngine()

    # Quote vs PO price discrepancy & date conflict
    quote = {
        "part_number": "PART-B200",
        "quantity": 1000,
        "unit_price": 120.00,
    }
    po = {
        "part_number": "PART-B200",
        "quantity": 1000,
        "unit_price": 105.00,  # Lower price on PO!
        "delivery_date": "2026-11-20",
    }
    so = {
        "part_number": "PART-B200",
        "quantity": 900,  # Quantity shortfall on SO!
        "unit_price": 105.00,
        "delivery_date": "2026-11-25",  # Scheduled after customer PO deadline!
    }

    res = engine.reconcile_three_way_match(quote, po, so)
    assert res.status == "DISCREPANCY_DETECTED"
    assert res.is_reconciled is False
    assert len(res.discrepancies) >= 3

    types = [d.discrepancy_type for d in res.discrepancies]
    assert "PRICE_MISMATCH" in types
    assert "QUANTITY_MISMATCH" in types
    assert "DATE_CONFLICT" in types


@pytest.mark.asyncio
async def test_three_way_reconciliation_incomplete():
    engine = BusinessContextEngine()
    res = engine.reconcile_three_way_match(None, {"part_number": "PART-C"}, None)
    assert res.status == "INCOMPLETE"
    assert res.is_reconciled is False
    assert "missing Quotation, Sales Order" in res.summary


@pytest.mark.asyncio
async def test_critical_path_and_delay_propagation():
    task_repo = TaskRepository()
    service = TaskCoordinationService(task_repo=task_repo)

    # Create 3 sequential tasks: T1 -> T2 -> T3
    # Approving proposals writes to legacy tasks
    p1 = await task_repo.create_proposal(
        TaskProposalCreate(
            title="Design Review",
            task_type="DESIGN_APPROVAL",
            suggested_department="Engineering",
            priority="HIGH",
        )
    )
    t1 = await service.approve_proposal(p1.id, assigned_to_name="Eng Lead")

    p2 = await task_repo.create_proposal(
        TaskProposalCreate(
            title="Raw Material Procurement",
            task_type="PURCHASE_ORDER",
            suggested_department="Purchase",
            priority="HIGH",
        )
    )
    t2 = await service.approve_proposal(p2.id, assigned_to_name="Purchase Mgr")

    p3 = await task_repo.create_proposal(
        TaskProposalCreate(
            title="CNC Machining",
            task_type="PRODUCTION",
            suggested_department="Production",
            priority="NORMAL",
        )
    )
    t3 = await service.approve_proposal(p3.id, assigned_to_name="Shop Supervisor")

    # Add dependencies: T1 -> T2 and T2 -> T3
    await service.add_dependency_with_cycle_check(
        TaskDependencyCreate(
            predecessor_task_id=t1.task_id,
            successor_task_id=t2.task_id,
            dependency_type="FINISH_TO_START",
        )
    )
    await service.add_dependency_with_cycle_check(
        TaskDependencyCreate(
            predecessor_task_id=t2.task_id,
            successor_task_id=t3.task_id,
            dependency_type="FINISH_TO_START",
        )
    )

    # 1. Calculate Critical Path
    cp_result = await service.calculate_critical_path()
    assert cp_result["critical_path_duration_days"] >= 3
    assert t1.task_id in cp_result["critical_path_tasks"]
    assert t2.task_id in cp_result["critical_path_tasks"]
    assert t3.task_id in cp_result["critical_path_tasks"]

    # 2. Propagate Delay from T1
    delay_impact = await service.propagate_delay(t1.task_id, delay_days=5)
    assert delay_impact["delay_days"] == 5
    assert delay_impact["downstream_impacted_count"] == 2
    impacted_ids = [imp["task_id"] for imp in delay_impact["impacted_tasks"]]
    assert t2.task_id in impacted_ids
    assert t3.task_id in impacted_ids


@pytest.mark.asyncio
async def test_department_risk_scores_and_early_warning():
    risk_engine = MonitoringRiskEngine()

    scores = await risk_engine.calculate_department_risk_scores()
    assert isinstance(scores, dict)
    # Check standard departments are accounted for
    for dept in ["Engineering", "Purchase", "Production", "Quality", "Dispatch"]:
        assert dept in scores
        assert "risk_score" in scores[dept]
        assert "risk_level" in scores[dept]
        assert "active_tasks_count" in scores[dept]
