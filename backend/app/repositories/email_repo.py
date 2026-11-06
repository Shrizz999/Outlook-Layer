"""Email & Ingestion Repository."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import MessageProcessingStatus
from app.repositories.store import get_store, get_supabase_client
from app.schemas.email import EmailAnalysisRead, SourceMessageCreate, SourceMessageRead


class EmailRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    async def get_or_create_default_mailbox(self, provider: str = "FIXTURE", name: str = "Synthetic Test Mailbox") -> UUID:
        """Ensure a default mailbox exists for ingestion."""
        if self._client:
            res = self._client.table("bi_source_mailboxes").select("id").eq("provider", provider).execute()
            if res.data:
                return UUID(res.data[0]["id"])
            new_id = uuid4()
            self._client.table("bi_source_mailboxes").insert({
                "id": str(new_id),
                "provider": provider,
                "display_name": name,
                "is_enabled": True,
            }).execute()
            return new_id

        for mbox in self._store.bi_source_mailboxes.values():
            if mbox["provider"] == provider:
                return mbox["id"]
        new_id = uuid4()
        self._store.bi_source_mailboxes[str(new_id)] = {
            "id": new_id,
            "provider": provider,
            "display_name": name,
            "is_enabled": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        return new_id

    async def find_message_by_provider_id(self, mailbox_id: UUID, provider_message_id: str) -> SourceMessageRead | None:
        if self._client:
            res = self._client.table("bi_source_messages").select("*").eq("source_mailbox_id", str(mailbox_id)).eq("provider_message_id", provider_message_id).execute()
            return SourceMessageRead(**res.data[0]) if res.data else None

        for msg in self._store.bi_source_messages.values():
            if msg["source_mailbox_id"] == mailbox_id and msg["provider_message_id"] == provider_message_id:
                return SourceMessageRead(**msg)
        return None

    async def find_message_by_body_hash(self, mailbox_id: UUID, body_hash: str) -> SourceMessageRead | None:
        if not body_hash:
            return None
        if self._client:
            res = self._client.table("bi_source_messages").select("*").eq("source_mailbox_id", str(mailbox_id)).eq("body_hash", body_hash).execute()
            return SourceMessageRead(**res.data[0]) if res.data else None

        for msg in self._store.bi_source_messages.values():
            if msg["source_mailbox_id"] == mailbox_id and msg.get("body_hash") == body_hash:
                return SourceMessageRead(**msg)
        return None

    async def create_source_message(self, data: SourceMessageCreate) -> SourceMessageRead:
        now = datetime.now(UTC)
        msg_id = uuid4()
        record = {
            "id": msg_id,
            "source_mailbox_id": data.source_mailbox_id,
            "conversation_id": None,
            "provider_message_id": data.provider_message_id,
            "internet_message_id": data.internet_message_id,
            "subject": data.subject,
            "sender_address": data.sender_address,
            "sender_display_name": data.sender_display_name,
            "to_recipients": [r.model_dump() for r in data.to_recipients],
            "cc_recipients": [r.model_dump() for r in data.cc_recipients],
            "sent_at": data.sent_at,
            "received_at": data.received_at,
            "body_text": data.body_text,
            "body_preprocessed": data.body_preprocessed,
            "quoted_history_text": data.quoted_history_text,
            "signature_text": data.signature_text,
            "body_hash": data.body_hash,
            "has_attachments": data.has_attachments,
            "is_automated_notification": data.is_automated_notification,
            "is_read_only_source": True,
            "processing_status": MessageProcessingStatus.PENDING.value,
            "fixture_path": data.fixture_path,
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            payload = {
                **record,
                "id": str(msg_id),
                "source_mailbox_id": str(data.source_mailbox_id),
                "sent_at": data.sent_at.isoformat() if data.sent_at else None,
                "received_at": data.received_at.isoformat() if data.received_at else None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            res = self._client.table("bi_source_messages").insert(payload).execute()
            return SourceMessageRead(**res.data[0])

        self._store.bi_source_messages[str(msg_id)] = record
        return SourceMessageRead(**record)

    async def list_messages(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SourceMessageRead]:
        if self._client:
            q = self._client.table("bi_source_messages").select("*")
            if status:
                q = q.eq("processing_status", status)
            res = q.range(offset, offset + limit - 1).order("sent_at", desc=True).execute()
            
            # Fetch latest analysis for each message
            msg_ids = [row["id"] for row in res.data]
            analysis_map: dict[str, EmailAnalysisRead] = {}
            if msg_ids:
                try:
                    res_a = self._client.table("bi_email_analyses").select("*").in_("source_message_id", msg_ids).order("processed_at", desc=True).execute()
                    for a_row in res_a.data:
                        s_id = str(a_row["source_message_id"])
                        if s_id not in analysis_map:
                            analysis_map[s_id] = EmailAnalysisRead(**a_row)
                except Exception:
                    pass

            return [
                SourceMessageRead(**{**row, "latest_analysis": analysis_map.get(str(row["id"]))})
                for row in res.data
            ]

        results = []
        for msg in self._store.bi_source_messages.values():
            if not status or msg["processing_status"] == status:
                # find analysis
                a_match = None
                for a in self._store.bi_email_analyses.values():
                    if str(a["source_message_id"]) == str(msg["id"]):
                        a_match = EmailAnalysisRead(**a)
                        break
                results.append(SourceMessageRead(**{**msg, "latest_analysis": a_match}))

        results.sort(key=lambda x: x.sent_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return results[offset : offset + limit]

    async def get_message_by_id(self, message_id: UUID) -> SourceMessageRead | None:
        msg_id_str = str(message_id)
        if self._client:
            res = self._client.table("bi_source_messages").select("*").eq("id", msg_id_str).execute()
            return SourceMessageRead(**res.data[0]) if res.data else None
        data = self._store.bi_source_messages.get(msg_id_str)
        return SourceMessageRead(**data) if data else None

    async def update_processing_status(self, message_id: UUID, status: MessageProcessingStatus) -> None:
        msg_id_str = str(message_id)
        now = datetime.now(UTC)
        if self._client:
            self._client.table("bi_source_messages").update({
                "processing_status": status.value,
                "updated_at": now.isoformat(),
            }).eq("id", msg_id_str).execute()
        elif msg_id_str in self._store.bi_source_messages:
            self._store.bi_source_messages[msg_id_str]["processing_status"] = status.value
            self._store.bi_source_messages[msg_id_str]["updated_at"] = now

    async def save_email_analysis(self, message_id: UUID, analysis_data: dict[str, Any]) -> EmailAnalysisRead:
        now = datetime.now(UTC)
        analysis_id = uuid4()
        record = {
            "id": analysis_id,
            "source_message_id": message_id,
            "analysis_version": 1,
            "model_provider": analysis_data.get("provider"),
            "model_name": analysis_data.get("model"),
            "prompt_version": analysis_data.get("prompt_version"),
            "schema_version": analysis_data.get("schema_version", "1.0"),
            "department": analysis_data.get("department"),
            "domain": analysis_data.get("domain"),
            "intent": analysis_data.get("intent"),
            "language": analysis_data.get("language", "en"),
            "priority": analysis_data.get("priority", "NORMAL"),
            "summary": analysis_data.get("summary"),
            "requires_action": analysis_data.get("requires_action", False),
            "follow_up_required": analysis_data.get("follow_up_required", False),
            "follow_up_type": analysis_data.get("follow_up_type"),
            "confidence": analysis_data.get("confidence", 0.0),
            "validation_status": "NEEDS_REVIEW" if analysis_data.get("human_review_required") else "ACCEPTED_AUTO",
            "raw_structured_output": analysis_data,
            "processed_at": now,
        }

        if self._client:
            payload = {
                **record,
                "id": str(analysis_id),
                "source_message_id": str(message_id),
                "processed_at": now.isoformat(),
            }
            res = self._client.table("bi_email_analyses").insert(payload).execute()
            return EmailAnalysisRead(**res.data[0])

        self._store.bi_email_analyses[str(analysis_id)] = record
        return EmailAnalysisRead(**record)

    async def get_analysis_for_message(self, message_id: UUID) -> EmailAnalysisRead | None:
        msg_id_str = str(message_id)
        if self._client:
            res = self._client.table("bi_email_analyses").select("*").eq("source_message_id", msg_id_str).order("processed_at", desc=True).limit(1).execute()
            return EmailAnalysisRead(**res.data[0]) if res.data else None

        for a in self._store.bi_email_analyses.values():
            if str(a["source_message_id"]) == msg_id_str:
                return EmailAnalysisRead(**a)
        return None
