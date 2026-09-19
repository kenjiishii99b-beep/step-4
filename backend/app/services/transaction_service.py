from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.transaction import get_sales_items_for_transaction, get_transaction_by_id
from app.models.transaction import SalesItem, Transaction


class TransactionNotFoundError(Exception):
    def __init__(self, transaction_id: str) -> None:
        self.transaction_id = transaction_id


async def get_transaction_detail(
    db: AsyncSession, transaction_id: str
) -> tuple[Transaction, list[SalesItem]]:
    transaction = await get_transaction_by_id(db, transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(transaction_id)
    items = await get_sales_items_for_transaction(db, transaction_id)
    return transaction, items
