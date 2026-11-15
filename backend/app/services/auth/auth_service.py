"""
Balbird Intelligence — Authentication & Role-Based Access Service
Enforces registration rules, role approval workflows, employee linking,
session management, rate limiting, and administrative actions.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from fastapi import HTTPException, status

from app.core.security import (
    clear_rate_limit,
    generate_session_token,
    hash_password,
    is_rate_limited,
    record_failed_attempt,
    validate_password_strength,
    verify_password,
)
from app.repositories.auth_repo import AuthRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.schemas.auth import (
    AdminPasswordResetRequest,
    AdminUserUpdateRequest,
    RoleRequestRead,
    RoleReviewRequest,
    SessionResponse,
    UserAccountRead,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.schemas.master_data import DepartmentHODCreate, EmployeeCreate

logger = structlog.get_logger(__name__)

# Position Normalization Map
POSITION_MAP = {
    "employee": "EMPLOYEE",
    "staff": "EMPLOYEE",
    "hod": "DEPT_HEAD",
    "dept_head": "DEPT_HEAD",
    "department head": "DEPT_HEAD",
    "head of department": "DEPT_HEAD",
    "manager": "MANAGEMENT",
    "management": "MANAGEMENT",
    "admin": "SYSADMIN",
    "administrator": "SYSADMIN",
    "sysadmin": "SYSADMIN",
}


class AuthService:
    def __init__(
        self,
        auth_repo: AuthRepository | None = None,
        master_repo: MasterDataRepository | None = None,
    ) -> None:
        self.auth_repo = auth_repo or AuthRepository()
        self.master_repo = master_repo or MasterDataRepository()

    def normalize_position(self, pos: str) -> str:
        key = pos.strip().lower()
        if key in POSITION_MAP:
            return POSITION_MAP[key]
        raise ValueError(f"Invalid position '{pos}'. Must be Employee, HOD, Manager, or Administrator.")

    async def register(self, req: UserRegisterRequest, ip_address: str | None = None) -> UserAccountRead:
        """Register a new user account with employee linking and role request routing."""
        # 1. Validation: password match
        if req.password != req.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password and confirmation password do not match",
            )

        # 2. Validation: password complexity
        is_strong, reason = validate_password_strength(req.password)
        if not is_strong:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

        # 3. Validation: Unique email
        existing_account = await self.auth_repo.get_account_by_email(req.email)
        if existing_account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An account with email '{req.email}' already exists",
            )

        # 4. Validation: Department must exist in system
        departments = await self.master_repo.list_departments()
        dept_match = None
        for d in departments:
            if (
                d.code.upper() == req.department.upper()
                or d.name.lower() == req.department.lower()
                or d.code.upper() in req.department.upper()
            ):
                dept_match = d
                break

        if not dept_match:
            available = [f"{d.name} ({d.code})" for d in departments]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid department '{req.department}'. Available: {', '.join(available)}",
            )
        resolved_department_code = dept_match.code.upper()

        # 5. Position parsing and authorization rules
        try:
            requested_pos = self.normalize_position(req.position)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # Role assignment rules:
        # Employee: active immediately with EMPLOYEE permissions.
        # HOD, Manager, Admin: approved_position = EMPLOYEE, account_status = pending_approval
        if requested_pos == "EMPLOYEE":
            approved_pos = "EMPLOYEE"
            account_status_val = "active"
            needs_approval = False
        else:
            # HOD, Manager, Administrator require administrative approval!
            approved_pos = "EMPLOYEE"  # Safe default until approved
            account_status_val = "pending_approval"
            needs_approval = True

        # 6. Employee Record Linking / Creation
        # Check if an employee with the same email already exists
        employees = await self.master_repo.list_employees()
        linked_employee = None
        for emp in employees:
            if emp.email and emp.email.strip().lower() == req.email.strip().lower():
                linked_employee = emp
                break

        if not linked_employee:
            # Determine unique employee number
            max_num = max([e.employee_number or 1000 for e in employees] or [1000])
            next_emp_num = max_num + 1

            new_emp = await self.master_repo.create_employee(
                EmployeeCreate(
                    name=req.full_name.strip(),
                    department=resolved_department_code,
                    email=req.email.strip().lower(),
                    employee_number=next_emp_num,
                    designation=f"{req.position.title()} (Staff)" if requested_pos != "EMPLOYEE" else "Staff Member",
                    role=approved_pos,
                    is_active=True,
                )
            )
            linked_employee = new_emp

        # 7. Create User Account with hashed password
        pwd_hash = hash_password(req.password)
        account = await self.auth_repo.create_account(
            {
                "employee_id": linked_employee.id,
                "email": req.email,
                "password_hash": pwd_hash,
                "full_name": req.full_name,
                "department": resolved_department_code,
                "requested_position": requested_pos,
                "approved_position": approved_pos,
                "account_status": account_status_val,
            }
        )

        # 8. Create Role Request if HOD/Manager/Admin requested
        if needs_approval:
            await self.auth_repo.create_role_request(
                user_id=account.id,
                requested_position=requested_pos,
                requested_department=resolved_department_code,
            )

        # 9. Audit Log
        await self.auth_repo.create_audit_log(
            user_id=account.id,
            action="USER_REGISTERED",
            old_value=None,
            new_value={
                "email": account.email,
                "department": resolved_department_code,
                "requested_position": requested_pos,
                "approved_position": approved_pos,
                "account_status": account_status_val,
                "employee_id": str(linked_employee.id),
            },
            performed_by=req.email,
        )

        return account

    async def login(
        self,
        req: UserLoginRequest,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SessionResponse:
        """Authenticate user, verify password, enforce rate limiting & status, create session."""
        rate_key = f"{ip_address or 'anon'}:{req.email.strip().lower()}"

        # 1. Rate Limiting Check
        if is_rate_limited(rate_key, max_attempts=5, window_seconds=300):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again in 5 minutes.",
            )

        # 2. Account Lookup
        account = await self.auth_repo.get_account_by_email(req.email)
        if not account:
            record_failed_attempt(rate_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # 3. Check Account Status
        acct_status = account.get("account_status", "active")
        if acct_status == "suspended":
            record_failed_attempt(rate_key)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended. Please contact your administrator.",
            )
        if acct_status == "rejected":
            record_failed_attempt(rate_key)
            reason = account.get("rejection_reason") or "Contact administrator"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account registration was rejected: {reason}",
            )

        # 4. Verify Password
        if not verify_password(req.password, account["password_hash"]):
            record_failed_attempt(rate_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Clear failed login attempts upon successful password verification
        clear_rate_limit(rate_key)

        # 5. Create Secure Session (24 hour expiration)
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=24)
        session_token = generate_session_token()

        await self.auth_repo.create_session(
            user_id=UUID(str(account["id"])),
            session_token=session_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Update last_login_at
        await self.auth_repo.update_account(
            UUID(str(account["id"])),
            {"last_login_at": now},
        )

        user_read = await self.auth_repo.get_account_by_id(UUID(str(account["id"])))
        if not user_read:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load user profile")

        return SessionResponse(
            session_token=session_token,
            user=user_read,
            expires_at=expires_at,
        )

    async def logout(self, session_token: str) -> bool:
        """Invalidate the session."""
        return await self.auth_repo.delete_session(session_token)

    async def get_current_user_from_token(self, token: str) -> UserAccountRead:
        """Validate session token and return user profile."""
        sess = await self.auth_repo.get_session(token)
        if not sess:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token",
            )

        # Expiry check
        exp = sess.get("expires_at")
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp and exp < datetime.now(UTC):
            await self.auth_repo.delete_session(token)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again.",
            )

        user = await self.auth_repo.get_account_by_id(UUID(str(sess["user_id"])))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if user.account_status == "suspended":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended")

        return user

    # --- Role Approval Workflow ---

    async def review_role_request(
        self,
        request_id: UUID,
        review: RoleReviewRequest,
        admin_user: UserAccountRead,
    ) -> RoleRequestRead:
        """Admin approves or rejects a role request with full department and HOD checks."""
        req = await self.auth_repo.get_role_request(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role request not found")

        if req.approval_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role request is already {req.approval_status}",
            )

        now = datetime.now(UTC)
        user = await self.auth_repo.get_account_by_id(req.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user account not found")

        old_user_state = user.model_dump()

        if review.approval_status == "APPROVED":
            target_role = req.requested_position

            # Specific check for HOD:
            if target_role == "DEPT_HEAD":
                # Ensure the employee belongs to the department they want to manage
                if not user.employee_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="User must be linked to an employee record before becoming HOD",
                    )
                emp = await self.master_repo.get_employee_by_id(user.employee_id)
                if not emp:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Linked employee not found")

                # Verify employee department matches requested department
                req_dept = req.requested_department.upper().strip()
                emp_dept = emp.department.upper().strip()
                if emp_dept != req_dept and req_dept not in emp_dept:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Employee '{emp.name}' belongs to department '{emp.department}', not '{req_dept}'. Transfer employee first.",
                    )

                # Assign HOD using existing department-HOD mapping
                try:
                    await self.master_repo.assign_department_hod(
                        dept_code_or_id=req_dept,
                        data=DepartmentHODCreate(
                            employee_id=user.employee_id,
                            assigned_by=admin_user.full_name,
                            notes=review.reason or "Approved via role request",
                        ),
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

            # Update user account
            await self.auth_repo.update_account(
                user.id,
                {
                    "approved_position": target_role,
                    "account_status": "active",
                    "rejection_reason": None,
                },
            )

            # Update role request
            updated_req = await self.auth_repo.update_role_request(
                request_id,
                {
                    "approval_status": "APPROVED",
                    "reviewed_by": admin_user.full_name,
                    "review_reason": review.reason or "Approved by Administrator",
                    "reviewed_at": now,
                },
            )

            # Audit log
            await self.auth_repo.create_audit_log(
                user_id=user.id,
                action="ROLE_REQUEST_APPROVED",
                old_value=old_user_state,
                new_value={
                    "approved_position": target_role,
                    "account_status": "active",
                    "approved_by": admin_user.full_name,
                },
                performed_by=admin_user.full_name,
            )
            return updated_req

        else:
            # REJECTED
            # User remains as approved_position (EMPLOYEE) with status active
            await self.auth_repo.update_account(
                user.id,
                {
                    "account_status": "active",
                    "rejection_reason": review.reason or "Role request was declined by administrator",
                },
            )

            updated_req = await self.auth_repo.update_role_request(
                request_id,
                {
                    "approval_status": "REJECTED",
                    "reviewed_by": admin_user.full_name,
                    "review_reason": review.reason or "Declined by administrator",
                    "reviewed_at": now,
                },
            )

            await self.auth_repo.create_audit_log(
                user_id=user.id,
                action="ROLE_REQUEST_REJECTED",
                old_value=old_user_state,
                new_value={
                    "rejection_reason": review.reason,
                    "rejected_by": admin_user.full_name,
                },
                performed_by=admin_user.full_name,
            )
            return updated_req

    # --- Admin User Management ---

    async def update_user_account_by_admin(
        self,
        target_user_id: UUID,
        req: AdminUserUpdateRequest,
        admin_user: UserAccountRead,
    ) -> UserAccountRead:
        """Admin updates user approved position, department, status, or links employee."""
        user = await self.auth_repo.get_account_by_id(target_user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")

        old_state = user.model_dump()
        updates: dict[str, Any] = {}

        # 1. Department change
        if req.department and req.department.upper() != user.department.upper():
            # If user was HOD of old department, revoke HOD
            if user.approved_position == "DEPT_HEAD":
                await self.master_repo.remove_department_hod(
                    user.department,
                    reason=f"User transferred to {req.department.upper()} by {admin_user.full_name}",
                )
                updates["approved_position"] = "EMPLOYEE"

            updates["department"] = req.department.upper()
            if user.employee_id:
                from app.schemas.master_data import EmployeeUpdate
                await self.master_repo.update_employee(
                    user.employee_id,
                    EmployeeUpdate(department=req.department.upper()),
                )

        # 2. Position change
        if req.approved_position and req.approved_position != user.approved_position:
            norm_pos = self.normalize_position(req.approved_position)
            if norm_pos == "DEPT_HEAD":
                dept = updates.get("department", user.department)
                if not user.employee_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link employee before making HOD")
                await self.master_repo.assign_department_hod(
                    dept_code_or_id=dept,
                    data=DepartmentHODCreate(
                        employee_id=user.employee_id,
                        assigned_by=admin_user.full_name,
                        notes="Assigned by administrator",
                    ),
                )
            elif user.approved_position == "DEPT_HEAD" and norm_pos != "DEPT_HEAD":
                await self.master_repo.remove_department_hod(
                    user.department,
                    reason=f"Position changed to {norm_pos} by {admin_user.full_name}",
                )
            updates["approved_position"] = norm_pos

        # 3. Account status change
        if req.account_status:
            updates["account_status"] = req.account_status
            if req.account_status == "suspended":
                # Invalidate active sessions
                await self.auth_repo.delete_user_sessions(target_user_id)
            if req.rejection_reason is not None:
                updates["rejection_reason"] = req.rejection_reason

        # 4. Link Employee ID
        if req.employee_id:
            emp = await self.master_repo.get_employee_by_id(req.employee_id)
            if not emp:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
            updates["employee_id"] = req.employee_id
            updates["department"] = emp.department.upper()

        updated_user = await self.auth_repo.update_account(target_user_id, updates)

        await self.auth_repo.create_audit_log(
            user_id=target_user_id,
            action="ADMIN_USER_UPDATED",
            old_value=old_state,
            new_value=updated_user.model_dump(),
            performed_by=admin_user.full_name,
        )

        return updated_user

    async def admin_reset_password(
        self,
        target_user_id: UUID,
        req: AdminPasswordResetRequest,
        admin_user: UserAccountRead,
    ) -> dict[str, str]:
        """Admin resets a user's password securely."""
        user = await self.auth_repo.get_account_by_id(target_user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")

        is_strong, reason = validate_password_strength(req.new_password)
        if not is_strong:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

        pwd_hash = hash_password(req.new_password)
        await self.auth_repo.update_account(target_user_id, {"password_hash": pwd_hash})
        # Invalidate active sessions
        await self.auth_repo.delete_user_sessions(target_user_id)

        await self.auth_repo.create_audit_log(
            user_id=target_user_id,
            action="ADMIN_PASSWORD_RESET",
            old_value=None,
            new_value={"reset_by": admin_user.full_name},
            performed_by=admin_user.full_name,
        )

        return {"status": "success", "message": f"Password reset successfully for {user.email}"}
