from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DiscountTargetTypeEnum
from app.models.product import DiscountMaster


async def get_active_discounts(
    db: AsyncSession, sku_ids: set[str], product_ids: set[str], now: datetime
) -> list[DiscountMaster]:
    stmt = select(DiscountMaster).where(
        DiscountMaster.is_active.is_(True),
        DiscountMaster.valid_from <= now,
        or_(DiscountMaster.valid_to.is_(None), DiscountMaster.valid_to > now),
        or_(
            DiscountMaster.sku_id.in_(sku_ids),
            DiscountMaster.product_id.in_(product_ids),
            DiscountMaster.target_type == DiscountTargetTypeEnum.MEMBER,
        ),
    )
    result = await db.execute(stmt)
    return list(result.scalars())


async def get_discount_by_id(db: AsyncSession, discount_id: str) -> DiscountMaster | None:
    result = await db.execute(
        select(DiscountMaster).where(DiscountMaster.discount_id == discount_id)
    )
    return result.scalar_one_or_none()


async def create_discount(db: AsyncSession, discount: DiscountMaster) -> None:
    db.add(discount)
    await db.flush()
