"""
Create Initial Administrator Script for Balbird Intelligence.
Usage:
    uv run --project backend python backend/scripts/create_initial_admin.py \
        --email admin@balbird.com \
        --password AdminPassword123 \
        --name "System Administrator" \
        --dept MANAGEMENT
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.security import hash_password, validate_password_strength
from app.repositories.auth_repo import AuthRepository
from app.repositories.master_data_repo import MasterDataRepository
from app.schemas.master_data import DepartmentCreate, EmployeeCreate


async def create_initial_admin(
    email: str,
    password: str,
    full_name: str,
    department: str = "MANAGEMENT",
) -> None:
    auth_repo = AuthRepository()
    master_repo = MasterDataRepository()

    # Validate password
    is_strong, reason = validate_password_strength(password)
    if not is_strong:
        print(f"Error: Password is too weak: {reason}")
        sys.exit(1)

    # Check if user already exists
    existing = await auth_repo.get_account_by_email(email)
    if existing:
        print(f"User account '{email}' already exists. Updating role to SYSADMIN and status to active.")
        from uuid import UUID
        await auth_repo.update_account(
            UUID(str(existing["id"])),
            {
                "approved_position": "SYSADMIN",
                "account_status": "active",
                "password_hash": hash_password(password),
            },
        )
        print("Initial administrator updated successfully.")
        return

    # Ensure department exists
    dept = await master_repo.get_department(department)
    if not dept:
        print(f"Department '{department}' not found. Creating department...")
        dept = await master_repo.create_department(
            DepartmentCreate(code=department.upper(), name="Executive Management")
        )

    # Ensure employee record exists
    employees = await master_repo.list_employees()
    linked_emp = None
    for emp in employees:
        if emp.email and emp.email.lower() == email.lower():
            linked_emp = emp
            break

    if not linked_emp:
        max_num = max([e.employee_number or 1000 for e in employees] or [1000])
        linked_emp = await master_repo.create_employee(
            EmployeeCreate(
                name=full_name,
                department=department.upper(),
                email=email.lower(),
                employee_number=max_num + 1,
                designation="System Administrator",
                role="SYSADMIN",
                is_active=True,
            )
        )

    # Create administrator account
    pwd_hash = hash_password(password)
    account = await auth_repo.create_account(
        {
            "employee_id": linked_emp.id,
            "email": email.lower(),
            "password_hash": pwd_hash,
            "full_name": full_name,
            "department": department.upper(),
            "requested_position": "SYSADMIN",
            "approved_position": "SYSADMIN",
            "account_status": "active",
        }
    )

    await auth_repo.create_audit_log(
        user_id=account.id,
        action="INITIAL_ADMIN_CREATED",
        old_value=None,
        new_value={"email": account.email, "role": "SYSADMIN"},
        performed_by="CLI_SCRIPT",
    )

    print("\n=======================================================")
    print("SUCCESS: Initial Administrator account created!")
    print(f"Email:             {account.email}")
    print(f"Full Name:         {account.full_name}")
    print(f"Department:        {account.department}")
    print(f"Approved Position: {account.approved_position}")
    print(f"Account Status:    {account.account_status}")
    print(f"Employee ID:       {account.employee_id}")
    print("=======================================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create initial administrator for Balbird Intelligence")
    parser.add_argument("--email", default="admin@balbird.com", help="Admin email address")
    parser.add_argument("--password", default="AdminSecure2026!", help="Admin password")
    parser.add_argument("--name", default="System Administrator", help="Admin full name")
    parser.add_argument("--dept", default="MANAGEMENT", help="Admin department code")

    args = parser.parse_args()
    asyncio.run(
        create_initial_admin(
            email=args.email,
            password=args.password,
            full_name=args.name,
            department=args.dept,
        )
    )


if __name__ == "__main__":
    main()
