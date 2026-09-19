from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import Product, RoleEnum, Sku, Staff

PASSWORD = "products-battery-staple"

MANAGER_ID = "AUTOTEST-PRODUCTS-MANAGER"
STAFF_ID = "AUTOTEST-PRODUCTS-STAFF"


async def _ensure_actor(staff_id: str, role: RoleEnum) -> None:
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
    await _ensure_actor(MANAGER_ID, RoleEnum.MANAGER)
    await _ensure_actor(STAFF_ID, RoleEnum.STAFF)
    yield


@pytest.fixture
async def manager_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, MANAGER_ID)


@pytest.fixture
async def staff_headers(client: AsyncClient) -> dict[str, str]:
    return await _login(client, STAFF_ID)


@pytest.fixture
async def new_product_id() -> AsyncGenerator[str, None]:
    pid = "AUTOTEST-NEWPRODUCT-1"
    yield pid
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Sku).where(Sku.product_id == pid))
        await db.execute(delete(Product).where(Product.product_id == pid))
        await db.commit()


async def test_manager_can_create_product_with_skus(
    client: AsyncClient, manager_headers: dict[str, str], new_product_id: str
) -> None:
    response = await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "New Season Tee",
            "category": "TOPS",
            "default_price": 2000,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-M-BLK",
                    "barcode_ean13": "4901234500019",
                    "size_system_id": "STANDARD",
                    "size_code": "M",
                    "color_system_id": "BASIC",
                    "color_code": "BLK",
                    "store_stock": 10,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product_id"] == new_product_id
    assert len(body["skus"]) == 1
    assert body["skus"][0]["store_stock"] == 10


async def test_create_product_duplicate_id_returns_409(
    client: AsyncClient, manager_headers: dict[str, str], new_product_id: str
) -> None:
    payload = {
        "product_id": new_product_id,
        "product_name": "Dup",
        "category": "TOPS",
        "default_price": 1000,
    }
    first = await client.post("/api/v1/admin/products", headers=manager_headers, json=payload)
    assert first.status_code == 200, first.text

    second = await client.post("/api/v1/admin/products", headers=manager_headers, json=payload)
    assert second.status_code == 409
    assert second.json()["detail"]["error"] == "PRODUCT_ALREADY_EXISTS"


async def test_create_product_with_unknown_size_master_returns_404(
    client: AsyncClient, manager_headers: dict[str, str], new_product_id: str
) -> None:
    response = await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Bad Size",
            "category": "TOPS",
            "default_price": 1000,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-BADSIZE",
                    "barcode_ean13": "4901234500026",
                    "size_system_id": "NO-SUCH-SYSTEM",
                    "size_code": "M",
                    "color_system_id": "BASIC",
                    "color_code": "BLK",
                }
            ],
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SIZE_MASTER_NOT_FOUND"


async def test_create_product_duplicate_barcode_returns_409(
    client: AsyncClient, manager_headers: dict[str, str], new_product_id: str
) -> None:
    shared_barcode = "4901234500064"
    first = await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Barcode Owner",
            "category": "TOPS",
            "default_price": 1000,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-OWNER",
                    "barcode_ean13": shared_barcode,
                    "size_system_id": "STANDARD",
                    "size_code": "M",
                    "color_system_id": "BASIC",
                    "color_code": "BLK",
                }
            ],
        },
    )
    assert first.status_code == 200, first.text

    response = await client.put(
        f"/api/v1/admin/products/{new_product_id}",
        headers=manager_headers,
        json={
            "product_name": "Barcode Owner",
            "category": "TOPS",
            "default_price": 1000,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-CLASH",
                    "barcode_ean13": shared_barcode,
                    "size_system_id": "STANDARD",
                    "size_code": "L",
                    "color_system_id": "BASIC",
                    "color_code": "WHT",
                }
            ],
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "BARCODE_ALREADY_EXISTS"


async def test_create_product_duplicate_size_color_returns_409(
    client: AsyncClient, manager_headers: dict[str, str], new_product_id: str
) -> None:
    """要件2.2: 同一商品内でサイズ・カラーの組み合わせは一意でなければならない。"""
    first = await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Variant Owner",
            "category": "TOPS",
            "default_price": 1000,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-OWNER",
                    "barcode_ean13": "4901234500071",
                    "size_system_id": "STANDARD",
                    "size_code": "M",
                    "color_system_id": "BASIC",
                    "color_code": "BLK",
                }
            ],
        },
    )
    assert first.status_code == 200, first.text

    response = await client.put(
        f"/api/v1/admin/products/{new_product_id}",
        headers=manager_headers,
        json={
            "product_name": "Variant Owner",
            "category": "TOPS",
            "default_price": 1000,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-CLASH",
                    "barcode_ean13": "4901234500088",
                    "size_system_id": "STANDARD",
                    "size_code": "M",
                    "color_system_id": "BASIC",
                    "color_code": "BLK",
                }
            ],
        },
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "SKU_VARIANT_ALREADY_EXISTS"
    assert detail["size_code"] == "M"
    assert detail["color_code"] == "BLK"


async def test_staff_cannot_create_product(
    client: AsyncClient, staff_headers: dict[str, str], new_product_id: str
) -> None:
    response = await client.post(
        "/api/v1/admin/products",
        headers=staff_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Denied",
            "category": "TOPS",
            "default_price": 1000,
        },
    )
    assert response.status_code == 403


async def test_get_product_returns_full_detail(
    client: AsyncClient,
    manager_headers: dict[str, str],
    staff_headers: dict[str, str],
    new_product_id: str,
) -> None:
    await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Detail Tee",
            "category": "TOPS",
            "default_price": 1500,
        },
    )
    response = await client.get(f"/api/v1/products/{new_product_id}", headers=staff_headers)
    assert response.status_code == 200, response.text
    assert response.json()["product_name"] == "Detail Tee"


async def test_get_unknown_product_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/products/NO-SUCH-PRODUCT", headers=staff_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "PRODUCT_NOT_FOUND"


async def test_manager_can_update_product_and_add_new_sku(
    client: AsyncClient, manager_headers: dict[str, str], new_product_id: str
) -> None:
    await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Original Name",
            "category": "TOPS",
            "default_price": 1000,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-M-BLK",
                    "barcode_ean13": "4901234500033",
                    "size_system_id": "STANDARD",
                    "size_code": "M",
                    "color_system_id": "BASIC",
                    "color_code": "BLK",
                    "store_stock": 5,
                }
            ],
        },
    )

    response = await client.put(
        f"/api/v1/admin/products/{new_product_id}",
        headers=manager_headers,
        json={
            "product_name": "Updated Name",
            "category": "TOPS",
            "default_price": 1200,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-M-BLK",
                    "barcode_ean13": "4901234500033",
                    "size_system_id": "STANDARD",
                    "size_code": "M",
                    "color_system_id": "BASIC",
                    "color_code": "BLK",
                    "store_stock": 999,  # 既存SKUなので無視され、5のまま維持される想定
                },
                {
                    "sku_id": f"{new_product_id}-L-WHT",
                    "barcode_ean13": "4901234500040",
                    "size_system_id": "STANDARD",
                    "size_code": "L",
                    "color_system_id": "BASIC",
                    "color_code": "WHT",
                    "store_stock": 7,
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product_name"] == "Updated Name"
    assert body["default_price"] == 1200
    skus_by_id = {sku["sku_id"]: sku for sku in body["skus"]}
    assert len(skus_by_id) == 2
    assert skus_by_id[f"{new_product_id}-M-BLK"]["store_stock"] == 5  # 既存SKUは変更されない
    assert skus_by_id[f"{new_product_id}-L-WHT"]["store_stock"] == 7  # 新規SKUは追加される


async def test_update_unknown_product_returns_404(
    client: AsyncClient, manager_headers: dict[str, str]
) -> None:
    response = await client.put(
        "/api/v1/admin/products/NO-SUCH-PRODUCT",
        headers=manager_headers,
        json={"product_name": "X", "category": "TOPS", "default_price": 1000},
    )
    assert response.status_code == 404


async def test_lookup_sku_by_barcode(
    client: AsyncClient,
    manager_headers: dict[str, str],
    staff_headers: dict[str, str],
    new_product_id: str,
) -> None:
    barcode = "4901234500057"
    await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Scan Me",
            "category": "TOPS",
            "default_price": 800,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-SCAN",
                    "barcode_ean13": barcode,
                    "size_system_id": "STANDARD",
                    "size_code": "S",
                    "color_system_id": "BASIC",
                    "color_code": "RED",
                    "store_stock": 3,
                }
            ],
        },
    )
    response = await client.get(f"/api/v1/skus/barcode/{barcode}", headers=staff_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product_name"] == "Scan Me"
    assert body["reference_price"] == 800
    assert body["store_stock"] == 3


async def test_lookup_sku_by_product_size_color(
    client: AsyncClient,
    manager_headers: dict[str, str],
    staff_headers: dict[str, str],
    new_product_id: str,
) -> None:
    """要件3.1: バーコード読取エラー時の手入力フォールバック（商品ID+サイズ+カラー）。"""
    await client.post(
        "/api/v1/admin/products",
        headers=manager_headers,
        json={
            "product_id": new_product_id,
            "product_name": "Manual Entry Me",
            "category": "TOPS",
            "default_price": 900,
            "skus": [
                {
                    "sku_id": f"{new_product_id}-MANUAL",
                    "barcode_ean13": "4901234500095",
                    "size_system_id": "STANDARD",
                    "size_code": "L",
                    "color_system_id": "BASIC",
                    "color_code": "NVY",
                    "store_stock": 7,
                }
            ],
        },
    )
    response = await client.get(
        "/api/v1/skus/lookup",
        params={"product_id": new_product_id, "size_code": "L", "color_code": "NVY"},
        headers=staff_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product_name"] == "Manual Entry Me"
    assert body["reference_price"] == 900
    assert body["store_stock"] == 7


async def test_lookup_unknown_product_size_color_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/skus/lookup",
        params={"product_id": "NOPE", "size_code": "M", "color_code": "BLK"},
        headers=staff_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SKU_NOT_FOUND"


async def test_lookup_unknown_barcode_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/skus/barcode/0000000000000", headers=staff_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SKU_NOT_FOUND"


async def test_products_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/products/whatever")
    assert response.status_code == 401
