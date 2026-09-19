from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import ColorMaster, Product, RoleEnum, SizeMaster, Sku, Staff

PASSWORD = "inventory-battery-staple"

STAFF_ID = "AUTOTEST-INV-STAFF"
MANAGER_ID = "AUTOTEST-INV-MANAGER"
PRODUCT_ID = "AUTOTEST-INV-PRODUCT"
SIZE_SYSTEM_ID = "AUTOTEST-INV-SIZE"
COLOR_SYSTEM_ID = "AUTOTEST-INV-COLOR"


async def _ensure_actor(staff_id: str, role: RoleEnum) -> None:
    # 入荷・在庫移動は inventory_histories.staff_id (ON DELETE RESTRICT) から
    # 恒久的に参照されるため、テスト用スタッフは削除せず get-or-create で
    # 再利用する（4.1節：取引履歴・マスターの物理削除禁止方針に整合）。
    async with AsyncSessionLocal() as db:
        staff = await db.get(Staff, staff_id)
        if staff is None:
            db.add(
                Staff(
                    staff_id=staff_id,
                    staff_name=f"Test {staff_id}",
                    password_hash=hash_password(PASSWORD),
                    role=role,
                    is_active=True,
                )
            )
        else:
            staff.is_active = True
            staff.role = role
        await db.commit()


async def _login(client: AsyncClient, staff_id: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": staff_id, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="module", autouse=True)
async def actors() -> AsyncGenerator[None, None]:
    await _ensure_actor(STAFF_ID, RoleEnum.STAFF)
    await _ensure_actor(MANAGER_ID, RoleEnum.MANAGER)
    yield


@pytest.fixture
async def staff_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, STAFF_ID)


@pytest.fixture
async def manager_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, MANAGER_ID)


@pytest.fixture(scope="module", autouse=True)
async def product_master() -> AsyncGenerator[None, None]:
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
                    product_name="Autotest Inventory Tee",
                    category="TOPS",
                    default_price=1000,
                )
            )
            await db.commit()
    yield


@pytest.fixture
async def sku_with_stock() -> AsyncGenerator[str, None]:
    sku_id = "AUTOTEST-INV-SKU"
    async with AsyncSessionLocal() as db:
        sku = await db.get(Sku, sku_id)
        if sku is None:
            db.add(
                Sku(
                    sku_id=sku_id,
                    product_id=PRODUCT_ID,
                    barcode_ean13="4900000000201",
                    size_system_id=SIZE_SYSTEM_ID,
                    size_code="M",
                    color_system_id=COLOR_SYSTEM_ID,
                    color_code="BLK",
                    store_stock=10,
                    warehouse_stock=20,
                )
            )
        else:
            sku.store_stock = 10
            sku.warehouse_stock = 20
        await db.commit()
    yield sku_id


async def test_get_inventory_status(
    client: AsyncClient, staff_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.get(f"/api/v1/inventory/{sku_with_stock}", headers=staff_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "sku_id": sku_with_stock,
        "store_stock": 10,
        "warehouse_stock": 20,
    }


async def test_get_inventory_status_unknown_sku_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/inventory/NO-SUCH-SKU", headers=staff_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SKU_NOT_FOUND"


async def test_inventory_status_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/inventory/whatever")
    assert response.status_code == 401


async def test_staff_can_receive_stock_to_store(
    client: AsyncClient, staff_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.post(
        "/api/v1/inventory/receipt",
        headers=staff_headers,
        json={"sku_id": sku_with_stock, "location": "STORE", "quantity": 5},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "sku_id": sku_with_stock,
        "store_stock": 15,
        "warehouse_stock": 20,
    }


async def test_staff_can_receive_stock_to_warehouse(
    client: AsyncClient, staff_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.post(
        "/api/v1/inventory/receipt",
        headers=staff_headers,
        json={"sku_id": sku_with_stock, "location": "WAREHOUSE", "quantity": 5},
    )
    assert response.status_code == 200, response.text
    assert response.json()["warehouse_stock"] == 25


async def test_receipt_defaults_to_store_location(
    client: AsyncClient, staff_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.post(
        "/api/v1/inventory/receipt",
        headers=staff_headers,
        json={"sku_id": sku_with_stock, "quantity": 3},
    )
    assert response.status_code == 200, response.text
    assert response.json()["store_stock"] == 13


async def test_receipt_unknown_sku_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/inventory/receipt",
        headers=staff_headers,
        json={"sku_id": "NO-SUCH-SKU", "quantity": 1},
    )
    assert response.status_code == 404


async def test_manager_can_transfer_from_warehouse_to_store(
    client: AsyncClient, manager_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.post(
        "/api/v1/inventory/transfer",
        headers=manager_headers,
        json={
            "sku_id": sku_with_stock,
            "from_location": "WAREHOUSE",
            "to_location": "STORE",
            "quantity": 8,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "sku_id": sku_with_stock,
        "store_stock": 18,
        "warehouse_stock": 12,
    }


async def test_transfer_more_than_available_returns_409(
    client: AsyncClient, manager_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.post(
        "/api/v1/inventory/transfer",
        headers=manager_headers,
        json={
            "sku_id": sku_with_stock,
            "from_location": "STORE",
            "to_location": "WAREHOUSE",
            "quantity": 999,
        },
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "INSUFFICIENT_STOCK"
    assert detail["available"] == 10


async def test_transfer_same_location_is_rejected_by_schema(
    client: AsyncClient, manager_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.post(
        "/api/v1/inventory/transfer",
        headers=manager_headers,
        json={
            "sku_id": sku_with_stock,
            "from_location": "STORE",
            "to_location": "STORE",
            "quantity": 1,
        },
    )
    assert response.status_code == 422


async def test_staff_cannot_transfer_stock(
    client: AsyncClient, staff_headers: dict[str, str], sku_with_stock: str
) -> None:
    response = await client.post(
        "/api/v1/inventory/transfer",
        headers=staff_headers,
        json={
            "sku_id": sku_with_stock,
            "from_location": "STORE",
            "to_location": "WAREHOUSE",
            "quantity": 1,
        },
    )
    assert response.status_code == 403


async def test_transfer_unknown_sku_returns_404(
    client: AsyncClient, manager_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/inventory/transfer",
        headers=manager_headers,
        json={
            "sku_id": "NO-SUCH-SKU",
            "from_location": "STORE",
            "to_location": "WAREHOUSE",
            "quantity": 1,
        },
    )
    assert response.status_code == 404
