from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member


async def get_member_by_id(db: AsyncSession, member_id: str) -> Member | None:
    result = await db.execute(select(Member).where(Member.member_id == member_id))
    return result.scalar_one_or_none()


async def create_member(db: AsyncSession, member: Member) -> None:
    db.add(member)
    await db.flush()
