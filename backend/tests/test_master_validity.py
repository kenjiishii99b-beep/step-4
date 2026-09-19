"""IT-13 / IT-14: 値引き・税率マスターの有効期間境界を検証する。

get_active_discounts / get_active_tax_rate は「現在時刻」を引数として受け取る
純粋なクエリ関数のため、任意の過去日時を直接指定してテストする。これにより
他のテストが依存する「現在有効な税率・値引き」をグローバルに変更せずに
境界値を検証できる。
"""

from collections.abc import AsyncGenerator
from datetime import datetime

import pytest

from app.core.database import AsyncSessionLocal
from app.crud.discount import get_active_discounts
from app.crud.tax import get_active_tax_rate
from app.models import (
    ColorMaster,
    DiscountMaster,
    DiscountTargetTypeEnum,
    DiscountTypeEnum,
    Product,
    SizeMaster,
    Sku,
    TaxRate,
)

PRODUCT_ID = "AUTOTEST-VALIDITY-PRODUCT"
SKU_ID = "AUTOTEST-VALIDITY-SKU"
SIZE_SYSTEM_ID = "AUTOTEST-VALIDITY-SIZE"
COLOR_SYSTEM_ID = "AUTOTEST-VALIDITY-COLOR"
TAX_RATE_ID = "AUTOTEST-VALIDITY-TAX"
DISCOUNT_ID = "AUTOTEST-VALIDITY-DISCOUNT"

# 実時間から隔離された固定の過去期間で検証する。
WINDOW_START = datetime(2020, 1, 1)
WINDOW_END = datetime(2020, 6, 1)
BEFORE_WINDOW = datetime(2019, 6, 1)
INSIDE_WINDOW = datetime(2020, 3, 1)
AFTER_WINDOW = datetime(2020, 12, 1)


@pytest.fixture(scope="module", autouse=True)
async def fixtures() -> AsyncGenerator[None, None]:
    async with AsyncSessionLocal() as db:
        if await db.get(SizeMaster, (SIZE_SYSTEM_ID, "M")) is None:
            db.add(SizeMaster(size_system_id=SIZE_SYSTEM_ID, size_code="M", size_name="M"))
            await db.commit()
        if await db.get(ColorMaster, (COLOR_SYSTEM_ID, "BLK")) is None:
            db.add(
                ColorMaster(color_system_id=COLOR_SYSTEM_ID, color_code="BLK", color_name="Black")
            )
            await db.commit()
        if await db.get(Product, PRODUCT_ID) is None:
            db.add(
                Product(
                    product_id=PRODUCT_ID,
                    product_name="Validity Tee",
                    category="TOPS",
                    default_price=1000,
                )
            )
            await db.commit()
        if await db.get(Sku, SKU_ID) is None:
            db.add(
                Sku(
                    sku_id=SKU_ID,
                    product_id=PRODUCT_ID,
                    barcode_ean13="4900000000966",
                    size_system_id=SIZE_SYSTEM_ID,
                    size_code="M",
                    color_system_id=COLOR_SYSTEM_ID,
                    color_code="BLK",
                    store_stock=100,
                )
            )
            await db.commit()

        # 値引き・税率は2020/1/1〜2020/6/1のみ有効な期間限定マスターとして登録する。
        if await db.get(DiscountMaster, DISCOUNT_ID) is None:
            db.add(
                DiscountMaster(
                    discount_id=DISCOUNT_ID,
                    target_type=DiscountTargetTypeEnum.SKU,
                    sku_id=SKU_ID,
                    discount_type=DiscountTypeEnum.RATE,
                    discount_value="10.00",
                    valid_from=WINDOW_START,
                    valid_to=WINDOW_END,
                    priority=1,
                    is_active=True,
                )
            )
            await db.commit()
        if await db.get(TaxRate, TAX_RATE_ID) is None:
            db.add(
                TaxRate(
                    tax_rate_id=TAX_RATE_ID,
                    tax_rate="8.00",
                    valid_from=WINDOW_START,
                    valid_to=WINDOW_END,
                    is_active=True,
                )
            )
            await db.commit()
    yield


async def test_discount_not_active_before_valid_from() -> None:
    async with AsyncSessionLocal() as db:
        discounts = await get_active_discounts(db, {SKU_ID}, {PRODUCT_ID}, BEFORE_WINDOW)
    assert DISCOUNT_ID not in {d.discount_id for d in discounts}


async def test_discount_active_within_window() -> None:
    async with AsyncSessionLocal() as db:
        discounts = await get_active_discounts(db, {SKU_ID}, {PRODUCT_ID}, INSIDE_WINDOW)
    assert DISCOUNT_ID in {d.discount_id for d in discounts}


async def test_discount_not_active_after_valid_to() -> None:
    async with AsyncSessionLocal() as db:
        discounts = await get_active_discounts(db, {SKU_ID}, {PRODUCT_ID}, AFTER_WINDOW)
    assert DISCOUNT_ID not in {d.discount_id for d in discounts}


async def test_tax_rate_not_found_before_valid_from() -> None:
    async with AsyncSessionLocal() as db:
        # この固定期間には他のテスト用税率が存在しないため、期間外では
        # そもそも該当する税率が見つからないことを確認する。
        rate = await get_active_tax_rate(db, BEFORE_WINDOW)
    assert rate is None or rate.tax_rate_id != TAX_RATE_ID


async def test_tax_rate_active_within_window() -> None:
    async with AsyncSessionLocal() as db:
        rate = await get_active_tax_rate(db, INSIDE_WINDOW)
    assert rate is not None
    assert rate.tax_rate_id == TAX_RATE_ID
    assert str(rate.tax_rate) == "8.00"


async def test_tax_rate_not_active_after_valid_to() -> None:
    async with AsyncSessionLocal() as db:
        rate = await get_active_tax_rate(db, AFTER_WINDOW)
    assert rate is None or rate.tax_rate_id != TAX_RATE_ID
