from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.master_reference import get_color_master, get_size_master
from app.crud.product import create_product, get_product_by_id
from app.crud.sku import create_sku, get_sku_by_barcode, get_sku_by_id
from app.models.product import Product, Sku
from app.schemas.product import (
    ProductCreateRequest,
    ProductUpdateRequest,
    SkuInput,
    SkuLookupResponse,
)


class ProductNotFoundError(Exception):
    def __init__(self, product_id: str) -> None:
        self.product_id = product_id


class ProductAlreadyExistsError(Exception):
    def __init__(self, product_id: str) -> None:
        self.product_id = product_id


class SkuAlreadyExistsError(Exception):
    def __init__(self, sku_id: str) -> None:
        self.sku_id = sku_id


class DuplicateBarcodeError(Exception):
    def __init__(self, barcode_ean13: str) -> None:
        self.barcode_ean13 = barcode_ean13


class SizeMasterNotFoundError(Exception):
    def __init__(self, size_system_id: str, size_code: str) -> None:
        self.size_system_id = size_system_id
        self.size_code = size_code


class ColorMasterNotFoundError(Exception):
    def __init__(self, color_system_id: str, color_code: str) -> None:
        self.color_system_id = color_system_id
        self.color_code = color_code


class SkuNotFoundError(Exception):
    def __init__(self, barcode_ean13: str) -> None:
        self.barcode_ean13 = barcode_ean13


async def _validate_and_build_sku(db: AsyncSession, product_id: str, item: SkuInput) -> Sku:
    if await get_sku_by_id(db, item.sku_id) is not None:
        raise SkuAlreadyExistsError(item.sku_id)
    if await get_sku_by_barcode(db, item.barcode_ean13) is not None:
        raise DuplicateBarcodeError(item.barcode_ean13)
    if await get_size_master(db, item.size_system_id, item.size_code) is None:
        raise SizeMasterNotFoundError(item.size_system_id, item.size_code)
    if await get_color_master(db, item.color_system_id, item.color_code) is None:
        raise ColorMasterNotFoundError(item.color_system_id, item.color_code)

    return Sku(
        sku_id=item.sku_id,
        product_id=product_id,
        barcode_ean13=item.barcode_ean13,
        size_system_id=item.size_system_id,
        size_code=item.size_code,
        color_system_id=item.color_system_id,
        color_code=item.color_code,
        store_stock=item.store_stock,
        warehouse_stock=item.warehouse_stock,
        location=item.location,
        # is_active は DB 側の server_default のみで Python 側の初期値がない。
        # flush 後にこのセッション内で（再クエリせず）直接読み出すと、期限切れ
        # 属性の暗黙リフレッシュが非同期コンテキスト外で走り失敗するため、
        # ここで明示的に設定しておく。
        is_active=True,
    )


async def get_product(db: AsyncSession, product_id: str) -> Product:
    product = await get_product_by_id(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    return product


async def create_product_with_skus(db: AsyncSession, request: ProductCreateRequest) -> Product:
    if await get_product_by_id(db, request.product_id) is not None:
        raise ProductAlreadyExistsError(request.product_id)

    new_skus = [
        await _validate_and_build_sku(db, request.product_id, item) for item in request.skus
    ]

    product = Product(
        product_id=request.product_id,
        product_name=request.product_name,
        category=request.category,
        default_price=request.default_price,
        image_url=request.image_url,
        size_system_id=request.size_system_id,
        color_system_id=request.color_system_id,
    )
    await create_product(db, product)
    for sku in new_skus:
        await create_sku(db, sku)

    await db.commit()
    created = await get_product_by_id(db, request.product_id)
    assert created is not None
    return created


async def update_product(
    db: AsyncSession, product_id: str, request: ProductUpdateRequest
) -> Product:
    product = await get_product_by_id(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)

    existing_sku_ids = {sku.sku_id for sku in product.skus}
    new_items = [item for item in request.skus if item.sku_id not in existing_sku_ids]
    new_skus = [await _validate_and_build_sku(db, product_id, item) for item in new_items]

    product.product_name = request.product_name
    product.category = request.category
    product.default_price = request.default_price
    product.image_url = request.image_url
    product.size_system_id = request.size_system_id
    product.color_system_id = request.color_system_id
    product.is_active = request.is_active

    for sku in new_skus:
        await create_sku(db, sku)
        # 既にこのセッションで selectinload 済みの product.skus はコミット後も
        # 自動では再読込されないため（identity map がロード済みと判断する）、
        # 再クエリせず明示的にコレクションへ追加する。
        product.skus.append(sku)

    await db.commit()
    return product


async def lookup_sku_by_barcode(db: AsyncSession, barcode_ean13: str) -> SkuLookupResponse:
    sku = await get_sku_by_barcode(db, barcode_ean13)
    if sku is None:
        raise SkuNotFoundError(barcode_ean13)

    product = await get_product_by_id(db, sku.product_id)
    assert product is not None
    return SkuLookupResponse(
        sku_id=sku.sku_id,
        barcode_ean13=sku.barcode_ean13,
        product_id=sku.product_id,
        product_name=product.product_name,
        reference_price=product.default_price,
        size_code=sku.size_code,
        color_code=sku.color_code,
        store_stock=sku.store_stock,
        is_active=sku.is_active,
    )
