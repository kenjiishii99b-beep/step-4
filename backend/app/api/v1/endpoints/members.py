from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentStaff, DbSession, require_roles
from app.models.enums import RoleEnum
from app.models.member import Member
from app.models.staff import Staff
from app.schemas.member import MemberResponse, MemberUpsertRequest
from app.services import member_service

router = APIRouter()

_require_manager_or_admin = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])


def _to_response(member: Member) -> MemberResponse:
    return MemberResponse(
        member_id=member.member_id,
        member_name=member.member_name,
        phone_number=member.phone_number,
        address=member.address,
        gender=member.gender,
        age=member.age,
        point_balance=member.point_balance,
    )


@router.get("/members/{member_id}", response_model=MemberResponse)
async def get_member(member_id: str, db: DbSession, _current_staff: CurrentStaff) -> MemberResponse:
    try:
        member = await member_service.get_member(db, member_id)
    except member_service.MemberNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "MEMBER_NOT_FOUND", "member_id": exc.member_id},
        ) from exc
    return _to_response(member)


@router.put("/members/{member_id}", response_model=MemberResponse)
async def upsert_member(
    member_id: str,
    payload: MemberUpsertRequest,
    db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> MemberResponse:
    member = await member_service.upsert_member(db, member_id, payload)
    return _to_response(member)
