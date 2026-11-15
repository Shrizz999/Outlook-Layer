"""
Balbird Intelligence — Security & Authentication Utilities
Argon2id/Bcrypt password hashing, validation, session token generation,
and in-memory rate limiting.
"""
from __future__ import annotations

import re
import secrets
import time
from typing import Tuple

import bcrypt

from app.repositories.store import get_store


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with random salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, str | None]:
    """
    Validate that password meets security complexity requirements:
    - At least 8 characters long
    - Contains at least one letter
    - Contains at least one numeric digit
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    return True, None


def generate_session_token() -> str:
    """Generate a high-entropy URL-safe session token."""
    return secrets.token_urlsafe(32)


# Rate Limiting
def is_rate_limited(key: str, max_attempts: int = 5, window_seconds: int = 300) -> bool:
    """Check if the given key has exceeded failed attempts in the time window."""
    store = get_store()
    now = time.time()
    history = store.login_rate_limits.get(key, [])
    # Filter attempts within the sliding window
    valid_attempts = [t for t in history if now - t < window_seconds]
    store.login_rate_limits[key] = valid_attempts
    return len(valid_attempts) >= max_attempts


def record_failed_attempt(key: str) -> None:
    """Record a failed attempt timestamp for a key."""
    store = get_store()
    now = time.time()
    if key not in store.login_rate_limits:
        store.login_rate_limits[key] = []
    store.login_rate_limits[key].append(now)


def clear_rate_limit(key: str) -> None:
    """Clear failed attempt history upon successful login."""
    store = get_store()
    if key in store.login_rate_limits:
        del store.login_rate_limits[key]
