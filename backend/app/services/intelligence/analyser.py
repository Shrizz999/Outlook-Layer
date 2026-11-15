"""Email Intelligence Analysis Service."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog

from app.domain.enums import MessageProcessingStatus
from app.integrations.ai_providers.provider import AIProvider, AIResult, create_ai_provider
from app.repositories.email_repo import EmailRepository
from app.schemas.email import EmailAnalysisRead, SourceMessageRead

logger = structlog.get_logger(__name__)


class EmailAnalysisService:
    def __init__(
        self,
        ai_provider: AIProvider | None = None,
        email_repo: EmailRepository | None = None,
    ) -> None:
        self._provider = ai_provider or create_ai_provider()
        self._repo = email_repo or EmailRepository()

    async def analyse_message(self, message: SourceMessageRead) -> EmailAnalysisRead:
        log = logger.bind(message_id=str(message.id))
        log.info("Starting AI analysis for email message")

        await self._repo.update_processing_status(message.id, MessageProcessingStatus.ANALYSING)

        result: AIResult = await self._provider.analyse_email(
            message_id=str(message.id),
            subject=message.subject,
            sender_address=message.sender_address,
            body_preprocessed=message.body_preprocessed,
            sent_at=message.sent_at,
            idempotency_key=f"analysis_{message.id}",
        )

        if not result.success or not result.analysis:
            log.warning("AI analysis provider returned error or exhausted quota; engaging heuristic fallback", error_class=getattr(result, "error_class", "UNKNOWN"))
            analysis_dict = self._create_heuristic_analysis(message, result.error_message if result else "Provider unavailable")
        else:
            analysis = result.analysis
            analysis_dict = {
                "provider": analysis.provider,
                "model": analysis.model,
                "prompt_version": analysis.prompt_version,
                "schema_version": analysis.schema_version,
                "department": analysis.department,
                "primary_department": getattr(analysis, "primary_department", analysis.department),
                "secondary_departments": getattr(analysis, "secondary_departments", []),
                "domain": analysis.domain,
                "intent": analysis.intent,
                "language": analysis.language,
                "priority": analysis.priority,
                "summary": analysis.summary,
                "requires_action": analysis.requires_action,
                "follow_up_required": analysis.follow_up_required,
                "follow_up_type": analysis.follow_up_type,
                "confidence": analysis.confidence,
                "human_review_required": analysis.human_review_required,
                "searchable_tags": getattr(analysis, "searchable_tags", []),
                "customers": getattr(analysis, "customers", []),
                "suppliers": getattr(analysis, "suppliers", []),
                "parts": getattr(analysis, "parts", []),
                "materials": getattr(analysis, "materials", []),
                "quantities": getattr(analysis, "quantities", []),
                "monetary_values": getattr(analysis, "monetary_values", []),
                "stock_states": getattr(analysis, "stock_states", []),
                "is_follow_up": getattr(analysis, "is_follow_up", False),
                "cross_department_connections": getattr(analysis, "cross_department_connections", []),
                "dates": [
                    {
                        "date": d.date.isoformat() if d.date else None,
                        "date_type": d.date_type,
                        "is_explicit": d.is_explicit,
                        "evidence": d.evidence,
                        "is_ambiguous": d.is_ambiguous,
                    }
                    for d in analysis.dates
                ],
                "references": [
                    {"type": r.type, "value": r.value, "confidence": r.confidence, "evidence": r.evidence}
                    for r in analysis.references
                ],
                "actions": [
                    {
                        "action_text": a.action_text,
                        "action_type": a.action_type,
                        "suggested_department": a.suggested_department,
                        "suggested_owner": a.suggested_owner,
                        "deadline": a.deadline.isoformat() if a.deadline else None,
                        "priority": a.priority,
                        "confidence": a.confidence,
                        "evidence": a.evidence,
                    }
                    for a in analysis.actions
                ],
                "commitments": [
                    {
                        "commitment_by": c.commitment_by,
                        "commitment_text": c.commitment_text,
                        "due_date": c.due_date.isoformat() if c.due_date else None,
                        "confidence": c.confidence,
                        "evidence": c.evidence,
                    }
                    for c in analysis.commitments
                ],
            }

        saved_analysis = await self._repo.save_email_analysis(message.id, analysis_dict)

        new_status = (
            MessageProcessingStatus.NEEDS_REVIEW
            if analysis_dict.get("human_review_required", False)
            else MessageProcessingStatus.ANALYSED
        )
        await self._repo.update_processing_status(message.id, new_status)

        log.info("Email analysis completed and saved", analysis_id=str(saved_analysis.id), status=new_status.value)
        return saved_analysis

    def _create_heuristic_analysis(self, message: SourceMessageRead, error_msg: str) -> dict[str, Any]:
        """Offline / Fallback deterministic heuristic analysis when AI provider is unavailable or quota exhausted."""
        import re

        body = f"{message.subject or ''}\n{message.body_preprocessed or message.body_text or ''}"
        body_lower = body.lower()

        # Department inference
        dept = "Sales Operations"
        if any(w in body_lower for w in ["drawing", "cad", "spec", "tolerance", "technical", "revc", "reva"]):
            dept = "Engineering"
        elif any(w in body_lower for w in ["capacity", "ppc", "schedule", "week 45", "slot"]):
            dept = "PPC"
        elif any(w in body_lower for w in ["purchase", "procurement", "supplier", "vendor", "shortfall"]):
            dept = "Purchase"
        elif any(w in body_lower for w in ["stock", "inventory", "stores", "warehouse"]):
            dept = "Stores"
        elif any(w in body_lower for w in ["machining", "cutting", "assembly", "shop floor", "production"]):
            dept = "Production"
        elif any(w in body_lower for w in ["qc", "inspection", "test cert", "quality"]):
            dept = "Quality"
        elif any(w in body_lower for w in ["dispatch", "logistics", "courier", "shipping", "dhl", "tracking"]):
            dept = "Dispatch"

        # Intent inference
        intent = "STATUS_INQUIRY"
        if any(w in body_lower for w in ["rfq", "quote", "please quote", "quotation"]):
            intent = "RFQ"
        elif any(w in body_lower for w in ["po", "purchase order", "po verified"]):
            intent = "PURCHASE_ORDER"
        elif any(w in body_lower for w in ["clarification", "confirm", "equivalent"]):
            intent = "TECHNICAL_CLARIFICATION"

        # References extraction
        refs = []
        for m in re.finditer(r"\b(SO|PO|RFQ)[-\s/]?([A-Z0-9\-_]{3,12})\b", body, re.IGNORECASE):
            refs.append({
                "type": m.group(1).upper(),
                "value": f"{m.group(1).upper()}-{m.group(2)}",
                "confidence": 0.90,
                "evidence": m.group(0),
            })
        for m in re.finditer(r"\b(AP-[A-Z0-9\-]+|DEMO-[A-Z0-9\-]+|HT-[0-9]+-[A-Z]+|GE[0-9]+[A-Z0-9/]+)\b", body):
            refs.append({
                "type": "PART",
                "value": m.group(1),
                "confidence": 0.88,
                "evidence": m.group(0),
            })

        # Actions
        actions = []
        if intent == "RFQ":
            actions.append({
                "action_text": f"Prepare commercial quotation for {message.subject or 'items'}",
                "action_type": "QUOTE",
                "suggested_department": dept,
                "priority": "HIGH" if "urgent" in body_lower else "NORMAL",
                "confidence": 0.85,
                "evidence": "Customer RFQ received",
            })
        elif "clarif" in body_lower or "confirm" in body_lower:
            actions.append({
                "action_text": f"Provide technical clarification for {message.subject or 'items'}",
                "action_type": "CLARIFICATION",
                "suggested_department": dept,
                "priority": "HIGH",
                "confidence": 0.85,
                "evidence": "Clarification requested",
            })

        priority = "CRITICAL" if any(w in body_lower for w in ["urgent", "shutdown", "immediate", "asap"]) else "HIGH" if "rfq" in body_lower else "NORMAL"

        return {
            "provider": "HEURISTIC_FALLBACK",
            "model": "rule-based-v1",
            "prompt_version": "heuristic",
            "schema_version": "1.0",
            "department": dept,
            "domain": "COMMERCIAL",
            "intent": intent,
            "language": "en",
            "priority": priority,
            "summary": (message.subject or "Email communication") + f": {(message.body_preprocessed or message.body_text or '')[:180]}...",
            "requires_action": len(actions) > 0,
            "follow_up_required": len(actions) > 0,
            "follow_up_type": "RESPONSE_REQUIRED" if len(actions) > 0 else None,
            "confidence": 0.80,
            "human_review_required": False,
            "references": refs,
            "actions": actions,
            "commitments": [],
            "note": f"Offline heuristic analysis applied (provider notice: {error_msg})",
        }
