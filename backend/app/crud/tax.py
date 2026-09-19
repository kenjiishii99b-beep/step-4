from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master import TaxRate


async def get_active_tax_rate(db: AsyncSession, now: datetime) -> TaxRate | None:
    stmt = (
        select(TaxRate)
        .where(
            TaxRate.is_active.is_(True),
            TaxRate.valid_from <= now,
            or_(TaxRate.valid_to.is_(None), TaxRate.valid_to > now),
        )
        .order_by(TaxRate.valid_from.desc(), TaxRate.tax_rate_id.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_tax_rate_by_id(db: AsyncSession, tax_rate_id: str) -> TaxRate | None:
    result = await db.execute(select(TaxRate).where(TaxRate.tax_rate_id == tax_rate_id))
    return result.scalar_one_or_none()


async def create_tax_rate(db: AsyncSession, tax_rate: TaxRate) -> None:
    db.add(tax_rate)
    await db.flush()
