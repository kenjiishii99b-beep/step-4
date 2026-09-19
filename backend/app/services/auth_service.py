from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import login_rate_limiter
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.crud.staff import get_staff_by_id
from app.models.staff import Staff
from app.schemas.auth import LoginResponse, RefreshResponse


class AccountLockedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


def _issue_login_response(staff: Staff) -> LoginResponse:
    return LoginResponse(
        access_token=create_access_token(staff.staff_id, staff.role),
        refresh_token=create_refresh_token(staff.staff_id, staff.role),
        staff_id=staff.staff_id,
        staff_name=staff.staff_name,
        role=staff.role,
    )


async def authenticate_staff(
    db: AsyncSession, staff_id: str, password: str, ip_address: str
) -> LoginResponse:
    remaining = await login_rate_limiter.seconds_until_unlocked(staff_id, ip_address)
    if remaining is not None:
        raise AccountLockedError(retry_after_seconds=int(remaining) + 1)

    staff = await get_staff_by_id(db, staff_id)
    if staff is None or not staff.is_active or not verify_password(password, staff.password_hash):
        await login_rate_limiter.record_failure(staff_id, ip_address)
        raise InvalidCredentialsError

    await login_rate_limiter.reset(staff_id, ip_address)
    return _issue_login_response(staff)


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> RefreshResponse:
    try:
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise InvalidRefreshTokenError from exc

    staff = await get_staff_by_id(db, payload.staff_id)
    if staff is None or not staff.is_active:
        raise InvalidRefreshTokenError

    return RefreshResponse(
        access_token=create_access_token(staff.staff_id, staff.role),
        staff_id=staff.staff_id,
        staff_name=staff.staff_name,
        role=staff.role,
    )
