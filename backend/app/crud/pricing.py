from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import PriceHistory


async def get_active_price_histories(
    db: AsyncSession, sku_ids: set[str], product_ids: set[str], now: datetime
) -> list[PriceHistory]:
    stmt = select(PriceHistory).where(
        PriceHistory.is_active.is_(True),
        PriceHistory.valid_from <= now,
        or_(PriceHistory.valid_to.is_(None), PriceHistory.valid_to > now),
        or_(
            PriceHistory.sku_id.in_(sku_ids),
            and_(PriceHistory.sku_id.is_(None), PriceHistory.product_id.in_(product_ids)),
        ),
    )
    result = await db.execute(stmt)
    return list(result.scalars())
