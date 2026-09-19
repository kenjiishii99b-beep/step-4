from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import ColorMaster, SizeMaster


async def get_size_master(
    db: AsyncSession, size_system_id: str, size_code: str
) -> SizeMaster | None:
    result = await db.execute(
        select(SizeMaster).where(
            SizeMaster.size_system_id == size_system_id, SizeMaster.size_code == size_code
        )
    )
    return result.scalar_one_or_none()


async def get_color_master(
    db: AsyncSession, color_system_id: str, color_code: str
) -> ColorMaster | None:
    result = await db.execute(
        select(ColorMaster).where(
            ColorMaster.color_system_id == color_system_id, ColorMaster.color_code == color_code
        )
    )
    return result.scalar_one_or_none()
