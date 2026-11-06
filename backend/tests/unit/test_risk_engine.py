"""Unit tests for Monitoring & Risk Engine."""
import pytest
from datetime import date
from decimal import Decimal
from app.repositories.alert_repo import AlertRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.store import get_store
from app.schemas.order import MRPRecordBase, SalesOrderCreate, SalesOrderLineBase
from app.services.monitoring.risk_engine import MonitoringRiskEngine


@pytest.fixture(autouse=True)
def clean_store():
    get_store().clear()


@pytest.mark.asyncio
async def test_material_shortage_detection_and_deduplication():
    order_repo = OrderRepository()
    alert_repo = AlertRepository()
    risk_engine = MonitoringRiskEngine(alert_repo=alert_repo, order_repo=order_repo)

    # 1. Create SO for 100 units of HT-2045
    await order_repo.create_sales_order(
        SalesOrderCreate(
            so_number="SO-1025",
            lines=[
                SalesOrderLineBase(
                    line_number=1,
                    source_part_number="HT-2045",
                    ordered_quantity=Decimal("100"),
                )
            ],
        )
    )

    # 2. Create MRP record showing 60 units available (40 unit shortage)
    await order_repo.create_mrp_snapshot(
        "snapshot.xlsx",
        [
            MRPRecordBase(
                source_part_number="HT-2045",
                available_stock=Decimal("60"),
                required_quantity=Decimal("100"),
            )
        ],
    )

    # 3. Evaluate shortage -> Must generate alert
    alert = await risk_engine.evaluate_material_shortage("SO-1025", "HT-2045")
    assert alert is not None
    assert "Material shortage of 40 units" in alert.description
    assert alert.severity == "HIGH"
    assert alert.alert_type == "MATERIAL_SHORTAGE"

    # 4. Evaluate again -> Must deduplicate (not create a second alert)
    alert2 = await risk_engine.evaluate_material_shortage("SO-1025", "HT-2045")
    assert alert2 is not None
    assert alert2.id == alert.id

    all_alerts = await alert_repo.list_alerts()
    assert len(all_alerts) == 1


@pytest.mark.asyncio
async def test_no_shortage_when_stock_is_sufficient():
    order_repo = OrderRepository()
    alert_repo = AlertRepository()
    risk_engine = MonitoringRiskEngine(alert_repo=alert_repo, order_repo=order_repo)

    await order_repo.create_sales_order(
        SalesOrderCreate(
            so_number="SO-9999",
            lines=[
                SalesOrderLineBase(
                    line_number=1,
                    source_part_number="FL-1002",
                    ordered_quantity=Decimal("50"),
                )
            ],
        )
    )

    await order_repo.create_mrp_snapshot(
        "snapshot.xlsx",
        [
            MRPRecordBase(
                source_part_number="FL-1002",
                available_stock=Decimal("100"),
                required_quantity=Decimal("50"),
            )
        ],
    )

    alert = await risk_engine.evaluate_material_shortage("SO-9999", "FL-1002")
    assert alert is None
