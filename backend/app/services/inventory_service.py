from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.sku import get_sku_by_id, get_sku_for_update
from app.models.enums import MovementTypeEnum
from app.models.inventory import InventoryHistory
from app.models.product import Sku
from app.schemas.inventory import InventoryReceiptRequest, InventoryTransferRequest, StockLocation


class SkuNotFoundError(Exception):
    def __init__(self, sku_id: str) -> None:
        self.sku_id = sku_id


class InsufficientStockError(Exception):
    def __init__(
        self, sku_id: str, location: StockLocation, available: int, requested: int
    ) -> None:
        self.sku_id = sku_id
        self.location = location
        self.available = available
        self.requested = requested


async def get_inventory_status(db: AsyncSession, sku_id: str) -> Sku:
    sku = await get_sku_by_id(db, sku_id)
    if sku is None:
        raise SkuNotFoundError(sku_id)
    return sku


async def receive_stock(db: AsyncSession, staff_id: str, request: InventoryReceiptRequest) -> Sku:
    sku = await get_sku_for_update(db, request.sku_id)
    if sku is None:
        await db.rollback()
        raise SkuNotFoundError(request.sku_id)

    if request.location == StockLocation.STORE:
        sku.store_stock += request.quantity
    else:
        sku.warehouse_stock += request.quantity

    db.add(
        InventoryHistory(
            sku_id=request.sku_id,
            location=request.location.value,
            quantity_delta=request.quantity,
            movement_type=MovementTypeEnum.RECEIPT,
            staff_id=staff_id,
        )
    )
    await db.commit()
    return sku


async def transfer_stock(db: AsyncSession, staff_id: str, request: InventoryTransferRequest) -> Sku:
    sku = await get_sku_for_update(db, request.sku_id)
    if sku is None:
        await db.rollback()
        raise SkuNotFoundError(request.sku_id)

    current = (
        sku.store_stock if request.from_location == StockLocation.STORE else sku.warehouse_stock
    )
    if current < request.quantity:
        # rollback は ORM オブジェクトの属性を失効させるため、遅延ロードを
        # 誘発する前に必要な値をローカル変数へ退避しておく。
        available = current
        await db.rollback()
        raise InsufficientStockError(
            request.sku_id, request.from_location, available, request.quantity
        )

    if request.from_location == StockLocation.STORE:
        sku.store_stock -= request.quantity
        sku.warehouse_stock += request.quantity
    else:
        sku.warehouse_stock -= request.quantity
        sku.store_stock += request.quantity

    db.add_all(
        [
            InventoryHistory(
                sku_id=request.sku_id,
                location=request.from_location.value,
                quantity_delta=-request.quantity,
                movement_type=MovementTypeEnum.TRANSFER,
                staff_id=staff_id,
            ),
            InventoryHistory(
                sku_id=request.sku_id,
                location=request.to_location.value,
                quantity_delta=request.quantity,
                movement_type=MovementTypeEnum.TRANSFER,
                staff_id=staff_id,
            ),
        ]
    )
    await db.commit()
    return sku
