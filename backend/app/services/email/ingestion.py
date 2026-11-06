"""Email Ingestion Service."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import structlog

from app.integrations.email_providers.fixture_provider import RawMessage
from app.repositories.email_repo import EmailRepository
from app.schemas.email import EmailRecipient, SourceMessageCreate, SourceMessageRead
from app.services.email.preprocessor import EmailPreprocessor
from app.services.intelligence.analyser import EmailAnalysisService

logger = structlog.get_logger(__name__)


@dataclass
class IngestionResult:
    imported_count: int
    duplicate_count: int
    imported_messages: list[SourceMessageRead]
    duplicate_messages: list[str]


class EmailIngestionService:
    def __init__(self, email_repo: EmailRepository | None = None, auto_analyse: bool = True) -> None:
        self._repo = email_repo or EmailRepository()
        self._preprocessor = EmailPreprocessor()
        self._auto_analyse = auto_analyse
        self._analyser = EmailAnalysisService(email_repo=self._repo) if auto_analyse else None

    async def ingest_raw_message(self, mailbox_id: UUID, raw: RawMessage) -> tuple[SourceMessageRead | None, bool]:
        """
        Ingest a single raw message and automatically run AI analysis.
        Returns (SourceMessageRead, is_duplicate).
        """
        log = logger.bind(mailbox_id=str(mailbox_id), provider_id=raw.provider_message_id)

        # 1. Deduplication check by provider_message_id
        existing = await self._repo.find_message_by_provider_id(mailbox_id, raw.provider_message_id)
        if existing:
            log.info("Duplicate message detected by provider_message_id")
            return existing, True

        # 2. Preprocess body
        prep = self._preprocessor.preprocess(raw.body_text, raw.sender_address)

        # 3. Deduplication check by body_hash
        existing_hash = await self._repo.find_message_by_body_hash(mailbox_id, prep.body_hash)
        if existing_hash:
            log.info("Duplicate message detected by body_hash", body_hash=prep.body_hash)
            return existing_hash, True

        # 4. Map recipients
        to_recipients = [
            EmailRecipient(address=r.get("address", ""), display_name=r.get("display_name"))
            for r in raw.to_recipients
            if r.get("address")
        ]
        cc_recipients = [
            EmailRecipient(address=r.get("address", ""), display_name=r.get("display_name"))
            for r in raw.cc_recipients
            if r.get("address")
        ]

        # 5. Persist
        create_data = SourceMessageCreate(
            source_mailbox_id=mailbox_id,
            provider_message_id=raw.provider_message_id,
            internet_message_id=raw.internet_message_id,
            provider_conversation_id=raw.provider_conversation_id,
            subject=raw.subject,
            sender_address=raw.sender_address,
            sender_display_name=raw.sender_display_name,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            sent_at=raw.sent_at,
            received_at=raw.received_at,
            body_text=raw.body_text,
            body_preprocessed=prep.cleaned_body,
            quoted_history_text=prep.quoted_history,
            signature_text=prep.signature,
            body_hash=prep.body_hash,
            has_attachments=raw.has_attachments,
            is_automated_notification=prep.is_automated,
            fixture_path=raw.source_fixture_path,
        )

        msg = await self._repo.create_source_message(create_data)
        log.info("Message ingested successfully", message_id=str(msg.id))

        # Auto-trigger AI analysis on incoming messages
        if self._auto_analyse and self._analyser:
            try:
                log.info("Auto-triggering AI analysis on newly ingested message", message_id=str(msg.id))
                analysis = await self._analyser.analyse_message(msg)
                msg.latest_analysis = analysis
            except Exception as e:
                log.warning("Auto-analysis failed during ingestion", error=str(e), message_id=str(msg.id))

        return msg, False

    async def ingest_batch(self, mailbox_id: UUID, raw_messages: list[RawMessage]) -> IngestionResult:
        imported: list[SourceMessageRead] = []
        duplicates: list[str] = []

        for raw in raw_messages:
            msg, is_dup = await self.ingest_raw_message(mailbox_id, raw)
            if is_dup:
                duplicates.append(raw.provider_message_id)
            elif msg:
                imported.append(msg)

        return IngestionResult(
            imported_count=len(imported),
            duplicate_count=len(duplicates),
            imported_messages=imported,
            duplicate_messages=duplicates,
        )
