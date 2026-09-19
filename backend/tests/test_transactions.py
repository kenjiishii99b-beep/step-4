from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import ColorMaster, Product, RoleEnum, SizeMaster, Sku, Staff, TaxRate

PASSWORD = "transactions-battery-staple"

STAFF_ID = "AUTOTEST-TX-STAFF"
PRODUCT_ID = "AUTOTEST-TX-PRODUCT"
SKU_ID = "AUTOTEST-TX-SKU"
SIZE_SYSTEM_ID = "AUTOTEST-TX-SIZE"
COLOR_SYSTEM_ID = "AUTOTEST-TX-COLOR"
TAX_RATE_ID = "AUTOTEST-TX-TAX"
EPOCH = "1970-01-01T00:00:00"


@pytest.fixture(scope="module", autouse=True)
async def fixtures() -> AsyncGenerator[None, None]:
    async with AsyncSessionLocal() as db:
        if await db.get(Staff, STAFF_ID) is None:
            db.add(
                Staff(
                    staff_id=STAFF_ID,
                    staff_name="Test",
                    password_hash=hash_password(PASSWORD),
                    role=RoleEnum.STAFF,
                    is_active=True,
                )
            )
            await db.commit()
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
                    product_name="Tx Tee",
                    category="TOPS",
                    default_price=1000,
                )
            )
            await db.commit()
        if await db.get(TaxRate, TAX_RATE_ID) is None:
            db.add(
                TaxRate(
                    tax_rate_id=TAX_RATE_ID,
                    tax_rate="10.00",
                    valid_from=EPOCH,
                    is_active=True,
                )
            )
            await db.commit()
        sku = await db.get(Sku, SKU_ID)
        if sku is None:
            db.add(
                Sku(
                    sku_id=SKU_ID,
                    product_id=PRODUCT_ID,
                    barcode_ean13="4900000000980",
                    size_system_id=SIZE_SYSTEM_ID,
                    size_code="M",
                    color_system_id=COLOR_SYSTEM_ID,
                    color_code="BLK",
                    store_stock=100,
                )
            )
        else:
            sku.store_stock = 100
        await db.commit()
    yield


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": STAFF_ID, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_get_transaction_returns_items(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    checkout = await client.post(
        "/api/v1/pos/checkout",
        headers=auth_headers,
        json={
            "items": [{"sku_id": SKU_ID, "quantity": 2}],
            "client_total": 2200,
            "payment_method": "CASH",
        },
    )
    assert checkout.status_code == 200, checkout.text
    tx_id = checkout.json()["transaction_id"]

    response = await client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["transaction_id"] == tx_id
    assert body["tx_type"] == "SALE"
    assert len(body["items"]) == 1
    assert body["items"][0]["sku_id"] == SKU_ID
    assert body["items"][0]["quantity"] == 2


async def test_get_unknown_transaction_returns_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/transactions/TX-NO-SUCH", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "TRANSACTION_NOT_FOUND"


async def test_get_transaction_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/transactions/whatever")
    assert response.status_code == 401
