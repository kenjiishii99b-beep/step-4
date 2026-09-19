from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.member import create_member, get_member_by_id
from app.models.member import Member
from app.schemas.member import MemberUpsertRequest


class MemberNotFoundError(Exception):
    def __init__(self, member_id: str) -> None:
        self.member_id = member_id


async def get_member(db: AsyncSession, member_id: str) -> Member:
    member = await get_member_by_id(db, member_id)
    if member is None:
        raise MemberNotFoundError(member_id)
    return member


async def upsert_member(db: AsyncSession, member_id: str, request: MemberUpsertRequest) -> Member:
    existing = await get_member_by_id(db, member_id)

    if existing is None:
        member = Member(
            member_id=member_id,
            member_name=request.member_name,
            phone_number=request.phone_number,
            address=request.address,
            gender=request.gender,
            age=request.age,
            point_balance=request.point_balance or 0,
        )
        await create_member(db, member)
    else:
        existing.member_name = request.member_name
        existing.phone_number = request.phone_number
        existing.address = request.address
        existing.gender = request.gender
        existing.age = request.age
        if request.point_balance is not None:
            existing.point_balance = request.point_balance
        member = existing

    await db.commit()
    return member
