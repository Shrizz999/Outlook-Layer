"""API v1 router — aggregates all route modules."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    alerts,
    auth,
    business_cases,
    departments,
    emails,
    employees,
    imports,
    orders,
    outlook,
    reviews,
    tasks,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(outlook.router, prefix="/outlook", tags=["outlook"])
router.include_router(emails.router, prefix="/emails", tags=["emails"])
router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
router.include_router(business_cases.router, prefix="/business-cases", tags=["business-cases"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(employees.router, prefix="/employees", tags=["employees"])
router.include_router(departments.router, prefix="/departments", tags=["departments"])
router.include_router(imports.router, prefix="/imports", tags=["imports"])
router.include_router(orders.router, prefix="/orders", tags=["orders"])
router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
