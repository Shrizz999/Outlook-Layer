"""Email Preprocessing Service.

Cleans email content, separates authored message body from quoted history,
detects disclaimers and signatures, and generates SHA-256 content hashes.
Preserves original body untouched for audit and legal provenance.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass
class PreprocessedEmail:
    cleaned_body: str
    quoted_history: str | None
    signature: str | None
    body_hash: str
    is_automated: bool


class EmailPreprocessor:
    # Common quoted reply boundary markers
    REPLY_MARKERS = [
        re.compile(r"^-+\s*Original Message\s*-+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^From:\s*.+?\nSent:\s*.+?", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^On\s+.+?wrote:\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"_{10,}", re.MULTILINE),  # Outlook separator line
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
        re.compile(r"^(?:Kind regards|Best regards|Regards|Thanks and regards|Thanks,|Sincerely),?\s*$", re.IGNORECASE | re.MULTILINE),
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

        # 4. Split quoted history
        cleaned_body = text
        quoted_history = None

        for marker in self.REPLY_MARKERS:
            match = marker.search(text)
            if match:
                idx = match.start()
                cleaned_body = text[:idx].strip()
                quoted_history = text[idx:].strip()
                break

        # 5. Extract signature if signoff marker found
        signature = None
        for sm in self.SIGNOFF_MARKERS:
            match = sm.search(cleaned_body)
            if match:
                sig_idx = match.start()
                signature = cleaned_body[sig_idx:].strip()
                # Keep signature in cleaned_body for context, but note it
                break

        return PreprocessedEmail(
            cleaned_body=cleaned_body,
            quoted_history=quoted_history,
            signature=signature,
            body_hash=body_hash,
            is_automated=is_automated,
        )

    def _is_automated_sender(self, sender: str | None) -> bool:
        if not sender:
            return False
        sender_lower = sender.lower()
        return any(ind in sender_lower for ind in self.AUTOMATED_INDICATORS)
