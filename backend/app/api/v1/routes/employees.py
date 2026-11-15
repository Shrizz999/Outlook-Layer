"""Employee Management API Routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_optional_user
from app.repositories.master_data_repo import MasterDataRepository
from app.schemas.auth import UserAccountRead
from app.schemas.master_data import EmployeeCreate, EmployeeRead, EmployeeUpdate

router = APIRouter()
repo = MasterDataRepository()


@router.get("", response_model=list[EmployeeRead])
async def list_employees(
    department: str | None = Query(None, description="Filter by department code"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    search: str | None = Query(None, description="Search by name, email, or designation"),
    user: UserAccountRead | None = Depends(get_optional_user),
) -> list[EmployeeRead]:
    """
    List employees with server-side role scoping.
    - Employee: Blocked from browsing company-wide employee lists.
    - HOD: Scoped strictly to their own department.
    - Management / SysAdmin: Full directory visibility.
    """
    if user:
        if user.approved_position == "EMPLOYEE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Employees are not authorized to view the employee directory.",
            )
        elif user.approved_position == "DEPT_HEAD":
            # Force department filter to HOD's own department
            department = user.department

    return await repo.list_employees(department=department, is_active=is_active, search=search)


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    user: UserAccountRead | None = Depends(get_optional_user),
) -> EmployeeRead:
    """Create a new employee. Restricted to administrators and management."""
    if user and user.approved_position not in ("SYSADMIN", "MANAGEMENT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only administrators and managers can create employee records.",
        )
    try:
        return await repo.create_employee(data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{employee_id}", response_model=EmployeeRead)
async def get_employee(
    employee_id: UUID,
    user: UserAccountRead | None = Depends(get_optional_user),
) -> EmployeeRead:
    """
    Retrieve employee profile.
    - Employee: Can only view their own employee record.
    - HOD: Can only view employees in their department.
    - Management / SysAdmin: Can view any employee record.
    """
    emp = await repo.get_employee_by_id(employee_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Employee {employee_id} not found")

    if user:
        if user.approved_position == "EMPLOYEE":
            if user.employee_id != employee_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You can only view your own employee record.",
                )
        elif user.approved_position == "DEPT_HEAD":
            u_dept = user.department.upper()
            e_dept = emp.department.upper()
            if u_dept != e_dept and u_dept not in e_dept:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Cannot view employees outside your department.",
                )

    return emp


@router.put("/{employee_id}", response_model=EmployeeRead)
async def update_employee(
    employee_id: UUID,
    data: EmployeeUpdate,
    user: UserAccountRead | None = Depends(get_optional_user),
) -> EmployeeRead:
    """Update employee details. Restricted to administrators and management."""
    if user and user.approved_position not in ("SYSADMIN", "MANAGEMENT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only administrators and managers can update employee records.",
        )
    try:
        return await repo.update_employee(employee_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
