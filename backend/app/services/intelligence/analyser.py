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

        if not result.success:
            log.warning("AI analysis failed or quota exhausted", error_class=result.error_class)
            status = (
                MessageProcessingStatus.WAITING_FOR_PROVIDER_QUOTA
                if result.error_class == "QUOTA_EXHAUSTED"
                else MessageProcessingStatus.ANALYSIS_FAILED
            )
            await self._repo.update_processing_status(message.id, status)
            raise RuntimeError(f"AI analysis failed: {result.error_message}")

        analysis = result.analysis
        if not analysis:
            await self._repo.update_processing_status(message.id, MessageProcessingStatus.ANALYSIS_FAILED)
            raise RuntimeError("Provider returned success but analysis is None")

        analysis_dict = {
            "provider": analysis.provider,
            "model": analysis.model,
            "prompt_version": analysis.prompt_version,
            "schema_version": analysis.schema_version,
            "department": analysis.department,
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
            "references": [
                {"type": r.type, "value": r.value, "confidence": r.confidence, "evidence": r.evidence}
                for r in analysis.references
            ],
            "actions": [
                {
                    "action_text": a.action_text,
                    "action_type": a.action_type,
                    "suggested_department": a.suggested_department,
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
            if analysis.human_review_required
            else MessageProcessingStatus.ANALYSED
        )
        await self._repo.update_processing_status(message.id, new_status)

        log.info("AI analysis completed and saved", analysis_id=str(saved_analysis.id), status=new_status.value)
        return saved_analysis
