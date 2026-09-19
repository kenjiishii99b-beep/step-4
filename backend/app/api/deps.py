from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError, TokenType, decode_token
from app.crud.staff import get_staff_by_id
from app.models.enums import RoleEnum
from app.models.staff import Staff

DbSession = Annotated[AsyncSession, Depends(get_db)]

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="認証情報が無効です。再度ログインしてください。",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_active_staff(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> Staff:
    if credentials is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise _CREDENTIALS_EXCEPTION from exc

    staff = await get_staff_by_id(db, payload.staff_id)
    if staff is None or not staff.is_active:
        raise _CREDENTIALS_EXCEPTION
    return staff


CurrentStaff = Annotated[Staff, Depends(get_current_active_staff)]


def require_roles(allowed_roles: list[RoleEnum]):
    def role_checker(current_user: CurrentStaff) -> Staff:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="操作を行う権限がありません。",
            )
        return current_user

    return role_checker
