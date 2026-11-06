"""Business Context Engine.

Connects incoming emails, extracted entities, and operational records into
unified Business Cases using staged multi-signal candidate scoring.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import structlog

from app.domain.enums import CaseType, Priority
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.repositories.order_repo import OrderRepository
from app.schemas.business_case import BusinessCaseCreate, BusinessCaseRead, CaseLinkCreate
from app.schemas.email import EmailAnalysisRead, SourceMessageRead

logger = structlog.get_logger(__name__)


@dataclass
class MatchResult:
    business_case: BusinessCaseRead
    is_new_case: bool
    match_method: str
    confidence: float
    reason: str


class BusinessContextEngine:
    def __init__(
        self,
        case_repo: BusinessCaseRepository | None = None,
        order_repo: OrderRepository | None = None,
        master_repo: MasterDataRepository | None = None,
    ) -> None:
        self._case_repo = case_repo or BusinessCaseRepository()
        self._order_repo = order_repo or OrderRepository()
        self._master_repo = master_repo or MasterDataRepository()

    async def resolve_context(
        self,
        message: SourceMessageRead,
        analysis: EmailAnalysisRead | None = None,
    ) -> MatchResult:
        log = logger.bind(message_id=str(message.id))
        log.info("Resolving business context for email message")

        # 1. Extract candidate reference values from analysis or regex
        references: list[dict] = []
        if analysis and analysis.raw_structured_output:
            references = analysis.raw_structured_output.get("references", [])

        # Fallback regex extraction if AI found no references
        if not references:
            subject_body = f"{message.subject or ''} {message.body_preprocessed or ''}"
            for m in re.finditer(r"\b(SO|PO|RFQ)[-\s]?(\d{4,6})\b", subject_body, re.IGNORECASE):
                references.append({
                    "type": m.group(1).upper(),
                    "value": f"{m.group(1).upper()}-{m.group(2)}",
                    "confidence": 0.85,
                    "evidence": m.group(0),
                })

        # 2. Match exact SO reference
        so_refs = [r["value"] for r in references if r.get("type") == "SO"]
        for so_num in so_refs:
            order = await self._order_repo.get_sales_order_by_number(so_num)
            if order:
                # Check if an existing Business Case links to this SO
                existing_cases = await self._case_repo.list_cases(limit=100)
                for case in existing_cases:
                    for link in case.links:
                        if link.linked_object_type == "SO" and link.linked_object_id == str(order.id):
                            # Link message to existing case
                            await self._case_repo.add_case_link(
                                case.id,
                                CaseLinkCreate(
                                    linked_object_type="MESSAGE",
                                    linked_object_id=str(message.id),
                                    relationship_type="RELATED",
                                    match_method="EXACT_SO",
                                    match_confidence=0.98,
                                    validation_status="ACCEPTED_AUTO",
                                ),
                            )
                            log.info("Linked message to existing case by exact SO", case_number=case.case_number)
                            return MatchResult(
                                business_case=case,
                                is_new_case=False,
                                match_method="EXACT_SO",
                                confidence=0.98,
                                reason=f"Exact match on Sales Order {so_num}",
                            )

                # Order exists but no case yet -> Create new Business Case for this SO
                new_case = await self._case_repo.create_case(
                    BusinessCaseCreate(
                        title=f"Order {order.so_number} - {order.source_customer_name or 'Customer'}",
                        case_type=CaseType.ORDER.value,
                        priority=Priority.NORMAL.value,
                        primary_customer_id=order.customer_id,
                        summary=f"Created from email referencing Sales Order {order.so_number}",
                    )
                )
                # Link SO and Message
                await self._case_repo.add_case_link(
                    new_case.id,
                    CaseLinkCreate(
                        linked_object_type="SO",
                        linked_object_id=str(order.id),
                        relationship_type="PRIMARY",
                        match_method="EXACT_SO",
                        match_confidence=1.0,
                        validation_status="ACCEPTED_AUTO",
                    ),
                )
                await self._case_repo.add_case_link(
                    new_case.id,
                    CaseLinkCreate(
                        linked_object_type="MESSAGE",
                        linked_object_id=str(message.id),
                        relationship_type="RELATED",
                        match_method="EXACT_SO",
                        match_confidence=0.98,
                        validation_status="ACCEPTED_AUTO",
                    ),
                )
                log.info("Created new Business Case for SO", case_number=new_case.case_number, so_number=order.so_number)
                return MatchResult(
                    business_case=new_case,
                    is_new_case=True,
                    match_method="EXACT_SO",
                    confidence=0.98,
                    reason=f"Created new case for confirmed Sales Order {so_num}",
                )

        # 3. Fallback: Propose new case for enquiry / rfq / issue
        title = message.subject or f"Enquiry from {message.sender_display_name or message.sender_address or 'Unknown'}"
        case_type = CaseType.ENQUIRY.value
        if analysis:
            if analysis.intent == "RFQ":
                case_type = CaseType.RFQ.value
            elif analysis.intent == "PURCHASE_ORDER":
                case_type = CaseType.ORDER.value

        new_case = await self._case_repo.create_case(
            BusinessCaseCreate(
                title=title,
                case_type=case_type,
                priority=analysis.priority if analysis else Priority.NORMAL.value,
                summary=analysis.summary if analysis else f"Ingested from email: {title}",
            )
        )
        await self._case_repo.add_case_link(
            new_case.id,
            CaseLinkCreate(
                linked_object_type="MESSAGE",
                linked_object_id=str(message.id),
                relationship_type="PRIMARY",
                match_method="INITIAL_INGESTION",
                match_confidence=0.80,
                validation_status="ACCEPTED_AUTO",
            ),
        )
        log.info("Created new Business Case from email", case_number=new_case.case_number)
        return MatchResult(
            business_case=new_case,
            is_new_case=True,
            match_method="NEW_ENQUIRY",
            confidence=0.80,
            reason="Created new case for customer enquiry",
        )
