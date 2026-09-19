from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RoleEnum
from app.models.staff import Staff


async def get_staff_by_id(db: AsyncSession, staff_id: str) -> Staff | None:
    result = await db.execute(select(Staff).where(Staff.staff_id == staff_id))
    return result.scalar_one_or_none()


async def create_staff(db: AsyncSession, staff: Staff) -> None:
    db.add(staff)
    await db.flush()


def _apply_staff_filters(stmt, role: RoleEnum | None, is_active: bool | None):
    if role is not None:
        stmt = stmt.where(Staff.role == role)
    if is_active is not None:
        stmt = stmt.where(Staff.is_active == is_active)
    return stmt


async def list_staff(
    db: AsyncSession,
    role: RoleEnum | None,
    is_active: bool | None,
    limit: int,
    offset: int,
) -> list[Staff]:
    stmt = _apply_staff_filters(select(Staff), role, is_active)
    stmt = stmt.order_by(Staff.created_at.desc(), Staff.staff_id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars())


async def count_staff(db: AsyncSession, role: RoleEnum | None, is_active: bool | None) -> int:
    stmt = _apply_staff_filters(select(func.count()).select_from(Staff), role, is_active)
    result = await db.execute(stmt)
    return result.scalar_one()
