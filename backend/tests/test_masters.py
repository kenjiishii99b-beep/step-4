from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import (
    ColorMaster,
    DiscountMaster,
    Product,
    RoleEnum,
    SizeMaster,
    Sku,
    Staff,
    TaxRate,
)

PASSWORD = "masters-battery-staple"

ADMIN_ID = "AUTOTEST-MASTERS-ADMIN"
MANAGER_ID = "AUTOTEST-MASTERS-MANAGER"
STAFF_ID = "AUTOTEST-MASTERS-STAFF"

PRODUCT_ID = "AUTOTEST-MASTERS-PRODUCT"
SIZE_SYSTEM_ID = "AUTOTEST-MASTERS-SIZE"
COLOR_SYSTEM_ID = "AUTOTEST-MASTERS-COLOR"
SKU_ID = "AUTOTEST-MASTERS-SKU"

EPOCH = "1970-01-01T00:00:00"


async def _create_actor(staff_id: str, role: RoleEnum) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            Staff(
                staff_id=staff_id,
                staff_name=f"Test {staff_id}",
                password_hash=hash_password(PASSWORD),
                role=role,
                is_active=True,
            )
        )
        await db.commit()


async def _delete_actor(staff_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Staff).where(Staff.staff_id == staff_id))
        await db.commit()


@pytest.fixture
async def admin_headers(client: AsyncClient) -> AsyncGenerator[dict[str, str], None]:
    await _create_actor(ADMIN_ID, RoleEnum.ADMIN)
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": ADMIN_ID, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    yield {"Authorization": f"Bearer {response.json()['access_token']}"}
    await _delete_actor(ADMIN_ID)


@pytest.fixture
async def manager_headers(client: AsyncClient) -> AsyncGenerator[dict[str, str], None]:
    await _create_actor(MANAGER_ID, RoleEnum.MANAGER)
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": MANAGER_ID, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    yield {"Authorization": f"Bearer {response.json()['access_token']}"}
    await _delete_actor(MANAGER_ID)


@pytest.fixture
async def staff_headers(client: AsyncClient) -> AsyncGenerator[dict[str, str], None]:
    await _create_actor(STAFF_ID, RoleEnum.STAFF)
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": STAFF_ID, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    yield {"Authorization": f"Bearer {response.json()['access_token']}"}
    await _delete_actor(STAFF_ID)


@pytest.fixture(scope="module", autouse=True)
async def product_and_sku() -> AsyncGenerator[None, None]:
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
                    product_name="Autotest Masters Tee",
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
                    barcode_ean13="4900000000102",
                    size_system_id=SIZE_SYSTEM_ID,
                    size_code="M",
                    color_system_id=COLOR_SYSTEM_ID,
                    color_code="BLK",
                    store_stock=100,
                )
            )
            await db.commit()
    yield


async def test_manager_can_upsert_sku_discount(
    client: AsyncClient, manager_headers: dict[str, str]
) -> None:
    discount_id = "AUTOTEST-MASTERS-DISCOUNT-SKU"
    try:
        response = await client.put(
            "/api/v1/masters/discounts",
            headers=manager_headers,
            json={
                "discount_id": discount_id,
                "target_type": "SKU",
                "sku_id": SKU_ID,
                "discount_type": "RATE",
                "discount_value": "10.00",
                "valid_from": EPOCH,
                "priority": 1,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["discount_id"] == discount_id
        assert body["sku_id"] == SKU_ID
        assert body["product_id"] is None

        # 同じ discount_id で再送すると更新される（upsert）。
        response2 = await client.put(
            "/api/v1/masters/discounts",
            headers=manager_headers,
            json={
                "discount_id": discount_id,
                "target_type": "SKU",
                "sku_id": SKU_ID,
                "discount_type": "RATE",
                "discount_value": "20.00",
                "valid_from": EPOCH,
                "priority": 1,
            },
        )
        assert response2.status_code == 200, response2.text
        assert response2.json()["discount_value"] == "20.00"

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DiscountMaster).where(DiscountMaster.discount_id == discount_id)
            )
            assert len(result.scalars().all()) == 1
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(DiscountMaster).where(DiscountMaster.discount_id == discount_id)
            )
            await db.commit()


async def test_discount_target_type_mismatch_is_rejected(
    client: AsyncClient, manager_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/v1/masters/discounts",
        headers=manager_headers,
        json={
            "discount_id": "AUTOTEST-MASTERS-DISCOUNT-BAD",
            "target_type": "SKU",
            "product_id": PRODUCT_ID,
            "discount_type": "RATE",
            "discount_value": "10.00",
            "valid_from": EPOCH,
            "priority": 1,
        },
    )
    assert response.status_code == 422


async def test_discount_for_unknown_sku_returns_404(
    client: AsyncClient, manager_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/v1/masters/discounts",
        headers=manager_headers,
        json={
            "discount_id": "AUTOTEST-MASTERS-DISCOUNT-NOSKU",
            "target_type": "SKU",
            "sku_id": "NO-SUCH-SKU",
            "discount_type": "RATE",
            "discount_value": "10.00",
            "valid_from": EPOCH,
            "priority": 1,
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SKU_NOT_FOUND"


async def test_discount_rate_over_100_is_rejected(
    client: AsyncClient, manager_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/v1/masters/discounts",
        headers=manager_headers,
        json={
            "discount_id": "AUTOTEST-MASTERS-DISCOUNT-OVER",
            "target_type": "SKU",
            "sku_id": SKU_ID,
            "discount_type": "RATE",
            "discount_value": "150.00",
            "valid_from": EPOCH,
            "priority": 1,
        },
    )
    assert response.status_code == 422


async def test_staff_cannot_manage_discounts(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/v1/masters/discounts",
        headers=staff_headers,
        json={
            "discount_id": "AUTOTEST-MASTERS-DISCOUNT-DENIED",
            "target_type": "SKU",
            "sku_id": SKU_ID,
            "discount_type": "RATE",
            "discount_value": "10.00",
            "valid_from": EPOCH,
            "priority": 1,
        },
    )
    assert response.status_code == 403


async def test_admin_can_upsert_tax_rate(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    tax_rate_id = "AUTOTEST-MASTERS-TAX"
    try:
        response = await client.put(
            "/api/v1/masters/tax-rates",
            headers=admin_headers,
            json={"tax_rate_id": tax_rate_id, "tax_rate": "8.00", "valid_from": EPOCH},
        )
        assert response.status_code == 200, response.text
        assert response.json()["tax_rate"] == "8.00"

        response2 = await client.put(
            "/api/v1/masters/tax-rates",
            headers=admin_headers,
            json={"tax_rate_id": tax_rate_id, "tax_rate": "10.00", "valid_from": EPOCH},
        )
        assert response2.status_code == 200, response2.text
        assert response2.json()["tax_rate"] == "10.00"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(TaxRate).where(TaxRate.tax_rate_id == tax_rate_id))
            await db.commit()


async def test_manager_cannot_manage_tax_rates(
    client: AsyncClient, manager_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/v1/masters/tax-rates",
        headers=manager_headers,
        json={
            "tax_rate_id": "AUTOTEST-MASTERS-TAX-DENIED",
            "tax_rate": "10.00",
            "valid_from": EPOCH,
        },
    )
    assert response.status_code == 403


async def test_tax_rate_valid_to_before_valid_from_is_rejected(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/v1/masters/tax-rates",
        headers=admin_headers,
        json={
            "tax_rate_id": "AUTOTEST-MASTERS-TAX-BADWINDOW",
            "tax_rate": "10.00",
            "valid_from": "2026-01-01T00:00:00",
            "valid_to": "2025-01-01T00:00:00",
        },
    )
    assert response.status_code == 422


async def test_masters_require_authentication(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/masters/tax-rates",
        json={
            "tax_rate_id": "AUTOTEST-MASTERS-TAX-NOAUTH",
            "tax_rate": "10.00",
            "valid_from": EPOCH,
        },
    )
    assert response.status_code == 401
