"""Email & Ingestion Repository."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import MessageProcessingStatus
from app.repositories.store import get_store, get_supabase_client
from app.schemas.email import EmailAnalysisRead, EmailDashboardSummary, SourceMessageCreate, SourceMessageRead


class EmailRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    async def get_or_create_default_mailbox(self, provider: str = "FIXTURE", name: str = "Synthetic Test Mailbox") -> UUID:
        """Ensure a default mailbox exists for ingestion."""
        db_provider = "MICROSOFT_GRAPH" if provider == "MICROSOFT_GRAPH" else "FIXTURE"
        if self._client:
            res = self._client.table("bi_source_mailboxes").select("id").eq("provider", db_provider).execute()
            if res.data:
                return UUID(res.data[0]["id"])
            new_id = uuid4()
            self._client.table("bi_source_mailboxes").insert({
                "id": str(new_id),
                "provider": db_provider,
                "display_name": name,
                "is_enabled": True,
            }).execute()
            return new_id

        for mbox in self._store.bi_source_mailboxes.values():
            if mbox["provider"] == db_provider:
                return mbox["id"]
        new_id = uuid4()
        self._store.bi_source_mailboxes[str(new_id)] = {
            "id": new_id,
            "provider": db_provider,
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

    async def find_message_by_internet_message_id(self, internet_message_id: str) -> SourceMessageRead | None:
        if not internet_message_id:
            return None
        clean_id = internet_message_id.strip("<>")
        if self._client:
            res = self._client.table("bi_source_messages").select("*").or_(f"internet_message_id.eq.{clean_id},internet_message_id.eq.<{clean_id}>").execute()
            return SourceMessageRead(**res.data[0]) if res.data else None

        for msg in self._store.bi_source_messages.values():
            m_id = (msg.get("internet_message_id") or "").strip("<>")
            if m_id == clean_id:
                return SourceMessageRead(**msg)
        return None

    async def find_parent_thread_message(
        self,
        in_reply_to: str | None,
        references: list[str],
        subject: str | None,
        provider_conversation_id: str | None = None,
    ) -> SourceMessageRead | None:
        """Find parent message by conversation ID, In-Reply-To, References, or normalized Subject."""
        # 0. Try Provider Conversation ID (e.g. Thread ID)
        if provider_conversation_id:
            all_msgs = await self.list_messages(limit=200)
            for m in all_msgs:
                if m.provider_conversation_id == provider_conversation_id and str(m.id) != "":
                    return m

        # 1. Try In-Reply-To
        if in_reply_to:
            parent = await self.find_message_by_internet_message_id(in_reply_to)
            if parent:
                return parent

        # 2. Try References in reverse order (most recent first)
        for ref in reversed(references):
            parent = await self.find_message_by_internet_message_id(ref)
            if parent:
                return parent

        # 3. Try Subject match (strip Re:, Fwd:, FW:, etc.)
        if subject:
            import re
            cleaned_sub = re.sub(r"^(?:re|fwd|fw|\s*\[.*?\]|\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip().lower()
            if len(cleaned_sub) >= 5:
                all_msgs = await self.list_messages(limit=100)
                for m in all_msgs:
                    if m.subject:
                        m_clean = re.sub(r"^(?:re|fwd|fw|\s*\[.*?\]|\s*:\s*)+", "", m.subject, flags=re.IGNORECASE).strip().lower()
                        if m_clean == cleaned_sub and str(m.id) != "":
                            return m
        return None

    async def update_message_identity_attribution(
        self,
        message_id: UUID,
        emp_id: UUID | None,
        emp_name: str | None,
        confidence: float,
        evidence: str | None,
    ) -> None:
        msg_id_str = str(message_id)
        if self._client:
            try:
                self._client.table("bi_source_messages").update({
                    "attributed_employee_id": str(emp_id) if emp_id else None,
                    "attribution_confidence": confidence,
                    "attribution_evidence": evidence,
                }).eq("id", msg_id_str).execute()
            except Exception:
                pass
        if msg_id_str in self._store.bi_source_messages:
            self._store.bi_source_messages[msg_id_str]["attributed_employee_id"] = emp_id
            self._store.bi_source_messages[msg_id_str]["attributed_employee_name"] = emp_name
            self._store.bi_source_messages[msg_id_str]["attribution_confidence"] = confidence
            self._store.bi_source_messages[msg_id_str]["attribution_evidence"] = evidence

    async def update_message_business_case(self, message_id: UUID, case_id: UUID, case_number: str) -> None:
        msg_id_str = str(message_id)
        if self._client:
            try:
                self._client.table("bi_source_messages").update({
                    "business_case_id": str(case_id),
                }).eq("id", msg_id_str).execute()
            except Exception:
                pass
        if msg_id_str in self._store.bi_source_messages:
            self._store.bi_source_messages[msg_id_str]["business_case_id"] = case_id
            self._store.bi_source_messages[msg_id_str]["business_case_number"] = case_number

    async def get_email_dashboard_summary(self) -> EmailDashboardSummary:
        messages = await self.list_messages(limit=500)
        total = len(messages)
        success = sum(1 for m in messages if m.processing_status in ("ANALYSED", "ACCEPTED_AUTO", "ACCEPTED"))
        pending = sum(1 for m in messages if m.processing_status in ("PENDING", "ANALYSING", "WAITING_FOR_PROVIDER_QUOTA"))
        failed = sum(1 for m in messages if m.processing_status == "ANALYSIS_FAILED")
        review = sum(1 for m in messages if m.processing_status == "NEEDS_REVIEW")
        linked = sum(1 for m in messages if m.business_case_id is not None)
        unlinked = total - linked
        last_time = max([m.sent_at for m in messages if m.sent_at], default=None)

        breakdown: dict[str, int] = {}
        for m in messages:
            st = getattr(m, "source_type", "EML") or "EML"
            breakdown[st] = breakdown.get(st, 0) + 1

        return EmailDashboardSummary(
            total_ingested=total,
            successfully_processed=success,
            pending_processing=pending,
            failed_processing=failed,
            duplicate_count=0,
            awaiting_review_count=review,
            linked_to_cases_count=linked,
            unlinked_count=unlinked,
            last_ingestion_time=last_time,
            source_breakdown=breakdown,
        )

    async def create_source_message(self, data: SourceMessageCreate) -> SourceMessageRead:
        now = datetime.now(UTC)
        msg_id = uuid4()
        record = {
            "id": msg_id,
            "source_mailbox_id": data.source_mailbox_id,
            "conversation_id": None,
            "provider_conversation_id": data.provider_conversation_id,
            "provider_message_id": data.provider_message_id,
            "internet_message_id": data.internet_message_id,
            "in_reply_to": data.in_reply_to,
            "references": data.references,
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
            "source_type": getattr(data, "source_type", "EML"),
            "attachments_metadata": getattr(data, "attachments_metadata", []),
            "meeting_info": getattr(data, "meeting_info", None),
            "parsed_tables": getattr(data, "parsed_tables", []),
            "created_at": now,
            "updated_at": now,
        }

        if self._client:
            payload = {
                "id": str(msg_id),
                "source_mailbox_id": str(data.source_mailbox_id),
                "provider_message_id": data.provider_message_id,
                "internet_message_id": data.internet_message_id,
                "subject": data.subject,
                "sender_address": data.sender_address,
                "sender_display_name": data.sender_display_name,
                "to_recipients": record["to_recipients"],
                "cc_recipients": record["cc_recipients"],
                "sent_at": data.sent_at.isoformat() if data.sent_at else None,
                "received_at": data.received_at.isoformat() if data.received_at else None,
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
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            try:
                res = self._client.table("bi_source_messages").insert(payload).execute()
                return SourceMessageRead(**res.data[0])
            except Exception:
                pass

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
            case_map: dict[str, str] = {}
            if msg_ids:
                try:
                    res_a = self._client.table("bi_email_analyses").select("*").in_("source_message_id", msg_ids).order("processed_at", desc=True).execute()
                    for a_row in res_a.data:
                        s_id = str(a_row["source_message_id"])
                        if s_id not in analysis_map:
                            analysis_map[s_id] = EmailAnalysisRead(**a_row)
                except Exception:
                    pass

                try:
                    res_c = self._client.table("bi_case_links").select("business_case_id, linked_object_id").eq("linked_object_type", "MESSAGE").in_("linked_object_id", msg_ids).execute()
                    for c_row in res_c.data:
                        case_map[str(c_row["linked_object_id"])] = c_row["business_case_id"]
                except Exception:
                    pass

            return [
                SourceMessageRead(**{
                    **row,
                    "latest_analysis": analysis_map.get(str(row["id"])),
                    "business_case_id": case_map.get(str(row["id"])),
                })
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
            if not res.data:
                return None
            case_id = None
            try:
                res_c = self._client.table("bi_case_links").select("business_case_id").eq("linked_object_type", "MESSAGE").eq("linked_object_id", msg_id_str).limit(1).execute()
                if res_c.data:
                    case_id = res_c.data[0]["business_case_id"]
            except Exception:
                pass
            return SourceMessageRead(**{**res.data[0], "business_case_id": case_id})
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
            try:
                payload = {
                    **record,
                    "id": str(analysis_id),
                    "source_message_id": str(message_id),
                    "processed_at": now.isoformat(),
                }
                res = self._client.table("bi_email_analyses").insert(payload).execute()
                return EmailAnalysisRead(**res.data[0])
            except Exception:
                pass

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

    async def create_attachment_record(
        self,
        message_id: UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_path: str,
        parsed_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist attachment record to database/store."""
        now = datetime.now(UTC)
        att_id = uuid4()
        record = {
            "id": str(att_id),
            "message_id": str(message_id),
            "source_message_id": str(message_id),
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "byte_size": size_bytes,
            "storage_path": storage_path,
            "parsed_data": parsed_data or {},
            "created_at": now.isoformat(),
        }

        if self._client:
            try:
                self._client.table("bi_source_attachments").insert({
                    "id": str(att_id),
                    "source_message_id": str(message_id),
                    "filename": filename,
                    "content_type": content_type,
                    "byte_size": size_bytes,
                    "storage_path": storage_path,
                    "metadata": parsed_data or {},
                }).execute()
            except Exception:
                pass

        self._store.bi_source_attachments[str(att_id)] = record
        return record

    async def list_attachments_for_message(self, message_id: UUID) -> list[dict[str, Any]]:
        """List attachments associated with a specific message."""
        msg_str = str(message_id)
        if self._client:
            try:
                res = self._client.table("bi_source_attachments").select("*").eq("source_message_id", msg_str).execute()
                if res.data:
                    return res.data
            except Exception:
                pass
        return [
            a for a in self._store.bi_source_attachments.values()
            if str(a.get("source_message_id") or a.get("message_id")) == msg_str
        ]

    async def list_all_attachments(self, limit: int = 100) -> list[dict[str, Any]]:
        """List all stored attachments."""
        if self._client:
            try:
                res = self._client.table("bi_source_attachments").select("*").order("created_at", desc=True).limit(limit).execute()
                if res.data:
                    return res.data
            except Exception:
                pass
        return list(self._store.bi_source_attachments.values())[:limit]
