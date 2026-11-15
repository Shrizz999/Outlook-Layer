"""
FastAPI Dependencies for Authentication and Role-Based Access Control (RBAC).
Extracts session tokens from Authorization Bearer headers or HttpOnly cookies,
validates user accounts, and enforces server-side role permissions.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from app.schemas.auth import UserAccountRead
from app.services.auth.auth_service import AuthService

auth_service = AuthService()


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    session_token: str | None = Cookie(None),
) -> UserAccountRead:
    """
    Extract session token from Authorization: Bearer <token> or cookie session_token.
    Validates token and returns authenticated UserAccountRead.
    Raises 401 if missing, invalid, or expired.
    Raises 403 if suspended.
    """
    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]

    if not token and session_token:
        token = session_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await auth_service.get_current_user_from_token(token)


async def get_optional_user(
    request: Request,
    authorization: str | None = Header(None),
    session_token: str | None = Cookie(None),
) -> UserAccountRead | None:
    """
    Optional user extraction. If a valid token is provided, returns UserAccountRead;
    otherwise returns None without raising an exception.
    """
    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]

    if not token and session_token:
        token = session_token

    if not token:
        return None

    try:
        return await auth_service.get_current_user_from_token(token)
    except Exception:
        return None


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory checking that user.approved_position is in allowed_roles."""

    async def _role_checker(user: UserAccountRead = Depends(get_current_user)) -> UserAccountRead:
        if user.approved_position.upper() not in [r.upper() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Position '{user.approved_position}' lacks authorization for this resource.",
            )
        return user

    return _role_checker


# Role helper dependencies
require_admin = require_roles("SYSADMIN")
require_management_or_above = require_roles("SYSADMIN", "MANAGEMENT")
require_hod_or_above = require_roles("SYSADMIN", "MANAGEMENT", "DEPT_HEAD")
