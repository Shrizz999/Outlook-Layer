"""
Authentication and RBAC API Routes for Balbird Intelligence.
Provides registration, login, logout, profile discovery, role approval,
and administrative user management.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from app.api.deps import get_current_user, require_admin
from app.schemas.auth import (
    AdminPasswordResetRequest,
    AdminUserUpdateRequest,
    RoleRequestRead,
    RoleReviewRequest,
    SessionResponse,
    UserAccountRead,
    UserAuditLogRead,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.services.auth.auth_service import AuthService

router = APIRouter()
service = AuthService()


@router.post("/register", response_model=UserAccountRead, status_code=status.HTTP_201_CREATED)
async def register(req: UserRegisterRequest, request: Request) -> UserAccountRead:
    """Register a new user account with employee linking and role request routing."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    return await service.register(req, ip_address=client_ip)


@router.post("/login", response_model=SessionResponse)
async def login(req: UserLoginRequest, request: Request, response: Response) -> SessionResponse:
    """Authenticate with email and password, returning a secure session."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent")

    sess = await service.login(req, ip_address=client_ip, user_agent=user_agent)

    # Set secure HttpOnly, SameSite cookie
    response.set_cookie(
        key="session_token",
        value=sess.session_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Allow http in development
        expires=int(sess.expires_at.timestamp()),
    )
    return sess


@router.post("/logout")
async def logout(
    response: Response,
    authorization: str | None = Header(None),
    user: UserAccountRead = Depends(get_current_user),
) -> dict[str, str]:
    """Invalidate session and clear cookies."""
    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]

    if token:
        await service.logout(token)

    response.delete_cookie("session_token")
    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me", response_model=UserAccountRead)
async def get_my_profile(user: UserAccountRead = Depends(get_current_user)) -> UserAccountRead:
    """Return currently authenticated user account profile."""
    return user


# --- Admin User Management Routes (require_admin) ---

@router.get("/admin/users", response_model=list[UserAccountRead])
async def list_users(
    department: str | None = Query(None),
    position: str | None = Query(None),
    account_status: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: UserAccountRead = Depends(require_admin),
) -> list[UserAccountRead]:
    """Admin: List all registered accounts with filtering."""
    return await service.auth_repo.list_accounts(
        department=department,
        position=position,
        account_status=account_status,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.patch("/admin/users/{user_id}", response_model=UserAccountRead)
async def update_user(
    user_id: UUID,
    req: AdminUserUpdateRequest,
    admin: UserAccountRead = Depends(require_admin),
) -> UserAccountRead:
    """Admin: Update user position, department, status, or employee link."""
    return await service.update_user_account_by_admin(user_id, req, admin)


@router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: UUID,
    req: AdminPasswordResetRequest,
    admin: UserAccountRead = Depends(require_admin),
) -> dict[str, str]:
    """Admin: Reset user password and invalidate active sessions."""
    return await service.admin_reset_password(user_id, req, admin)


@router.get("/admin/role-requests", response_model=list[RoleRequestRead])
async def list_role_requests(
    approval_status: str | None = Query(None),
    admin: UserAccountRead = Depends(require_admin),
) -> list[RoleRequestRead]:
    """Admin: List role approval requests."""
    return await service.auth_repo.list_role_requests(status=approval_status)


@router.post("/admin/role-requests/{request_id}/review", response_model=RoleRequestRead)
async def review_role_request(
    request_id: UUID,
    review: RoleReviewRequest,
    admin: UserAccountRead = Depends(require_admin),
) -> RoleRequestRead:
    """Admin: Approve or reject a role approval request."""
    return await service.review_role_request(request_id, review, admin)


@router.get("/admin/audit-logs", response_model=list[UserAuditLogRead])
async def list_audit_logs(
    user_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    admin: UserAccountRead = Depends(require_admin),
) -> list[UserAuditLogRead]:
    """Admin: View system audit trail of administrative and role changes."""
    return await service.auth_repo.list_audit_logs(user_id=user_id, limit=limit)
