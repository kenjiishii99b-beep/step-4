from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import DbSession
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, RefreshResponse
from app.services import auth_service

router = APIRouter()

_INVALID_CREDENTIALS_DETAIL = "IDまたはパスワードが正しくありません。"
_INVALID_REFRESH_TOKEN_DETAIL = "認証が必要です。再度ログインしてください。"


def _client_ip(request: Request) -> str:
    # Backend は BFF (Next.js) からの内部通信のみを受け付けるため、
    # request.client.host は常に BFF コンテナの IP になり店舗ごとの
    # 送信元を区別できない。BFF が転送する X-Forwarded-For を信頼して
    # 実際のブラウザ側送信元を IP 単位制限のキーとして用いる。
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, db: DbSession) -> LoginResponse:
    try:
        return await auth_service.authenticate_staff(
            db, payload.staff_id, payload.password, _client_ip(request)
        )
    except auth_service.AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ログイン試行回数が上限に達しました。しばらくしてから再度お試しください。",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_DETAIL,
        ) from exc


@router.post("/auth/refresh", response_model=RefreshResponse)
async def refresh(payload: RefreshRequest, db: DbSession) -> RefreshResponse:
    try:
        return await auth_service.refresh_access_token(db, payload.refresh_token)
    except auth_service.InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_REFRESH_TOKEN_DETAIL,
        ) from exc
