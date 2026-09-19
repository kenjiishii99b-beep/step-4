from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

# 本番ではブラウザから直接叩かれない前提（Next.js BFF 経由のみ）のため、
# 本番環境では Swagger UI / ReDoc / OpenAPI スキーマを無効化する。
_is_dev = settings.ENVIRONMENT in ("local", "development")

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
)

# BFF (Next.js) からのサーバー間通信が前提。ブラウザからの直接アクセスは想定しない。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.include_router(api_router, prefix="/api/v1")
