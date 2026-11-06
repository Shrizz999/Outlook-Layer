"""
Balbird Intelligence — Email Provider Interface and Fixture Adapter
"""
from __future__ import annotations

import email as email_lib
import email.policy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Protocol

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class RawMessage:
    """Raw message as fetched from a provider."""
    provider_message_id: str
    internet_message_id: str | None
    provider_conversation_id: str | None
    subject: str | None
    sender_address: str | None
    sender_display_name: str | None
    to_recipients: list[dict]
    cc_recipients: list[dict]
    sent_at: datetime | None
    received_at: datetime | None
    body_text: str | None
    has_attachments: bool
    source_fixture_path: str | None = None

    @property
    def body_hash(self) -> str | None:
        if self.body_text:
            return hashlib.sha256(self.body_text.encode()).hexdigest()
        return None


class EmailProvider(Protocol):
    async def list_messages(self, *, limit: int = 100, offset: int = 0) -> list[str]:
        """Return list of provider message IDs."""
        ...

    async def get_message(self, provider_message_id: str) -> RawMessage | None:
        """Fetch a single message by provider ID."""
        ...

    async def import_batch(self, source_path: str) -> AsyncIterator[RawMessage]:
        """Import messages from a batch source (file, directory, etc.)."""
        ...


class FixtureEmailProvider:
    """
    Reads synthetic email fixtures from JSON files or .eml files.
    Safe: no real mailbox access, no external connections.
    """

    def __init__(self, fixture_dir: str | None = None) -> None:
        settings = get_settings()
        self._fixture_dir = Path(fixture_dir or settings.fixture_email_dir)

    async def list_messages(self, *, limit: int = 100, offset: int = 0) -> list[str]:
        messages = []
        for f in sorted(self._fixture_dir.glob("*.json"))[:limit]:
            messages.append(f.stem)
        for f in sorted(self._fixture_dir.glob("*.eml"))[:limit]:
            messages.append(f.stem)
        return messages[offset:offset + limit]

    async def get_message(self, provider_message_id: str) -> RawMessage | None:
        # Try JSON first
        json_path = self._fixture_dir / f"{provider_message_id}.json"
        if json_path.exists():
            return self._load_json_fixture(json_path)
        # Try .eml
        eml_path = self._fixture_dir / f"{provider_message_id}.eml"
        if eml_path.exists():
            return self._load_eml_fixture(eml_path)
        return None

    async def import_from_file(self, source_path: str) -> list[RawMessage]:
        """Import messages from a JSON batch file or directory."""
        path = Path(source_path)
        messages: list[RawMessage] = []

        if path.is_dir():
            for json_file in sorted(path.glob("*.json")):
                msg = self._load_json_fixture(json_file)
                if msg:
                    messages.append(msg)
            for eml_file in sorted(path.glob("*.eml")):
                msg = self._load_eml_fixture(eml_file)
                if msg:
                    messages.append(msg)
        elif path.suffix == ".json":
            # Could be a batch file (array) or single message
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    msg = self._parse_json_message(item, str(path))
                    if msg:
                        messages.append(msg)
            else:
                msg = self._parse_json_message(data, str(path))
                if msg:
                    messages.append(msg)
        elif path.suffix == ".eml":
            msg = self._load_eml_fixture(path)
            if msg:
                messages.append(msg)

        logger.info("Fixture import complete", source=source_path, count=len(messages))
        return messages

    def _load_json_fixture(self, path: Path) -> RawMessage | None:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            return self._parse_json_message(data, str(path))
        except Exception as exc:
            logger.warning("Failed to load JSON fixture", path=str(path), error=str(exc))
            return None

    def _parse_json_message(self, data: dict, source_path: str) -> RawMessage | None:
        try:
            sent_at = None
            if data.get("sent_at"):
                from dateutil.parser import parse as parse_dt
                sent_at = parse_dt(data["sent_at"])

            return RawMessage(
                provider_message_id=data.get("id", data.get("message_id", Path(source_path).stem)),
                internet_message_id=data.get("internet_message_id"),
                provider_conversation_id=data.get("conversation_id"),
                subject=data.get("subject"),
                sender_address=data.get("sender", {}).get("address", data.get("sender_address")),
                sender_display_name=data.get("sender", {}).get("name", data.get("sender_display_name")),
                to_recipients=data.get("to_recipients", []),
                cc_recipients=data.get("cc_recipients", []),
                sent_at=sent_at,
                received_at=sent_at,
                body_text=data.get("body_text", data.get("body")),
                has_attachments=bool(data.get("has_attachments", False)),
                source_fixture_path=source_path,
            )
        except Exception as exc:
            logger.warning("Failed to parse JSON message", error=str(exc))
            return None

    def _load_eml_fixture(self, path: Path) -> RawMessage | None:
        try:
            with path.open("rb") as f:
                msg = email_lib.message_from_binary_file(f, policy=email_lib.policy.default)
            return self._parse_eml_message(msg, str(path))
        except Exception as exc:
            logger.warning("Failed to load .eml fixture", path=str(path), error=str(exc))
            return None

    def _parse_eml_message(self, msg: email_lib.message.EmailMessage, source_path: str) -> RawMessage:
        from dateutil.parser import parse as parse_dt

        sent_at = None
        date_str = msg.get("Date")
        if date_str:
            try:
                sent_at = parse_dt(str(date_str))
            except Exception:
                pass

        # Extract text body
        body_text = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(charset, errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body_text = payload.decode(charset, errors="replace")

        def parse_address_list(header: str | None) -> list[dict]:
            if not header:
                return []
            # Simple parsing; real production would use email.headerregistry
            results = []
            for addr in str(header).split(","):
                addr = addr.strip()
                if "<" in addr:
                    name, email_addr = addr.rsplit("<", 1)
                    results.append({
                        "display_name": name.strip().strip('"'),
                        "address": email_addr.rstrip(">").strip(),
                    })
                elif addr:
                    results.append({"display_name": "", "address": addr})
            return results

        return RawMessage(
            provider_message_id=msg.get("Message-ID", Path(source_path).stem).strip("<>"),
            internet_message_id=msg.get("Message-ID", "").strip("<>") or None,
            provider_conversation_id=msg.get("Thread-Index"),
            subject=str(msg.get("Subject", "")).strip() or None,
            sender_address=str(msg.get("From", "")).split("<")[-1].rstrip(">").strip() or None,
            sender_display_name=str(msg.get("From", "")).split("<")[0].strip().strip('"') or None,
            to_recipients=parse_address_list(msg.get("To")),
            cc_recipients=parse_address_list(msg.get("Cc")),
            sent_at=sent_at,
            received_at=sent_at,
            body_text=body_text,
            has_attachments=any(
                part.get_content_disposition() == "attachment"
                for part in (msg.walk() if msg.is_multipart() else [])
            ),
            source_fixture_path=source_path,
        )
