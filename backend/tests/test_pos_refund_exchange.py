from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import ColorMaster, Product, RoleEnum, SizeMaster, Sku, Staff, TaxRate

PASSWORD = "refund-battery-staple"

PRODUCT_ID = "AUTOTEST-REFUND-PRODUCT"
EXCHANGE_PRODUCT_ID = "AUTOTEST-REFUND-EXCHANGE-PRODUCT"
STAFF_ID = "AUTOTEST-REFUND-STAFF"
TAX_RATE_ID = "AUTOTEST-REFUND-TAX"
SIZE_SYSTEM_ID = "AUTOTEST-REFUND-SIZE"
COLOR_SYSTEM_ID = "AUTOTEST-REFUND-COLOR"

EPOCH = datetime(1970, 1, 1)


async def _ensure_size_master(db) -> None:
    if await db.get(SizeMaster, (SIZE_SYSTEM_ID, "M")) is None:
        db.add(SizeMaster(size_system_id=SIZE_SYSTEM_ID, size_code="M", size_name="M"))
        await db.commit()


async def _ensure_color_master(db) -> None:
    if await db.get(ColorMaster, (COLOR_SYSTEM_ID, "BLK")) is None:
        db.add(ColorMaster(color_system_id=COLOR_SYSTEM_ID, color_code="BLK", color_name="Black"))
        await db.commit()


async def _ensure_product(db, product_id: str, default_price: int = 1000) -> None:
    if await db.get(Product, product_id) is None:
        db.add(
            Product(
                product_id=product_id,
                product_name="Autotest Refund Tee",
                category="TOPS",
                default_price=default_price,
            )
        )
        await db.commit()


async def _ensure_sku(db, sku_id: str, barcode: str, stock: int, product_id: str) -> None:
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
                staff_name="Autotest Refund Cashier",
                password_hash=hash_password(PASSWORD),
                role=RoleEnum.STAFF,
                is_active=True,
            )
        )
    else:
        staff.is_active = True
    await db.commit()


async def _ensure_tax_rate(db) -> None:
    if await db.get(TaxRate, TAX_RATE_ID) is None:
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


@pytest.fixture(scope="module", autouse=True)
async def refund_master_data() -> AsyncGenerator[None, None]:
    async with AsyncSessionLocal() as db:
        await _ensure_size_master(db)
        await _ensure_color_master(db)
        await _ensure_product(db, PRODUCT_ID)
        await _ensure_product(db, EXCHANGE_PRODUCT_ID)
        await _ensure_staff(db)
        await _ensure_tax_rate(db)
    yield


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": STAFF_ID, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _checkout(
    client: AsyncClient, auth_headers: dict[str, str], sku_id: str, qty: int, unit_price: int
):
    total = unit_price * qty
    tax = total // 10
    response = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": sku_id, "quantity": qty}],
            "client_total": total + tax,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
async def sold_sku() -> AsyncGenerator[dict, None]:
    """1着1000円の商品を3点、事前に会計済みにしておく共通フィクスチャ。"""
    sku_id = "AUTOTEST-REFUND-SKU-SOLD"
    async with AsyncSessionLocal() as db:
        await _ensure_sku(db, sku_id, "4900000000041", stock=100, product_id=PRODUCT_ID)
    yield {"sku_id": sku_id, "unit_price": 1000}


@pytest.fixture
async def exchange_target_sku() -> AsyncGenerator[str, None]:
    sku_id = "AUTOTEST-REFUND-SKU-EXCHANGE-TARGET"
    async with AsyncSessionLocal() as db:
        await _ensure_sku(db, sku_id, "4900000000058", stock=100, product_id=EXCHANGE_PRODUCT_ID)
    yield sku_id


async def test_full_return_refunds_entire_amount(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict
) -> None:
    sale = await _checkout(client, auth_headers, sold_sku["sku_id"], 2, sold_sku["unit_price"])
    parent_id = sale["transaction_id"]

    async with AsyncSessionLocal() as db:
        sku = await db.get(Sku, sold_sku["sku_id"])
        stock_before = sku.store_stock

    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 2}],
            "client_total": -2200,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tx_type"] == "RETURN"
    assert body["parent_transaction_id"] == parent_id
    assert body["total_inc_tax"] == -2200
    assert body["tax_amount"] == -200
    assert body["subtotal_ex_tax"] == -2000

    async with AsyncSessionLocal() as db:
        sku = await db.get(Sku, sold_sku["sku_id"])
        assert sku.store_stock == stock_before + 2


async def test_partial_return_then_exceeding_remaining_is_rejected(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict
) -> None:
    sale = await _checkout(client, auth_headers, sold_sku["sku_id"], 3, sold_sku["unit_price"])
    parent_id = sale["transaction_id"]

    first = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 2}],
            "client_total": -2200,
            "payment_method": "CASH",
        },
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 2}],
            "client_total": -2200,
            "payment_method": "CASH",
        },
    )
    assert second.status_code == 422
    detail = second.json()["detail"]
    assert detail["error"] == "RETURN_QUANTITY_EXCEEDED"
    assert detail["remaining"] == 1


async def test_return_rejects_sku_not_in_original_transaction(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict, exchange_target_sku: str
) -> None:
    sale = await _checkout(client, auth_headers, sold_sku["sku_id"], 1, sold_sku["unit_price"])
    parent_id = sale["transaction_id"]

    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "RETURN",
            "return_items": [{"sku_id": exchange_target_sku, "quantity": 1}],
            "client_total": -1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "RETURN_ITEM_NOT_IN_ORIGINAL_TRANSACTION"


async def test_parent_transaction_not_found(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict
) -> None:
    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": "TX-NO-SUCH-TRANSACTION",
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "client_total": -1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "PARENT_TRANSACTION_NOT_FOUND"


async def test_cannot_return_against_a_return(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict
) -> None:
    sale = await _checkout(client, auth_headers, sold_sku["sku_id"], 1, sold_sku["unit_price"])
    parent_id = sale["transaction_id"]

    refund = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "client_total": -1100,
            "payment_method": "CASH",
        },
    )
    assert refund.status_code == 200, refund.text
    refund_tx_id = refund.json()["transaction_id"]

    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": refund_tx_id,
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "client_total": -1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "PARENT_TRANSACTION_NOT_ELIGIBLE"


async def test_exchange_for_pricier_item_charges_the_difference(
    client: AsyncClient,
    auth_headers: dict[str, str],
    sold_sku: dict,
    exchange_target_sku: str,
) -> None:
    # 交換先商品を通常価格より高く設定し、差額請求になることを確認する。
    async with AsyncSessionLocal() as db:
        product = await db.get(Product, EXCHANGE_PRODUCT_ID)
        product.default_price = 1500
        await db.commit()

    sale = await _checkout(client, auth_headers, sold_sku["sku_id"], 1, sold_sku["unit_price"])
    parent_id = sale["transaction_id"]

    async with AsyncSessionLocal() as db:
        old_sku = await db.get(Sku, sold_sku["sku_id"])
        new_sku = await db.get(Sku, exchange_target_sku)
        old_stock_before = old_sku.store_stock
        new_stock_before = new_sku.store_stock

    # 1000円(税込1100円)を返品し、1500円(税込1650円)の商品と交換 -> 差額550円請求
    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "EXCHANGE",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "exchange_items": [{"sku_id": exchange_target_sku, "quantity": 1}],
            "client_total": 550,
            "payment_method": "CASH",
            "amount_tendered": 1000,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tx_type"] == "EXCHANGE"
    assert body["total_inc_tax"] == 550
    assert body["change"] == 450

    async with AsyncSessionLocal() as db:
        old_sku = await db.get(Sku, sold_sku["sku_id"])
        new_sku = await db.get(Sku, exchange_target_sku)
        assert old_sku.store_stock == old_stock_before + 1
        assert new_sku.store_stock == new_stock_before - 1


async def test_exchange_insufficient_payment_returns_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
    sold_sku: dict,
    exchange_target_sku: str,
) -> None:
    async with AsyncSessionLocal() as db:
        product = await db.get(Product, EXCHANGE_PRODUCT_ID)
        product.default_price = 1500
        await db.commit()

    sale = await _checkout(client, auth_headers, sold_sku["sku_id"], 1, sold_sku["unit_price"])
    parent_id = sale["transaction_id"]

    async with AsyncSessionLocal() as db:
        old_sku = await db.get(Sku, sold_sku["sku_id"])
        new_sku = await db.get(Sku, exchange_target_sku)
        old_stock_before = old_sku.store_stock
        new_stock_before = new_sku.store_stock

    # 差額550円請求のところ、預かり金額500円は不足している。
    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "EXCHANGE",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "exchange_items": [{"sku_id": exchange_target_sku, "quantity": 1}],
            "client_total": 550,
            "payment_method": "CASH",
            "amount_tendered": 500,
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "INSUFFICIENT_PAYMENT"
    assert detail["required"] == 550
    assert detail["tendered"] == 500

    async with AsyncSessionLocal() as db:
        old_sku = await db.get(Sku, sold_sku["sku_id"])
        new_sku = await db.get(Sku, exchange_target_sku)
        # ロールバックされ在庫・返品とも変動しない
        assert old_sku.store_stock == old_stock_before
        assert new_sku.store_stock == new_stock_before


async def test_pure_return_ignores_amount_tendered(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict
) -> None:
    # 返金（total_inc_tax が負）のケースでは預かり金額の過不足という概念が
    # 存在しないため、amount_tendered が指定されていてもエラーにならない。
    sale = await _checkout(client, auth_headers, sold_sku["sku_id"], 1, sold_sku["unit_price"])
    parent_id = sale["transaction_id"]

    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": parent_id,
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "client_total": -1100,
            "payment_method": "CASH",
            "amount_tendered": 0,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_inc_tax"] == -1100


async def test_refund_exchange_requires_authentication(client: AsyncClient, sold_sku: dict) -> None:
    response = await client.post(
        "/api/v1/pos/refund-exchange",
        json={
            "parent_transaction_id": "TX-DOES-NOT-MATTER",
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "client_total": -1100,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 401


async def test_return_with_exchange_items_is_rejected_by_schema(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict
) -> None:
    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": "TX-WHATEVER",
            "tx_type": "RETURN",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "exchange_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "client_total": 0,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 422


async def test_exchange_without_exchange_items_is_rejected_by_schema(
    client: AsyncClient, auth_headers: dict[str, str], sold_sku: dict
) -> None:
    response = await client.post(
        "/api/v1/pos/refund-exchange",
        headers=auth_headers,
        json={
            "parent_transaction_id": "TX-WHATEVER",
            "tx_type": "EXCHANGE",
            "return_items": [{"sku_id": sold_sku["sku_id"], "quantity": 1}],
            "client_total": 0,
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 422
