from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import SalesItem, Transaction


async def get_transaction_by_id(db: AsyncSession, transaction_id: str) -> Transaction | None:
    result = await db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_id)
    )
    return result.scalar_one_or_none()


async def get_transaction_for_update(db: AsyncSession, transaction_id: str) -> Transaction | None:
    """返品・交換の二重登録を防ぐため、元取引行をロックして取得する。"""
    result = await db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def get_sales_items_for_transaction(db: AsyncSession, transaction_id: str) -> list[SalesItem]:
    result = await db.execute(select(SalesItem).where(SalesItem.transaction_id == transaction_id))
    return list(result.scalars())


async def get_returned_quantities(db: AsyncSession, parent_transaction_id: str) -> dict[str, int]:
    """指定した元取引に対して、これまでに返品済みの数量をSKU単位で集計する。

    返品行は sales_items.quantity を負数で記録する規約のため、符号を反転して
    正の「返品済み数量」として返す。
    """
    stmt = (
        select(SalesItem.sku_id, func.sum(SalesItem.quantity))
        .join(Transaction, Transaction.transaction_id == SalesItem.transaction_id)
        .where(
            Transaction.parent_transaction_id == parent_transaction_id,
            SalesItem.quantity < 0,
        )
        .group_by(SalesItem.sku_id)
    )
    result = await db.execute(stmt)
    return {sku_id: -int(total) for sku_id, total in result.all()}
