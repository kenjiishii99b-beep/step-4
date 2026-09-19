from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Sku


async def get_skus_for_update(db: AsyncSession, sku_ids: list[str]) -> dict[str, Sku]:
    """会計トランザクション用に対象SKU行をロックして取得する（設計仕様書 2.3節②）。"""
    result = await db.execute(select(Sku).where(Sku.sku_id.in_(sku_ids)).with_for_update())
    return {sku.sku_id: sku for sku in result.scalars()}


async def get_sku_by_id(db: AsyncSession, sku_id: str) -> Sku | None:
    result = await db.execute(select(Sku).where(Sku.sku_id == sku_id))
    return result.scalar_one_or_none()


async def get_sku_for_update(db: AsyncSession, sku_id: str) -> Sku | None:
    """入荷・在庫移動時に対象SKU行をロックして取得する。"""
    result = await db.execute(select(Sku).where(Sku.sku_id == sku_id).with_for_update())
    return result.scalar_one_or_none()


async def get_sku_by_barcode(db: AsyncSession, barcode_ean13: str) -> Sku | None:
    result = await db.execute(select(Sku).where(Sku.barcode_ean13 == barcode_ean13))
    return result.scalar_one_or_none()


async def create_sku(db: AsyncSession, sku: Sku) -> None:
    db.add(sku)
    await db.flush()
