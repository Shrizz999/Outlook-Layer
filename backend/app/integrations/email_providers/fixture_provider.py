"""
Balbird Intelligence — Email Provider Interface and Fixture Adapter
"""
from __future__ import annotations

import csv
import email as email_lib
import email.policy
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Protocol

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
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    attachments_metadata: list[dict[str, Any]] = field(default_factory=list)
    parsed_tables: list[dict[str, Any]] = field(default_factory=list)
    meeting_info: dict[str, Any] | None = None
    source_type: str = "EML"

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

        # Extract text body (prefer text/plain, fallback to stripped text/html)
        body_text = None
        html_fallback = None
        attachments_meta: list[dict[str, Any]] = []
        parsed_tables: list[dict[str, Any]] = []
        meeting_info: dict[str, Any] | None = None

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get_content_disposition() or "").lower()
                fname = part.get_filename()

                # Calendar invite payload
                if ctype in ("text/calendar", "application/ics") or (fname and fname.lower().endswith(".ics")):
                    payload = part.get_payload(decode=True)
                    if payload:
                        ics_text = payload.decode("utf-8", errors="replace")
                        meeting_info = self._parse_ics_text(ics_text)

                if ctype == "text/plain" and disp != "attachment" and not body_text:
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(charset, errors="replace")
                elif ctype == "text/html" and disp != "attachment" and not html_fallback:
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_fallback = self._extract_text_from_html(payload.decode(charset, errors="replace"))

                # Attachments
                if disp == "attachment" or fname:
                    payload = part.get_payload(decode=True)
                    size = len(payload) if payload else 0
                    meta_item = {
                        "filename": fname or f"attachment_{len(attachments_meta) + 1}",
                        "content_type": ctype,
                        "size_bytes": size,
                    }
                    if payload and fname:
                        meta_item["payload"] = payload
                        parsed_doc = self._parse_supported_attachment(payload, fname)
                        if parsed_doc:
                            meta_item["parsed_data"] = parsed_doc
                            if parsed_doc.get("tables"):
                                parsed_tables.extend(parsed_doc["tables"])
                    attachments_meta.append(meta_item)
        else:
            ctype = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if ctype == "text/plain":
                    body_text = decoded
                elif ctype == "text/html":
                    body_text = self._extract_text_from_html(decoded)
                elif ctype in ("text/calendar", "application/ics"):
                    meeting_info = self._parse_ics_text(decoded)
                    body_text = f"Meeting Invitation: {meeting_info.get('summary', 'Meeting')}\n{meeting_info.get('description', '')}"

        if not body_text and html_fallback:
            body_text = html_fallback

        # Check adjacent attachments folder & Attachment_Manifest.csv if present
        if source_path:
            p_src = Path(source_path)
            candidate_dirs = [
                p_src.parent / "attachments",
                p_src.parent.parent / "attachments",
            ]
            att_dir = next((d for d in candidate_dirs if d.is_dir()), None)
            if att_dir:
                manifest_file = att_dir.parent / "Attachment_Manifest.csv"
                email_id_key = p_src.stem
                test_email_id = str(msg.get("X-Balbird-Test-Email-ID", "")).strip()

                matched_files: list[str] = []
                if manifest_file.exists():
                    try:
                        with manifest_file.open("r", encoding="utf-8-sig") as mf:
                            reader = csv.DictReader(mf)
                            for r in reader:
                                ref_ids = str(r.get("Referenced Email IDs") or r.get("Email_IDs") or "")
                                fn = str(r.get("Attachment Filename") or r.get("Attachment") or "").strip()
                                if fn and (email_id_key in ref_ids or (test_email_id and test_email_id in ref_ids)):
                                    matched_files.append(fn)
                    except Exception:
                        pass

                for mf in matched_files:
                    if not any(a.get("filename") == mf for a in attachments_meta):
                        target_file = att_dir / mf
                        if target_file.exists():
                            file_bytes = target_file.read_bytes()
                            parsed_doc = self._parse_supported_attachment(file_bytes, mf)
                            meta_item = {
                                "filename": mf,
                                "content_type": "application/octet-stream",
                                "size_bytes": len(file_bytes),
                                "payload": file_bytes,
                                "parsed_data": parsed_doc,
                            }
                            if parsed_doc and parsed_doc.get("tables"):
                                parsed_tables.extend(parsed_doc["tables"])
                            attachments_meta.append(meta_item)

        def parse_address_list(header: str | None) -> list[dict]:
            if not header:
                return []
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

        in_reply_to = msg.get("In-Reply-To", "").strip("<>") or None
        ref_header = msg.get("References", "")
        references = [r.strip("<>") for r in ref_header.split() if r.strip("<>")]

        test_thread_id = str(msg.get("X-Balbird-Test-Thread-ID", "")).strip()
        provider_conversation_id = test_thread_id or msg.get("Thread-Index")
        test_msg_id = str(msg.get("X-Balbird-Test-Email-ID", "")).strip()
        raw_msg_id = (test_msg_id or msg.get("Message-ID", Path(source_path).stem)).strip("<>")

        return RawMessage(
            provider_message_id=raw_msg_id,
            internet_message_id=msg.get("Message-ID", "").strip("<>") or raw_msg_id,
            provider_conversation_id=provider_conversation_id,
            in_reply_to=in_reply_to,
            references=references,
            subject=str(msg.get("Subject", "")).strip() or None,
            sender_address=str(msg.get("From", "")).split("<")[-1].rstrip(">").strip() or None,
            sender_display_name=str(msg.get("From", "")).split("<")[0].strip().strip('"') or None,
            to_recipients=parse_address_list(msg.get("To")),
            cc_recipients=parse_address_list(msg.get("Cc")),
            sent_at=sent_at,
            received_at=sent_at,
            body_text=body_text,
            has_attachments=bool(attachments_meta),
            attachments_metadata=attachments_meta,
            parsed_tables=parsed_tables,
            meeting_info=meeting_info,
            source_fixture_path=source_path,
        )

    def _extract_text_from_html(self, html: str) -> str:
        """Strip HTML tags while preserving linebreaks."""
        text = re.sub(r"<(?:p|br|div|tr|li)[^>]*>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)
        text = re.sub(r"&lt;", "<", text, flags=re.IGNORECASE)
        text = re.sub(r"&gt;", ">", text, flags=re.IGNORECASE)
        return "\n".join(line.strip() for line in text.split("\n") if line.strip())

    def _parse_ics_text(self, ics_text: str) -> dict[str, Any]:
        """Parse RFC 5545 calendar invitation and extract agenda & action items."""
        summary, organizer, dtstart, dtend, location, description = "", "", "", "", "", ""
        attendees = []

        # Unfold lines (RFC 5545 folding: newline followed by whitespace)
        unfolded = re.sub(r"\r?\n[ \t]", "", ics_text)
        for line in unfolded.splitlines():
            line = line.strip()
            if line.startswith("SUMMARY:"):
                summary = line[8:].strip()
            elif line.startswith("ORGANIZER:"):
                organizer = line[10:].replace("mailto:", "").strip()
            elif line.startswith("DTSTART"):
                dtstart = line.split(":", 1)[-1].strip()
            elif line.startswith("DTEND"):
                dtend = line.split(":", 1)[-1].strip()
            elif line.startswith("LOCATION:"):
                location = line[9:].strip()
            elif line.startswith("ATTENDEE"):
                attendees.append(line.split(":", 1)[-1].replace("mailto:", "").strip())
            elif line.startswith("DESCRIPTION:"):
                description = line[12:].replace("\\n", "\n").strip()

        # Extract agenda and action items from description
        action_items = []
        agenda_items = []
        if description:
            for l in description.splitlines():
                l_str = l.strip()
                if re.match(r"^(?:Action|Task|TODO|Action Item|\d+\.|\- \[ \])[:\s]", l_str, re.IGNORECASE):
                    action_items.append(re.sub(r"^(?:Action|Task|TODO|Action Item|\d+\.|\- \[ \])[:\s]*", "", l_str, flags=re.IGNORECASE).strip())
                elif re.match(r"^(?:Agenda|Discuss|Topic)[:\s]", l_str, re.IGNORECASE):
                    agenda_items.append(l_str)

        return {
            "summary": summary,
            "organizer": organizer,
            "start_time": dtstart,
            "end_time": dtend,
            "location": location,
            "attendees": attendees,
            "description": description,
            "agenda": "\n".join(agenda_items) if agenda_items else None,
            "action_items": action_items,
        }

    def _parse_supported_attachment(self, payload: bytes, filename: str) -> dict[str, Any] | None:
        """Parse text-based attachments (CSV, XLSX, PDF text, TXT). Strictly NO OCR / NO images."""
        fn = filename.lower()
        if fn.endswith((".csv", ".tsv")):
            try:
                text = payload.decode("utf-8", errors="replace")
                reader = csv.reader(io.StringIO(text))
                rows = list(reader)
                if rows:
                    return {
                        "type": "CSV",
                        "headers": rows[0],
                        "row_count": len(rows) - 1,
                        "tables": [{"headers": rows[0], "rows": rows[1:50]}],
                    }
            except Exception as e:
                return {"type": "CSV", "error": str(e)}

        elif fn.endswith((".xlsx", ".xls")):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(payload), data_only=True)
                sheet_tables = []
                for sheet in wb.sheetnames[:3]:
                    ws = wb[sheet]
                    rows = [[str(cell.value) if cell.value is not None else "" for cell in r] for r in ws.iter_rows(max_row=50)]
                    if rows and any(any(c for c in r) for r in rows):
                        sheet_tables.append({"sheet": sheet, "headers": rows[0], "rows": rows[1:]})
                return {
                    "type": "EXCEL",
                    "sheets": wb.sheetnames,
                    "tables": sheet_tables,
                }
            except Exception as e:
                return {"type": "EXCEL", "error": str(e)}

        elif fn.endswith(".pdf"):
            try:
                import pdfplumber
                pages_text = []
                extracted_tables = []
                with pdfplumber.open(io.BytesIO(payload)) as pdf:
                    for i, page in enumerate(pdf.pages[:10]):
                        txt = page.extract_text()
                        if txt:
                            pages_text.append(txt)
                        tabs = page.extract_tables()
                        for t in tabs:
                            if t and len(t) >= 2:
                                extracted_tables.append({"page": i + 1, "headers": t[0], "rows": t[1:]})

                full_text = "\n".join(pages_text).strip()
                if not full_text:
                    return {
                        "type": "PDF",
                        "is_scanned_unsupported": True,
                        "text": "Scanned image document. OCR and image processing are strictly excluded per system requirements.",
                    }
                return {
                    "type": "PDF",
                    "page_count": len(pdf.pages),
                    "extracted_text": full_text[:4000],
                    "tables": extracted_tables,
                }
            except Exception as e:
                return {"type": "PDF", "error": str(e)}

        elif fn.endswith((".txt", ".log")):
            try:
                text = payload.decode("utf-8", errors="replace")
                return {"type": "TEXT", "content": text[:3000]}
            except Exception:
                pass

        return None

    def parse_zip_eml_archive(self, zip_bytes: bytes) -> list[RawMessage]:
        """Extract all .eml files from a ZIP archive and parse them."""
        parsed_messages: list[RawMessage] = []
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for member in zf.namelist():
                if member.lower().endswith((".eml", ".msg")) and not member.startswith("__MACOSX"):
                    try:
                        eml_data = zf.read(member)
                        msg_obj = email_lib.message_from_bytes(eml_data, policy=email_lib.policy.default)
                        raw = self._parse_eml_message(msg_obj, member)
                        raw.source_type = "ZIP"
                        parsed_messages.append(raw)
                    except Exception as e:
                        logger.warning("Failed to parse member in ZIP", member=member, error=str(e))
        return parsed_messages
