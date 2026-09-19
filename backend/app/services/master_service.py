from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.discount import create_discount, get_discount_by_id
from app.crud.product import get_products_by_ids
from app.crud.sku import get_sku_by_id
from app.crud.tax import create_tax_rate, get_tax_rate_by_id
from app.models.enums import DiscountTargetTypeEnum
from app.models.master import TaxRate
from app.models.product import DiscountMaster
from app.schemas.masters import DiscountUpsertRequest, TaxRateUpsertRequest


class SkuNotFoundError(Exception):
    def __init__(self, sku_id: str) -> None:
        self.sku_id = sku_id


class ProductNotFoundError(Exception):
    def __init__(self, product_id: str) -> None:
        self.product_id = product_id


async def upsert_discount(db: AsyncSession, request: DiscountUpsertRequest) -> DiscountMaster:
    # target_type に応じた参照整合性をアプリ側で確認する（DB外部キーは
    # product_id/sku_id のどちらか一方が常にNULLになりうるため素通りする）。
    if request.target_type == DiscountTargetTypeEnum.SKU:
        sku = await get_sku_by_id(db, request.sku_id)
        if sku is None:
            raise SkuNotFoundError(request.sku_id)
    elif request.target_type == DiscountTargetTypeEnum.PRODUCT:
        products = await get_products_by_ids(db, {request.product_id})
        if request.product_id not in products:
            raise ProductNotFoundError(request.product_id)

    existing = await get_discount_by_id(db, request.discount_id)
    if existing is None:
        discount = DiscountMaster(
            discount_id=request.discount_id,
            target_type=request.target_type,
            product_id=request.product_id,
            sku_id=request.sku_id,
            discount_type=request.discount_type,
            discount_value=request.discount_value,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            priority=request.priority,
            is_active=request.is_active,
        )
        await create_discount(db, discount)
    else:
        existing.target_type = request.target_type
        existing.product_id = request.product_id
        existing.sku_id = request.sku_id
        existing.discount_type = request.discount_type
        existing.discount_value = request.discount_value
        existing.valid_from = request.valid_from
        existing.valid_to = request.valid_to
        existing.priority = request.priority
        existing.is_active = request.is_active
        discount = existing

    await db.commit()
    return discount


async def upsert_tax_rate(db: AsyncSession, request: TaxRateUpsertRequest) -> TaxRate:
    existing = await get_tax_rate_by_id(db, request.tax_rate_id)
    if existing is None:
        tax_rate = TaxRate(
            tax_rate_id=request.tax_rate_id,
            tax_rate=request.tax_rate,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            is_active=request.is_active,
        )
        await create_tax_rate(db, tax_rate)
    else:
        existing.tax_rate = request.tax_rate
        existing.valid_from = request.valid_from
        existing.valid_to = request.valid_to
        existing.is_active = request.is_active
        tax_rate = existing

    await db.commit()
    return tax_rate
