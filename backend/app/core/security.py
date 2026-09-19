from datetime import UTC, datetime, timedelta
from enum import StrEnum

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings
from app.models.enums import RoleEnum

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    staff_id: str
    role: RoleEnum
    token_type: TokenType
    exp: datetime


class InvalidTokenError(Exception):
    pass


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(plain_password, password_hash)


def _create_token(
    staff_id: str, role: RoleEnum, token_type: TokenType, expires_delta: timedelta
) -> str:
    now = datetime.now(UTC)
    payload = {
        "staff_id": staff_id,
        "role": role.value,
        "token_type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(staff_id: str, role: RoleEnum) -> str:
    return _create_token(
        staff_id,
        role,
        TokenType.ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(staff_id: str, role: RoleEnum) -> str:
    return _create_token(
        staff_id,
        role,
        TokenType.REFRESH,
        timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    try:
        raw = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise InvalidTokenError("トークンが無効です。") from exc

    payload = TokenPayload.model_validate(raw)
    if payload.token_type != expected_type:
        raise InvalidTokenError("トークン種別が不正です。")
    return payload
