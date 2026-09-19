from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, require_roles
from app.models.enums import RoleEnum
from app.models.staff import Staff
from app.schemas.staff import StaffListResponse, StaffResponse, StaffUpsertRequest
from app.services import staff_service

router = APIRouter()

_require_admin = require_roles([RoleEnum.ADMIN])
_CurrentAdmin = Annotated[Staff, Depends(_require_admin)]


@router.get("/admin/staff", response_model=StaffListResponse)
async def get_staff_list(
    db: DbSession,
    _current_admin: _CurrentAdmin,
    role: RoleEnum | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StaffListResponse:
    return await staff_service.get_staff_list(db, role, is_active, limit, offset)


@router.post("/admin/staff", response_model=StaffResponse)
async def upsert_staff(
    payload: StaffUpsertRequest,
    db: DbSession,
    current_admin: _CurrentAdmin,
) -> StaffResponse:
    try:
        staff = await staff_service.upsert_staff(db, current_admin.staff_id, payload)
    except staff_service.PasswordRequiredForNewStaffError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "PASSWORD_REQUIRED",
                "message": "新規スタッフ作成時はパスワードが必須です。",
            },
        ) from exc
    except staff_service.SelfLockoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "SELF_LOCKOUT_PREVENTED",
                "message": "自分自身の権限剥奪・無効化はできません。",
            },
        ) from exc

    return StaffResponse(
        staff_id=staff.staff_id,
        staff_name=staff.staff_name,
        role=staff.role,
        is_active=staff.is_active,
    )
