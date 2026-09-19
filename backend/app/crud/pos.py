from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryHistory
from app.models.transaction import SalesItem, Transaction


async def persist_checkout(
    db: AsyncSession,
    transaction: Transaction,
    sales_items: list[SalesItem],
    inventory_histories: list[InventoryHistory],
) -> None:
    """SKU在庫の減算は呼び出し側で FOR UPDATE 取得済みの ORM オブジェクトを
    直接変更済みのため、ここでは新規エンティティの追加のみを行う。"""
    db.add(transaction)
    db.add_all(sales_items)
    db.add_all(inventory_histories)
    await db.flush()
