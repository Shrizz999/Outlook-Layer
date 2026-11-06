"""Smart Draft Generation Service."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.order_repo import OrderRepository
from app.schemas.draft import SmartDraftCreate, SmartDraftRead

logger = structlog.get_logger(__name__)


class SmartDraftService:
    def __init__(
        self,
        case_repo: BusinessCaseRepository | None = None,
        order_repo: OrderRepository | None = None,
    ) -> None:
        self._case_repo = case_repo or BusinessCaseRepository()
        self._order_repo = order_repo or OrderRepository()

    async def generate_supplier_followup_draft(
        self,
        case_id: UUID,
        supplier_name: str,
        part_number: str,
        so_number: str | None = None,
        creator_id: UUID | None = None,
    ) -> SmartDraftCreate:
        """
        Generates a supplier follow-up email draft for expected material delivery.
        Highlights missing parameters and warns if expected date is unverified.
        """
        missing_fields: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        # Find SO data if present
        so = await self._order_repo.get_sales_order_by_number(so_number) if so_number else None
        qty = 0
        if so:
            for l in so.lines:
                if l.source_part_number and l.source_part_number.upper() == part_number.upper():
                    qty = l.ordered_quantity or 0
        else:
            missing_fields.append({"field": "quantity", "reason": "No linked Sales Order quantity confirmed"})

        subject = f"Delivery Status Clarification — Part {part_number} (Ref: {so_number or 'Order'})"
        body = (
            f"Dear {supplier_name} Team,\n\n"
            f"We are following up regarding the delivery schedule for Part Number: {part_number}.\n"
            f"Quantity: {qty if qty else '[CONFIRM QUANTITY]'}.\n\n"
            f"Could you please confirm the expected dispatch date and provide tracking details when available?\n\n"
            f"Kind regards,\n"
            f"Balbird Procurement Team"
        )

        if not qty:
            warnings.append({"warning_type": "UNCONFIRMED_QUANTITY", "message": "Verify order quantity before sending"})

        return SmartDraftCreate(
            template_key="SUPPLIER_DELIVERY_FOLLOWUP",
            draft_type="SUPPLIER_FOLLOWUP",
            recipient_suggestions=[{"name": supplier_name, "role": "SUPPLIER"}],
            subject=subject,
            body=body,
            missing_fields=missing_fields,
            warnings=warnings,
            business_case_id=case_id,
            created_by_employee_id=creator_id or UUID("00000000-0000-0000-0000-000000000001"),
        )
