import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# asyncmy は ssl=True だけでは TLS ハンドシェイクを行わない（実際に
# ssl.SSLContext を渡す必要がある）。Azure Database for MySQL Flexible
# Server は require_secure_transport=ON がデフォルトのため必須。
_connect_args = {"ssl": ssl.create_default_context()} if settings.DATABASE_SSL else {}

engine = create_async_engine(
    settings.DATABASE_URL, pool_pre_ping=True, echo=False, connect_args=_connect_args
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
