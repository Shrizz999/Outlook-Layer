"""Email Preprocessing Service.

Cleans email content, separates authored message body from quoted history,
detects disclaimers and signatures, and generates SHA-256 content hashes.
Preserves original body untouched for audit and legal provenance.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class PreprocessedEmail:
    cleaned_body: str
    quoted_history: str | None
    signature: str | None
    body_hash: str
    is_automated: bool
    is_forwarded: bool = False
    forwarded_from: str | None = None
    signature_name_hint: str | None = None
    extracted_tables: list[dict] = field(default_factory=list)


class EmailPreprocessor:
    # Common quoted reply boundary markers
    REPLY_MARKERS = [
        re.compile(r"^-+\s*Original Message\s*-+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^From:\s*.+?\nSent:\s*.+?", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^On\s+.+?wrote:\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"_{10,}", re.MULTILINE),  # Outlook separator line
    ]

    # Forward markers
    FORWARD_MARKERS = [
        re.compile(r"^-+\s*Forwarded message\s*-+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^Begin forwarded message:\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^-+\s*Forwarded by\s*.+?-+", re.IGNORECASE | re.MULTILINE),
    ]

    # Automated sender signatures
    AUTOMATED_INDICATORS = [
        "do-not-reply@",
        "noreply@",
        "no-reply@",
        "mailer-daemon@",
        "notifications@",
    ]

    # Sign-off markers
    SIGNOFF_MARKERS = [
        re.compile(r"^(?:Kind regards|Best regards|Regards|Thanks and regards|Thanks,|Sincerely|Warm regards),?\s*$", re.IGNORECASE | re.MULTILINE),
    ]

    def preprocess(self, raw_body: str | None, sender_address: str | None = None) -> PreprocessedEmail:
        if not raw_body:
            return PreprocessedEmail(
                cleaned_body="",
                quoted_history=None,
                signature=None,
                body_hash=hashlib.sha256(b"").hexdigest(),
                is_automated=self._is_automated_sender(sender_address),
            )

        # 1. Normalize line endings
        text = raw_body.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Compute canonical hash
        body_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # 3. Detect automated notification
        is_automated = self._is_automated_sender(sender_address) or "this is an automated message" in text.lower()

        # 4. Check for forwarded message structure
        is_forwarded = False
        forwarded_from = None
        for fm in self.FORWARD_MARKERS:
            fmatch = fm.search(text)
            if fmatch:
                is_forwarded = True
                fwd_block = text[fmatch.start():]
                from_match = re.search(r"From:\s*([^\n\r]+)", fwd_block, re.IGNORECASE)
                if from_match:
                    forwarded_from = from_match.group(1).strip()
                break

        # 5. Split quoted history
        cleaned_body = text
        quoted_history = None

        for marker in self.REPLY_MARKERS:
            match = marker.search(text)
            if match:
                idx = match.start()
                cleaned_body = text[:idx].strip()
                quoted_history = text[idx:].strip()
                break

        # 6. Extract signature and name hint if signoff marker found
        signature = None
        signature_name_hint = None
        for sm in self.SIGNOFF_MARKERS:
            match = sm.search(cleaned_body)
            if match:
                sig_idx = match.start()
                signature = cleaned_body[sig_idx:].strip()
                # Inspect lines right after signoff marker to find person name
                after_signoff = cleaned_body[match.end():].strip().split("\n")
                if after_signoff:
                    first_line = after_signoff[0].strip()
                    # Clean punctuation or title
                    first_line = re.sub(r"[,\-_|].*", "", first_line).strip()
                    if first_line and len(first_line) < 50 and not first_line.lower().startswith(("http", "tel", "email", "phone", "sent from")):
                        signature_name_hint = first_line
                break

        # 7. Extract tabular structures from cleaned body
        extracted_tables = self._extract_tables(cleaned_body)

        return PreprocessedEmail(
            cleaned_body=cleaned_body,
            quoted_history=quoted_history,
            signature=signature,
            body_hash=body_hash,
            is_automated=is_automated,
            is_forwarded=is_forwarded,
            forwarded_from=forwarded_from,
            signature_name_hint=signature_name_hint,
            extracted_tables=extracted_tables,
        )

    def _extract_tables(self, text: str) -> list[dict]:
        """Extract markdown tables and columnar lines from email body."""
        tables = []
        lines = [line.strip() for line in text.split("\n")]
        current_table_lines = []

        for line in lines:
            if "|" in line:
                current_table_lines.append(line)
            else:
                if len(current_table_lines) >= 2:
                    tables.append(self._parse_pipe_table(current_table_lines))
                current_table_lines = []

        if len(current_table_lines) >= 2:
            tables.append(self._parse_pipe_table(current_table_lines))

        return tables

    def _parse_pipe_table(self, lines: list[str]) -> dict:
        headers = [c.strip() for c in lines[0].strip("|").split("|")]
        rows = []
        for line in lines[1:]:
            if re.match(r"^\|?[-:\s|]+\|?$", line):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            if cols:
                rows.append(cols)
        return {"headers": headers, "rows": rows}

    def _is_automated_sender(self, sender: str | None) -> bool:
        if not sender:
            return False
        sender_lower = sender.lower()
        return any(ind in sender_lower for ind in self.AUTOMATED_INDICATORS)
