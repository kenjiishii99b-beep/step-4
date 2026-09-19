"""Playwright E2E テスト用の固定フィクスチャを投入する（冪等）。

数量系フィールド（在庫）は実行のたびに大きな値へリセットし、繰り返し
テスト実行しても在庫切れで失敗しないようにする。パスワードも毎回
既知の値へ上書きするため、過去のセッションでハッシュが失われていても
問題なく再利用できる。
"""

import asyncio
from datetime import datetime

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import (
    ColorMaster,
    DiscountMaster,
    DiscountTargetTypeEnum,
    DiscountTypeEnum,
    Member,
    Product,
    RoleEnum,
    SizeMaster,
    Sku,
    Staff,
)

CASHIER_STAFF_ID = "E2E-CASHIER"
MANAGER_STAFF_ID = "E2E-MANAGER"
E2E_PASSWORD = "E2ePlaywright!23"

SIZE_SYSTEM_ID = "E2E-SIZE"
COLOR_SYSTEM_ID = "E2E-COLOR"

PRODUCT_1_ID = "E2E-PRODUCT-1"
PRODUCT_2_ID = "E2E-PRODUCT-2"
PRODUCT_3_ID = "E2E-PRODUCT-3"

SKU_1_ID = "E2E-PRODUCT-1-M-BLK"
SKU_1_BARCODE = "2900000000018"
SKU_2_ID = "E2E-PRODUCT-2-M-BLK"
SKU_2_BARCODE = "2900000000025"
# 在庫移動テスト専用SKU。チェックアウト/交換テストと在庫数を共有しないよう分離し、
# 店舗在庫・倉庫在庫の両方を毎回固定値へリセットして再現性を確保する。
SKU_3_ID = "E2E-PRODUCT-3-M-BLK"
SKU_3_BARCODE = "2900000000032"

SEED_STOCK = 999_999
INVENTORY_TEST_STORE_STOCK = 100
INVENTORY_TEST_WAREHOUSE_STOCK = 0

MEMBER_ID = "E2E-MEMBER-1"
MEMBER_NAME = "E2E Member"
MEMBER_POINT_BALANCE = 250
MEMBER_DISCOUNT_ID = "E2E-MEMBER-DISCOUNT"
MEMBER_DISCOUNT_RATE = 10  # %

# UT-03（購入リストSKU上限）用に、101種類の異なるSKUを用意する。
BULK_SKU_COUNT = 101
EPOCH = datetime(1970, 1, 1)


async def _ensure_staff(db, staff_id: str, name: str, role: RoleEnum) -> None:
    staff = await db.get(Staff, staff_id)
    if staff is None:
        db.add(
            Staff(
                staff_id=staff_id,
                staff_name=name,
                password_hash=hash_password(E2E_PASSWORD),
                role=role,
                is_active=True,
            )
        )
    else:
        staff.password_hash = hash_password(E2E_PASSWORD)
        staff.role = role
        staff.is_active = True
    await db.commit()


async def _ensure_size_master(db) -> None:
    obj = await db.get(SizeMaster, (SIZE_SYSTEM_ID, "M"))
    if obj is None:
        db.add(SizeMaster(size_system_id=SIZE_SYSTEM_ID, size_code="M", size_name="M"))
        await db.commit()


async def _ensure_color_master(db) -> None:
    obj = await db.get(ColorMaster, (COLOR_SYSTEM_ID, "BLK"))
    if obj is None:
        db.add(ColorMaster(color_system_id=COLOR_SYSTEM_ID, color_code="BLK", color_name="Black"))
        await db.commit()


async def _ensure_product(db, product_id: str, name: str, price: int) -> None:
    obj = await db.get(Product, product_id)
    if obj is None:
        db.add(
            Product(
                product_id=product_id,
                product_name=name,
                category="TOPS",
                default_price=price,
                is_active=True,
            )
        )
    else:
        obj.is_active = True
    await db.commit()


async def _ensure_sku(
    db,
    sku_id: str,
    barcode: str,
    product_id: str,
    store_stock: int = SEED_STOCK,
    warehouse_stock: int = 0,
) -> None:
    sku = await db.get(Sku, sku_id)
    if sku is None:
        db.add(
            Sku(
                sku_id=sku_id,
                product_id=product_id,
                barcode_ean13=barcode,
                size_system_id=SIZE_SYSTEM_ID,
                size_code="M",
                color_system_id=COLOR_SYSTEM_ID,
                color_code="BLK",
                store_stock=store_stock,
                warehouse_stock=warehouse_stock,
                is_active=True,
            )
        )
    else:
        sku.barcode_ean13 = barcode
        sku.store_stock = store_stock
        sku.warehouse_stock = warehouse_stock
        sku.is_active = True
    await db.commit()


async def _ensure_member(db) -> None:
    obj = await db.get(Member, MEMBER_ID)
    if obj is None:
        db.add(
            Member(
                member_id=MEMBER_ID,
                member_name=MEMBER_NAME,
                point_balance=MEMBER_POINT_BALANCE,
            )
        )
    else:
        obj.member_name = MEMBER_NAME
        obj.point_balance = MEMBER_POINT_BALANCE
    await db.commit()


async def _ensure_member_discount(db) -> None:
    obj = await db.get(DiscountMaster, MEMBER_DISCOUNT_ID)
    if obj is None:
        db.add(
            DiscountMaster(
                discount_id=MEMBER_DISCOUNT_ID,
                target_type=DiscountTargetTypeEnum.MEMBER,
                product_id=None,
                sku_id=None,
                discount_type=DiscountTypeEnum.RATE,
                discount_value=MEMBER_DISCOUNT_RATE,
                valid_from=EPOCH,
                valid_to=None,
                priority=1,
                is_active=True,
            )
        )
    else:
        obj.discount_value = MEMBER_DISCOUNT_RATE
        obj.valid_from = EPOCH
        obj.valid_to = None
        obj.is_active = True
    await db.commit()


def bulk_sku_id(index: int) -> str:
    return f"E2E-BULK-{index:03d}-M-BLK"


# GS1の「restricted circulation number」用プレフィックス(20-29)のうち、
# 既存デモ商品（backend/generate_demo_products.py、プレフィックス"20"）と衝突しない
# "29"を使用する。チェックデジットも正規のEAN-13アルゴリズムで計算する。
_BULK_BARCODE_PREFIX = "29"


def _ean13_check_digit(digits12: str) -> str:
    total = sum(int(d) * (3 if i % 2 == 1 else 1) for i, d in enumerate(digits12))
    return str((10 - total % 10) % 10)


def bulk_sku_barcode(index: int) -> str:
    body = f"{_BULK_BARCODE_PREFIX}{100 + index:010d}"
    return body + _ean13_check_digit(body)


async def _ensure_bulk_skus(db) -> None:
    # UT-03「異なるSKUを100種類→101種類目追加」の実データ。1商品1SKUとし、
    # 在庫は個々のテストで消費しない（カート追加のみ）ため少量で十分。
    for i in range(1, BULK_SKU_COUNT + 1):
        product_id = f"E2E-BULK-{i:03d}"
        await _ensure_product(db, product_id, f"E2E Bulk Item {i}", 100 + i)
        await _ensure_sku(db, bulk_sku_id(i), bulk_sku_barcode(i), product_id, store_stock=10)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await _ensure_size_master(db)
        await _ensure_color_master(db)
        await _ensure_product(db, PRODUCT_1_ID, "E2E Tee", 2500)
        await _ensure_product(db, PRODUCT_2_ID, "E2E Pants", 4800)
        await _ensure_product(db, PRODUCT_3_ID, "E2E Cap", 1500)
        await _ensure_sku(db, SKU_1_ID, SKU_1_BARCODE, PRODUCT_1_ID)
        await _ensure_sku(db, SKU_2_ID, SKU_2_BARCODE, PRODUCT_2_ID)
        await _ensure_sku(
            db,
            SKU_3_ID,
            SKU_3_BARCODE,
            PRODUCT_3_ID,
            store_stock=INVENTORY_TEST_STORE_STOCK,
            warehouse_stock=INVENTORY_TEST_WAREHOUSE_STOCK,
        )
        await _ensure_staff(db, CASHIER_STAFF_ID, "E2E Cashier", RoleEnum.STAFF)
        await _ensure_staff(db, MANAGER_STAFF_ID, "E2E Manager", RoleEnum.MANAGER)
        await _ensure_member(db)
        await _ensure_member_discount(db)
        await _ensure_bulk_skus(db)
    print("E2E fixtures seeded.")


if __name__ == "__main__":
    asyncio.run(main())
