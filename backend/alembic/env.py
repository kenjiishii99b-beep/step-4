import asyncio
from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.core.database import Base, engine
from app.models import *  # noqa: F401,F403  (register models with Base.metadata)

config = context.config
# ConfigParser は値中の "%" を補間構文として解釈するため、URLエンコードされた
# パスワード（%40 等）を含むDATABASE_URLをそのまま渡すと ValueError になる。
# "%" をエスケープしてから渡す（Alembic公式FAQ記載の回避策）。
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # app.core.database の engine を再利用する（DATABASE_SSL 等の接続設定を
    # ここで重複定義すると設定が乖離するため）。
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
