"""
Balbird Intelligence — Authentication and Role-Based Access Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    department: str = Field(..., min_length=1)
    position: str = Field(..., min_length=1)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserAccountRead(BaseModel):
    id: UUID
    employee_id: UUID | None = None
    email: str
    full_name: str
    department: str
    requested_position: str
    approved_position: str
    account_status: str
    rejection_reason: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class SessionResponse(BaseModel):
    session_token: str
    user: UserAccountRead
    expires_at: datetime


class RoleRequestRead(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str | None = None
    user_name: str | None = None
    requested_position: str
    requested_department: str
    approval_status: str
    reviewed_by: str | None = None
    review_reason: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None


class RoleReviewRequest(BaseModel):
    approval_status: Literal["APPROVED", "REJECTED"]
    reason: str | None = None


class AdminUserUpdateRequest(BaseModel):
    approved_position: str | None = None
    department: str | None = None
    account_status: Literal["active", "pending_approval", "rejected", "suspended"] | None = None
    employee_id: UUID | None = None
    rejection_reason: str | None = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class UserAuditLogRead(BaseModel):
    id: UUID
    user_id: UUID | None = None
    action: str
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    performed_by: str
    created_at: datetime
