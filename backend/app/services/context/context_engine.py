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
from app.schemas.business_case import (
    BusinessCaseCreate,
    BusinessCaseRead,
    CaseLinkCreate,
    ThreeWayDiscrepancy,
    ThreeWayReconciliationResult,
)
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
        parent_message: SourceMessageRead | None = None,
    ) -> MatchResult:
        log = logger.bind(message_id=str(message.id))
        log.info("Resolving business context for email message")

        # 0. Thread / Parent Message association: If message is reply/thread member, inherit Business Case
        existing_cases = await self._case_repo.list_cases(limit=100)

        # 0a. Check link to parent message ID
        if parent_message:
            for case in existing_cases:
                for link in case.links:
                    if link.linked_object_type == "MESSAGE" and link.linked_object_id == str(parent_message.id):
                        await self._case_repo.add_case_link(
                            case.id,
                            CaseLinkCreate(
                                linked_object_type="MESSAGE",
                                linked_object_id=str(message.id),
                                relationship_type="THREAD_REPLY",
                                match_method="THREAD_ASSOCIATION",
                                match_confidence=0.99,
                                validation_status="ACCEPTED_AUTO",
                            ),
                        )
                        log.info("Linked reply message to existing case via parent message ID", case_number=case.case_number)
                        return MatchResult(
                            business_case=case,
                            is_new_case=False,
                            match_method="THREAD_ASSOCIATION",
                            confidence=0.99,
                            reason=f"Linked to thread parent case {case.case_number}",
                        )

        # 0b. Check parent message business_case_id attribute
        if parent_message and parent_message.business_case_id:
            parent_case = await self._case_repo.get_case_by_id(parent_message.business_case_id)
            if parent_case:
                await self._case_repo.add_case_link(
                    parent_case.id,
                    CaseLinkCreate(
                        linked_object_type="MESSAGE",
                        linked_object_id=str(message.id),
                        relationship_type="THREAD_REPLY",
                        match_method="THREAD_ASSOCIATION",
                        match_confidence=0.99,
                        validation_status="ACCEPTED_AUTO",
                    ),
                )
                log.info("Linked reply message to existing case via thread parent", case_number=parent_case.case_number)
                return MatchResult(
                    business_case=parent_case,
                    is_new_case=False,
                    match_method="THREAD_ASSOCIATION",
                    confidence=0.99,
                    reason=f"Linked to thread parent case {parent_case.case_number}",
                )

        # 0c. Check thread references / In-Reply-To
        if message.in_reply_to or message.references:
            target_ids = set(([message.in_reply_to] if message.in_reply_to else []) + (message.references or []))
            clean_targets = {t.strip("<>") for t in target_ids if t}
            for case in existing_cases:
                for link in case.links:
                    if link.linked_object_type == "MESSAGE" and link.linked_object_id in clean_targets:
                        await self._case_repo.add_case_link(
                            case.id,
                            CaseLinkCreate(
                                linked_object_type="MESSAGE",
                                linked_object_id=str(message.id),
                                relationship_type="THREAD_REPLY",
                                match_method="THREAD_REFERENCES",
                                match_confidence=0.95,
                                validation_status="ACCEPTED_AUTO",
                            ),
                        )
                        log.info("Linked message to case via references header", case_number=case.case_number)
                        return MatchResult(
                            business_case=case,
                            is_new_case=False,
                            match_method="THREAD_REFERENCES",
                            confidence=0.95,
                            reason=f"Matched thread reference to case {case.case_number}",
                        )

        # 0d. Check normalized thread subject match (e.g. "RE: RFQ - ..." matches "RFQ - ...")
        if message.subject:
            import re
            cleaned_sub = re.sub(r"^(?:re|fwd|fw|\s*\[.*?\]|\s*:\s*)+", "", message.subject, flags=re.IGNORECASE).strip().lower()
            if len(cleaned_sub) >= 8:
                for case in existing_cases:
                    case_clean = re.sub(r"^(?:re|fwd|fw|\s*\[.*?\]|\s*:\s*)+", "", case.title, flags=re.IGNORECASE).strip().lower()
                    if cleaned_sub == case_clean or cleaned_sub in case_clean or case_clean in cleaned_sub:
                        await self._case_repo.add_case_link(
                            case.id,
                            CaseLinkCreate(
                                linked_object_type="MESSAGE",
                                linked_object_id=str(message.id),
                                relationship_type="THREAD_REPLY",
                                match_method="THREAD_SUBJECT",
                                match_confidence=0.92,
                                validation_status="ACCEPTED_AUTO",
                            ),
                        )
                        log.info("Linked reply message to existing case via subject match", case_number=case.case_number)
                        return MatchResult(
                            business_case=case,
                            is_new_case=False,
                            match_method="THREAD_SUBJECT",
                            confidence=0.92,
                            reason=f"Linked to existing case {case.case_number} via thread subject match",
                        )

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

        # 2b. Match Cross-Department Connections (Machine Breakdown, Management Priority, SS304 Shortage, HR Onboarding)
        cross_conns = (analysis.raw_structured_output or {}).get("cross_department_connections", []) if analysis else []
        if cross_conns:
            for conn in cross_conns:
                refs_to_check = conn.get("business_references", [])
                for case in existing_cases:
                    case_title_upper = (case.title or "").upper()
                    if any(ref.upper() in case_title_upper for ref in refs_to_check if len(ref) >= 4):
                        await self._case_repo.add_case_link(
                            case.id,
                            CaseLinkCreate(
                                linked_object_type="MESSAGE",
                                linked_object_id=str(message.id),
                                relationship_type="RELATED",
                                match_method="CROSS_DEPARTMENT",
                                match_confidence=conn.get("confidence", 0.92),
                                validation_status="ACCEPTED_AUTO",
                            ),
                        )
                        log.info("Linked message to case via cross-department relationship", scenario=conn.get("scenario"), case_number=case.case_number)
                        return MatchResult(
                            business_case=case,
                            is_new_case=False,
                            match_method=f"CROSS_DEPT_{conn.get('scenario')}",
                            confidence=conn.get("confidence", 0.92),
                            reason=f"Cross-department connection: {conn.get('scenario_title')} linked to case {case.case_number}",
                        )

        # 3. Fallback: Propose new case for enquiry / rfq / issue
        title = message.subject or f"Enquiry from {message.sender_display_name or message.sender_address or 'Unknown'}"
        case_type = CaseType.ENQUIRY.value
        if analysis:
            if analysis.intent == "RFQ":
                case_type = CaseType.RFQ.value
            elif analysis.intent in ("PURCHASE_ORDER", "CUSTOMER_PO"):
                case_type = CaseType.ORDER.value
            elif analysis.intent in ("MACHINE_BREAKDOWN", "SPECIFICATION_MISMATCH", "MATERIAL_SHORTAGE"):
                case_type = CaseType.ISSUE.value

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

    def reconcile_three_way_match(
        self,
        quote: dict | None,
        po: dict | None,
        so: dict | None,
    ) -> ThreeWayReconciliationResult:
        """
        Reconciles Quotation, Purchase Order (PO), and Sales Order (SO) across:
        - Part numbers / specifications
        - Quantities
        - Unit prices / totals
        - Delivery / promised dates
        Identifies discrepancies, conflict severity, and whether order is fully cleared for production.
        """
        if not quote or not po or not so:
            missing = []
            if not quote: missing.append("Quotation")
            if not po: missing.append("Purchase Order")
            if not so: missing.append("Sales Order")
            return ThreeWayReconciliationResult(
                status="INCOMPLETE",
                is_reconciled=False,
                summary=f"Three-way matching incomplete: missing {', '.join(missing)}.",
                discrepancies=[],
                matched_fields=[],
                recommended_action=f"Obtain and link missing {', '.join(missing)} before production release.",
            )

        discrepancies: list[ThreeWayDiscrepancy] = []
        matched_fields: list[str] = []

        # 1. Part Number Reconciliation
        q_part = str(quote.get("part_number") or quote.get("part_id") or "").strip().upper()
        po_part = str(po.get("part_number") or po.get("part_id") or "").strip().upper()
        so_part = str(so.get("part_number") or so.get("part_id") or "").strip().upper()

        if q_part and po_part and so_part and (q_part == po_part == so_part):
            matched_fields.append("part_number")
        else:
            discrepancies.append(
                ThreeWayDiscrepancy(
                    field="part_number",
                    quote_value=q_part,
                    po_value=po_part,
                    so_value=so_part,
                    discrepancy_type="PART_MISMATCH",
                    severity="CRITICAL",
                    description=f"Part number mismatch: Quote={q_part}, PO={po_part}, SO={so_part}",
                )
            )

        # 2. Quantity Reconciliation
        try:
            q_qty = float(quote.get("quantity") or 0)
            po_qty = float(po.get("quantity") or 0)
            so_qty = float(so.get("quantity") or 0)

            if po_qty != so_qty:
                discrepancies.append(
                    ThreeWayDiscrepancy(
                        field="quantity",
                        quote_value=q_qty,
                        po_value=po_qty,
                        so_value=so_qty,
                        discrepancy_type="QUANTITY_MISMATCH",
                        severity="CRITICAL",
                        description=f"Sales Order quantity ({so_qty}) does not match Customer PO quantity ({po_qty})",
                    )
                )
            elif q_qty > 0 and q_qty != po_qty:
                discrepancies.append(
                    ThreeWayDiscrepancy(
                        field="quantity",
                        quote_value=q_qty,
                        po_value=po_qty,
                        so_value=so_qty,
                        discrepancy_type="QUANTITY_VARIATION",
                        severity="WARNING",
                        description=f"Customer PO quantity ({po_qty}) varies from initial Quotation ({q_qty})",
                    )
                )
                matched_fields.append("quantity_po_so")
            else:
                matched_fields.append("quantity")
        except (ValueError, TypeError):
            discrepancies.append(
                ThreeWayDiscrepancy(
                    field="quantity",
                    quote_value=quote.get("quantity"),
                    po_value=po.get("quantity"),
                    so_value=so.get("quantity"),
                    discrepancy_type="INVALID_QUANTITY",
                    severity="CRITICAL",
                    description="Non-numeric quantity detected in order specifications",
                )
            )

        # 3. Unit Price Reconciliation
        try:
            q_price = float(quote.get("unit_price") or 0)
            po_price = float(po.get("unit_price") or 0)
            so_price = float(so.get("unit_price") or 0)

            price_mismatch = False
            if abs(po_price - q_price) > 0.01 and q_price > 0:
                discrepancies.append(
                    ThreeWayDiscrepancy(
                        field="unit_price",
                        quote_value=q_price,
                        po_value=po_price,
                        so_value=so_price,
                        discrepancy_type="PRICE_MISMATCH",
                        severity="CRITICAL",
                        description=f"Customer PO unit price ({po_price}) does not match Quoted price ({q_price})",
                    )
                )
                price_mismatch = True

            if abs(so_price - po_price) > 0.01:
                discrepancies.append(
                    ThreeWayDiscrepancy(
                        field="unit_price",
                        quote_value=q_price,
                        po_value=po_price,
                        so_value=so_price,
                        discrepancy_type="INTERNAL_PRICE_MISMATCH",
                        severity="CRITICAL",
                        description=f"Sales Order unit price ({so_price}) differs from PO agreed price ({po_price})",
                    )
                )
                price_mismatch = True

            if not price_mismatch:
                matched_fields.append("unit_price")
        except (ValueError, TypeError):
            discrepancies.append(
                ThreeWayDiscrepancy(
                    field="unit_price",
                    quote_value=quote.get("unit_price"),
                    po_value=po.get("unit_price"),
                    so_value=so.get("unit_price"),
                    discrepancy_type="INVALID_PRICE",
                    severity="CRITICAL",
                    description="Invalid unit price values provided in matching records",
                )
            )

        # 4. Delivery Date Feasibility
        po_delivery = str(po.get("delivery_date") or "").strip()
        so_delivery = str(so.get("delivery_date") or "").strip()
        q_lead_time_days = quote.get("lead_time_days")

        if po_delivery and so_delivery:
            if po_delivery < so_delivery:
                discrepancies.append(
                    ThreeWayDiscrepancy(
                        field="delivery_date",
                        quote_value=q_lead_time_days,
                        po_value=po_delivery,
                        so_value=so_delivery,
                        discrepancy_type="DATE_CONFLICT",
                        severity="CRITICAL",
                        description=f"Sales Order scheduled completion ({so_delivery}) breaches Customer PO deadline ({po_delivery})",
                    )
                )
            else:
                matched_fields.append("delivery_date")

        # Determine overall reconciliation status
        has_critical = any(d.severity == "CRITICAL" for d in discrepancies)
        if has_critical:
            status_str = "DISCREPANCY_DETECTED"
            is_reconciled = False
            summary = f"Reconciliation failed with {len([d for d in discrepancies if d.severity == 'CRITICAL'])} critical discrepancies."
            recommended_action = "Hold production order until commercial and technical discrepancies are reviewed and approved by Sales and Engineering HODs."
        else:
            status_str = "MATCHED"
            is_reconciled = True
            summary = "Quotation, PO, and Sales Order are fully reconciled with 0 critical discrepancies."
            recommended_action = "Clear order for production scheduling and material requisition."

        return ThreeWayReconciliationResult(
            status=status_str,
            is_reconciled=is_reconciled,
            summary=summary,
            discrepancies=discrepancies,
            matched_fields=matched_fields,
            recommended_action=recommended_action,
        )
