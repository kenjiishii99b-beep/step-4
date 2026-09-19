from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
from httpx import AsyncClient

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
    TaxRate,
)

PASSWORD = "checkout-battery-staple"

# 取引履歴は物理削除しない設計方針（4.1節）のため、これらのマスターは
# get-or-create で再利用し、テスト終了後も削除しない。数量系フィールドのみ
# 各テスト前にリセットする。
PRODUCT_ID = "AUTOTEST-POS-PRODUCT"
# 商品単位の値引きテスト専用の別商品。PRODUCT_ID を共用すると、商品単位の
# 値引きが他テストの SKU にも波及してしまうため分離する。
DISCOUNT_PRODUCT_ID = "AUTOTEST-POS-PRODUCT-DISCOUNT"
STAFF_ID = "AUTOTEST-POS-STAFF"
MEMBER_ID = "AUTOTEST-POS-MEMBER"
TAX_RATE_ID = "AUTOTEST-POS-TAX"
SIZE_SYSTEM_ID = "AUTOTEST-POS-SIZE"
COLOR_SYSTEM_ID = "AUTOTEST-POS-COLOR"

EPOCH = datetime(1970, 1, 1)


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


async def _ensure_product(db, product_id: str = PRODUCT_ID) -> None:
    obj = await db.get(Product, product_id)
    if obj is None:
        db.add(
            Product(
                product_id=product_id,
                product_name="Autotest Tee",
                category="TOPS",
                default_price=1000,
            )
        )
        await db.commit()


async def _ensure_sku(
    db, sku_id: str, barcode: str, stock: int, product_id: str = PRODUCT_ID
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
                store_stock=stock,
            )
        )
    else:
        sku.store_stock = stock
    await db.commit()


async def _ensure_staff(db) -> None:
    staff = await db.get(Staff, STAFF_ID)
    if staff is None:
        db.add(
            Staff(
                staff_id=STAFF_ID,
                staff_name="Autotest Cashier",
                password_hash=hash_password(PASSWORD),
                role=RoleEnum.STAFF,
                is_active=True,
            )
        )
    else:
        staff.is_active = True
    await db.commit()


async def _ensure_member(db) -> None:
    obj = await db.get(Member, MEMBER_ID)
    if obj is None:
        db.add(Member(member_id=MEMBER_ID, member_name="Autotest Member"))
        await db.commit()


async def _ensure_tax_rate(db) -> None:
    obj = await db.get(TaxRate, TAX_RATE_ID)
    if obj is None:
        db.add(
            TaxRate(
                tax_rate_id=TAX_RATE_ID,
                tax_rate="10.00",
                valid_from=EPOCH,
                valid_to=None,
                is_active=True,
            )
        )
        await db.commit()


async def _ensure_discount(
    db,
    discount_id: str,
    target_type,
    target_id_kwargs,
    value,
    priority,
    discount_type=DiscountTypeEnum.RATE,
    valid_from=EPOCH,
    valid_to=None,
):
    obj = await db.get(DiscountMaster, discount_id)
    if obj is None:
        db.add(
            DiscountMaster(
                discount_id=discount_id,
                target_type=target_type,
                discount_type=discount_type,
                discount_value=value,
                valid_from=valid_from,
                valid_to=valid_to,
                priority=priority,
                is_active=True,
                **target_id_kwargs,
            )
        )
    else:
        obj.discount_type = discount_type
        obj.discount_value = value
        obj.valid_from = valid_from
        obj.valid_to = valid_to
        obj.priority = priority
        obj.is_active = True
    await db.commit()


@pytest.fixture(scope="module", autouse=True)
async def pos_master_data() -> AsyncGenerator[None, None]:
    async with AsyncSessionLocal() as db:
        await _ensure_size_master(db)
        await _ensure_color_master(db)
        await _ensure_product(db)
        await _ensure_staff(db)
        await _ensure_member(db)
        await _ensure_tax_rate(db)
    yield


async def _login(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": STAFF_ID, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    token = await _login(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def main_sku() -> AsyncGenerator[str, None]:
    sku_id = "AUTOTEST-POS-SKU-MAIN"
    async with AsyncSessionLocal() as db:
        await _ensure_sku(db, sku_id, "4900000000010", stock=500)
    yield sku_id


@pytest.fixture
async def low_stock_sku() -> AsyncGenerator[str, None]:
    sku_id = "AUTOTEST-POS-SKU-LOWSTOCK"
    async with AsyncSessionLocal() as db:
        await _ensure_sku(db, sku_id, "4900000000027", stock=1)
    yield sku_id


@pytest.fixture
async def discount_priority_skus() -> AsyncGenerator[str, None]:
    sku_id = "AUTOTEST-POS-SKU-DISCOUNT"
    async with AsyncSessionLocal() as db:
        await _ensure_product(db, DISCOUNT_PRODUCT_ID)
        await _ensure_sku(db, sku_id, "4900000000034", stock=500, product_id=DISCOUNT_PRODUCT_ID)
        await _ensure_discount(
            db,
            "AUTOTEST-POS-DISCOUNT-SKU",
            DiscountTargetTypeEnum.SKU,
            {"sku_id": sku_id},
            value="10.00",
            priority=1,
        )
        await _ensure_discount(
            db,
            "AUTOTEST-POS-DISCOUNT-PRODUCT",
            DiscountTargetTypeEnum.PRODUCT,
            {"product_id": DISCOUNT_PRODUCT_ID},
            value="50.00",
            priority=1,
        )
    yield sku_id


@pytest.fixture
async def amount_discount_sku() -> AsyncGenerator[str, None]:
    """BE-U11: discount_type=AMOUNT（金額値引き）の計算検証用。"""
    sku_id = "AUTOTEST-POS-SKU-AMOUNT-DISCOUNT"
    async with AsyncSessionLocal() as db:
        await _ensure_sku(db, sku_id, "4900000000225", stock=500)
        await _ensure_discount(
            db,
            "AUTOTEST-POS-DISCOUNT-AMOUNT",
            DiscountTargetTypeEnum.SKU,
            {"sku_id": sku_id},
            value="300.00",
            priority=1,
            discount_type=DiscountTypeEnum.AMOUNT,
        )
    yield sku_id


@pytest.fixture
async def scheduled_discount_sku() -> AsyncGenerator[str, None]:
    """IT-13: 値引きの有効期間（valid_from/valid_to）境界検証用。

    デフォルトでは無効期間（未来のvalid_from）にしておき、各テストで
    _ensure_discount を再度呼んで期間を書き換える。
    """
    sku_id = "AUTOTEST-POS-SKU-SCHEDULED-DISCOUNT"
    async with AsyncSessionLocal() as db:
        await _ensure_sku(db, sku_id, "4900000000232", stock=500)
    yield sku_id


async def test_checkout_success(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 2}],
            "client_total": 2200,
            "payment_method": "CASH",
            "amount_tendered": 3000,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subtotal_ex_tax"] == 2000
    assert body["discount_total"] == 0
    assert body["tax_amount"] == 200
    assert body["total_inc_tax"] == 2200
    assert body["change"] == 800
    assert body["transaction_id"].startswith("TX-")

    async with AsyncSessionLocal() as db:
        sku = await db.get(Sku, main_sku)
        assert sku.store_stock == 498


async def test_checkout_tax_is_floored(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    # 999 * 1 * 10% = 99.9 -> 切り捨てで 99 円になることを検証。
    async with AsyncSessionLocal() as db:
        product = await db.get(Product, PRODUCT_ID)
        original_price = product.default_price
        product.default_price = 999
        await db.commit()

    try:
        response = await client.post(
            "/api/v1/pos/checkout",
            headers=auth_headers,
            json={
                "items": [{"sku_id": main_sku, "quantity": 1}],
                "client_total": 1098,
                "payment_method": "CASH",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["tax_amount"] == 99
        assert body["total_inc_tax"] == 1098
    finally:
        async with AsyncSessionLocal() as db:
            product = await db.get(Product, PRODUCT_ID)
            product.default_price = original_price
            await db.commit()


async def test_checkout_price_mismatch_returns_422(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 2}],
            "client_total": 999999,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "PRICE_MISMATCH"
    assert detail["current_total"] == 2200

    async with AsyncSessionLocal() as db:
        sku = await db.get(Sku, main_sku)
        assert sku.store_stock == 500  # ロールバックされ在庫は変動しない


async def test_checkout_insufficient_payment_returns_422(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 2}],
            "client_total": 2200,
            "payment_method": "CASH",
            "amount_tendered": 2000,
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "INSUFFICIENT_PAYMENT"
    assert detail["required"] == 2200
    assert detail["tendered"] == 2000

    async with AsyncSessionLocal() as db:
        sku = await db.get(Sku, main_sku)
        assert sku.store_stock == 500  # ロールバックされ在庫は変動しない


async def test_checkout_exact_payment_gives_zero_change(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 2}],
            "client_total": 2200,
            "payment_method": "CASH",
            "amount_tendered": 2200,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["change"] == 0


async def test_checkout_non_cash_ignores_amount_tendered(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    # CASH以外の支払方法では預かり金額の概念がないため、amount_tendered が
    # 合計未満でもエラーにならない。
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 2}],
            "client_total": 2200,
            "payment_method": "CREDIT_CARD",
            "amount_tendered": 0,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["change"] == 0


async def test_checkout_insufficient_stock_returns_409(
    client: AsyncClient, auth_headers: dict[str, str], low_stock_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": low_stock_sku, "quantity": 2}],
            "client_total": 2200,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "INSUFFICIENT_STOCK"
    assert detail["available"] == 1


async def test_checkout_unknown_sku_returns_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": "NO-SUCH-SKU", "quantity": 1}],
            "client_total": 1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SKU_NOT_FOUND"


async def test_checkout_unknown_member_returns_404(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 1}],
            "client_total": 1100,
            "payment_method": "CASH",
            "member_id": "NO-SUCH-MEMBER",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "MEMBER_NOT_FOUND"


async def test_checkout_requires_authentication(client: AsyncClient, main_sku: str) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        json={
            "items": [{"sku_id": main_sku, "quantity": 1}],
            "client_total": 1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 401


async def test_checkout_sku_discount_takes_priority_over_product_discount(
    client: AsyncClient, auth_headers: dict[str, str], discount_priority_skus: str
) -> None:
    # SKU値引き(10%)の方がPRODUCT値引き(50%)より低額でも、優先順位規則により
    # SKU値引きが適用されなければならない（設計仕様書8節：SKU > 商品ID > 会員）。
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": discount_priority_skus, "quantity": 1}],
            "client_total": 990,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["discount_total"] == 100  # 1000 * 10%
    assert body["total_inc_tax"] == 990  # (1000-100) * 1.10


async def test_checkout_amount_discount_is_applied_per_unit(
    client: AsyncClient, auth_headers: dict[str, str], amount_discount_sku: str
) -> None:
    # BE-U11: discount_type=AMOUNT は「1点あたりの値引き額」として数量倍される。
    # 単価1000円、AMOUNT値引き300円、数量2 -> 値引き合計 300*2=600円
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": amount_discount_sku, "quantity": 2}],
            "client_total": 1540,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subtotal_ex_tax"] == 2000  # 1000 * 2
    assert body["discount_total"] == 600  # 300 * 2
    assert body["tax_amount"] == 140  # (2000-600) * 10%
    assert body["total_inc_tax"] == 1540


async def test_checkout_amount_discount_does_not_exceed_line_subtotal(
    client: AsyncClient, auth_headers: dict[str, str], amount_discount_sku: str
) -> None:
    # AMOUNT値引きが単価を超えていても、値引き額は行小計でクランプされ
    # マイナスの税抜金額にはならない（pos_service._compute_discount_amount）。
    async with AsyncSessionLocal() as db:
        await _ensure_discount(
            db,
            "AUTOTEST-POS-DISCOUNT-AMOUNT",
            DiscountTargetTypeEnum.SKU,
            {"sku_id": amount_discount_sku},
            value="9999.00",
            priority=1,
            discount_type=DiscountTypeEnum.AMOUNT,
        )
    try:
        response = await client.post(
            "/api/v1/pos/checkout",
            headers=auth_headers,
            json={
                "items": [{"sku_id": amount_discount_sku, "quantity": 1}],
                "client_total": 0,
                "payment_method": "CASH",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["discount_total"] == 1000  # 単価(1000)でクランプ
        assert body["total_inc_tax"] == 0
    finally:
        async with AsyncSessionLocal() as db:
            await _ensure_discount(
                db,
                "AUTOTEST-POS-DISCOUNT-AMOUNT",
                DiscountTargetTypeEnum.SKU,
                {"sku_id": amount_discount_sku},
                value="300.00",
                priority=1,
                discount_type=DiscountTypeEnum.AMOUNT,
            )


async def test_checkout_discount_not_yet_valid_is_not_applied(
    client: AsyncClient, auth_headers: dict[str, str], scheduled_discount_sku: str
) -> None:
    # IT-13: valid_from が未来の値引きは適用されない。
    future = datetime(2999, 1, 1)
    async with AsyncSessionLocal() as db:
        await _ensure_discount(
            db,
            "AUTOTEST-POS-DISCOUNT-SCHEDULED",
            DiscountTargetTypeEnum.SKU,
            {"sku_id": scheduled_discount_sku},
            value="10.00",
            priority=1,
            valid_from=future,
            valid_to=None,
        )
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": scheduled_discount_sku, "quantity": 1}],
            "client_total": 1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["discount_total"] == 0
    assert body["total_inc_tax"] == 1100


async def test_checkout_discount_within_valid_window_is_applied(
    client: AsyncClient, auth_headers: dict[str, str], scheduled_discount_sku: str
) -> None:
    # IT-13: 現在時刻が valid_from〜valid_to の範囲内であれば適用される。
    async with AsyncSessionLocal() as db:
        await _ensure_discount(
            db,
            "AUTOTEST-POS-DISCOUNT-SCHEDULED",
            DiscountTargetTypeEnum.SKU,
            {"sku_id": scheduled_discount_sku},
            value="10.00",
            priority=1,
            valid_from=EPOCH,
            valid_to=None,
        )
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": scheduled_discount_sku, "quantity": 1}],
            "client_total": 990,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["discount_total"] == 100
    assert body["total_inc_tax"] == 990


async def test_checkout_discount_after_valid_to_is_not_applied(
    client: AsyncClient, auth_headers: dict[str, str], scheduled_discount_sku: str
) -> None:
    # IT-13: valid_to を過去に設定すると期限切れとして適用されない。
    past = datetime(2000, 1, 1)
    async with AsyncSessionLocal() as db:
        await _ensure_discount(
            db,
            "AUTOTEST-POS-DISCOUNT-SCHEDULED",
            DiscountTargetTypeEnum.SKU,
            {"sku_id": scheduled_discount_sku},
            value="10.00",
            priority=1,
            valid_from=EPOCH,
            valid_to=past,
        )
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": scheduled_discount_sku, "quantity": 1}],
            "client_total": 1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["discount_total"] == 0
    assert body["total_inc_tax"] == 1100


async def test_checkout_rejects_more_than_100_items(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 1} for _ in range(101)],
            "client_total": 1,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 422


async def test_checkout_rejects_quantity_over_99(
    client: AsyncClient, auth_headers: dict[str, str], main_sku: str
) -> None:
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": main_sku, "quantity": 100}],
            "client_total": 1,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 422
