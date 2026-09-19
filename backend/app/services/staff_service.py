from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.crud.staff import count_staff, create_staff, get_staff_by_id, list_staff
from app.models.enums import RoleEnum
from app.models.staff import Staff
from app.schemas.staff import StaffListResponse, StaffResponse, StaffUpsertRequest


class PasswordRequiredForNewStaffError(Exception):
    pass


class SelfLockoutError(Exception):
    """管理者が自分自身の権限剥奪・無効化を行おうとした場合に発生する。"""


async def upsert_staff(db: AsyncSession, actor_staff_id: str, request: StaffUpsertRequest) -> Staff:
    existing = await get_staff_by_id(db, request.staff_id)

    if existing is None:
        if not request.password:
            raise PasswordRequiredForNewStaffError

        staff = Staff(
            staff_id=request.staff_id,
            staff_name=request.staff_name,
            password_hash=hash_password(request.password),
            role=request.role,
            is_active=request.is_active,
        )
        await create_staff(db, staff)
        await db.commit()
        return staff

    # システム管理者が操作対象を自分自身にした場合、権限剥奪・無効化により
    # 誰も管理者操作を行えなくなる自己ロックアウトを防止する。
    is_self = request.staff_id == actor_staff_id
    if is_self and (request.role != RoleEnum.ADMIN or not request.is_active):
        raise SelfLockoutError

    existing.staff_name = request.staff_name
    existing.role = request.role
    existing.is_active = request.is_active
    if request.password:
        existing.password_hash = hash_password(request.password)

    await db.commit()
    return existing


def _to_response(staff: Staff) -> StaffResponse:
    return StaffResponse(
        staff_id=staff.staff_id,
        staff_name=staff.staff_name,
        role=staff.role,
        is_active=staff.is_active,
    )


async def get_staff_list(
    db: AsyncSession,
    role: RoleEnum | None,
    is_active: bool | None,
    limit: int,
    offset: int,
) -> StaffListResponse:
    items = await list_staff(db, role, is_active, limit, offset)
    total = await count_staff(db, role, is_active)
    return StaffListResponse(items=[_to_response(s) for s in items], total=total)
