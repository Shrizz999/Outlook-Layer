"""
Token Cache and Secret Encryption at Rest.
Uses Fernet symmetric authenticated encryption (AES-128-CBC + HMAC-SHA256).
Zero plaintext tokens ever written to database or logs.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _get_fernet_suite() -> Fernet:
    """
    Get or derive a 32-byte urlsafe base64 Fernet encryption key.
    Prioritizes TOKEN_ENCRYPTION_KEY if set, otherwise derives deterministically
    from APP_SECRET_KEY using PBKDF2HMAC.
    """
    settings = get_settings()
    configured_key = settings.token_encryption_key.strip() if hasattr(settings, "token_encryption_key") else ""

    if configured_key:
        try:
            # Validate if it is already a valid 32-byte base64 Fernet key
            key_bytes = base64.urlsafe_b64decode(configured_key.encode("utf-8"))
            if len(key_bytes) == 32:
                return Fernet(configured_key.encode("utf-8"))
        except Exception:
            logger.warning("Configured TOKEN_ENCRYPTION_KEY invalid format; deriving from key string")

    # Fallback / deterministic key derivation using PBKDF2 from secret
    secret = (configured_key or settings.app_secret_key or "balbird-intelligence-default-secret").encode("utf-8")
    salt = b"balbird_outlook_token_cache_salt_v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    derived_key = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(derived_key)


def encrypt_token_cache(plaintext: str) -> str:
    """Encrypt MSAL serialized token cache string. Returns base64 ciphertext string."""
    if not plaintext:
        return ""
    fernet = _get_fernet_suite()
    encrypted_bytes = fernet.encrypt(plaintext.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token_cache(ciphertext: str) -> str:
    """Decrypt encrypted token cache string. Returns plaintext JSON string."""
    if not ciphertext:
        return ""
    fernet = _get_fernet_suite()
    decrypted_bytes = fernet.decrypt(ciphertext.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")
