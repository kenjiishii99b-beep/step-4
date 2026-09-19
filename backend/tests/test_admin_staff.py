from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, verify_password
from app.models import RoleEnum, Staff

PASSWORD = "admin-battery-staple"

ADMIN_ID = "AUTOTEST-ADMIN"
MANAGER_ID = "AUTOTEST-ADMIN-MANAGER"


async def _create_staff(staff_id: str, role: RoleEnum, is_active: bool = True) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            Staff(
                staff_id=staff_id,
                staff_name=f"Test {staff_id}",
                password_hash=hash_password(PASSWORD),
                role=role,
                is_active=is_active,
            )
        )
        await db.commit()


async def _delete_staff(staff_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Staff).where(Staff.staff_id == staff_id))
        await db.commit()


@pytest.fixture
async def admin_actor() -> AsyncGenerator[str, None]:
    await _create_staff(ADMIN_ID, RoleEnum.ADMIN)
    yield ADMIN_ID
    await _delete_staff(ADMIN_ID)


@pytest.fixture
async def manager_actor() -> AsyncGenerator[str, None]:
    await _create_staff(MANAGER_ID, RoleEnum.MANAGER)
    yield MANAGER_ID
    await _delete_staff(MANAGER_ID)


async def _login(client: AsyncClient, staff_id: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": staff_id, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_admin_can_create_new_staff(client: AsyncClient, admin_actor: str) -> None:
    headers = await _login(client, admin_actor)
    new_staff_id = "AUTOTEST-ADMIN-CREATED"
    try:
        response = await client.post(
            "/api/v1/admin/staff",
            headers=headers,
            json={
                "staff_id": new_staff_id,
                "staff_name": "New Hire",
                "role": "STAFF",
                "password": "new-hire-password",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body == {
            "staff_id": new_staff_id,
            "staff_name": "New Hire",
            "role": "STAFF",
            "is_active": True,
        }

        async with AsyncSessionLocal() as db:
            staff = await db.get(Staff, new_staff_id)
            assert staff is not None
            assert verify_password("new-hire-password", staff.password_hash)
    finally:
        await _delete_staff(new_staff_id)


async def test_create_without_password_is_rejected(client: AsyncClient, admin_actor: str) -> None:
    headers = await _login(client, admin_actor)
    response = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={"staff_id": "AUTOTEST-ADMIN-NOPASS", "staff_name": "No Pass", "role": "STAFF"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "PASSWORD_REQUIRED"


async def test_admin_can_change_existing_staff_role(
    client: AsyncClient, admin_actor: str, manager_actor: str
) -> None:
    headers = await _login(client, admin_actor)
    response = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={"staff_id": manager_actor, "staff_name": "Promoted", "role": "ADMIN"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "ADMIN"
    assert body["staff_name"] == "Promoted"

    async with AsyncSessionLocal() as db:
        staff = await db.get(Staff, manager_actor)
        assert staff.role == RoleEnum.ADMIN
        # パスワード未指定の更新では既存ハッシュが維持される。
        assert verify_password(PASSWORD, staff.password_hash)


async def test_admin_can_deactivate_other_staff(
    client: AsyncClient, admin_actor: str, manager_actor: str
) -> None:
    headers = await _login(client, admin_actor)
    response = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={
            "staff_id": manager_actor,
            "staff_name": "Deactivated",
            "role": "MANAGER",
            "is_active": False,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False


async def test_admin_cannot_demote_self(client: AsyncClient, admin_actor: str) -> None:
    headers = await _login(client, admin_actor)
    response = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={"staff_id": admin_actor, "staff_name": "Self", "role": "MANAGER"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "SELF_LOCKOUT_PREVENTED"


async def test_admin_cannot_deactivate_self(client: AsyncClient, admin_actor: str) -> None:
    headers = await _login(client, admin_actor)
    response = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={
            "staff_id": admin_actor,
            "staff_name": "Self",
            "role": "ADMIN",
            "is_active": False,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "SELF_LOCKOUT_PREVENTED"


async def test_manager_cannot_access_admin_endpoint(
    client: AsyncClient, manager_actor: str
) -> None:
    headers = await _login(client, manager_actor)
    response = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={"staff_id": "AUTOTEST-ADMIN-BLOCKED", "staff_name": "Nope", "role": "STAFF"},
    )
    assert response.status_code == 403


async def test_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/admin/staff",
        json={"staff_id": "AUTOTEST-ADMIN-NOAUTH", "staff_name": "Nope", "role": "STAFF"},
    )
    assert response.status_code == 401


async def test_password_too_short_is_rejected(client: AsyncClient, admin_actor: str) -> None:
    headers = await _login(client, admin_actor)
    response = await client.post(
        "/api/v1/admin/staff",
        headers=headers,
        json={
            "staff_id": "AUTOTEST-ADMIN-SHORTPASS",
            "staff_name": "Short",
            "role": "STAFF",
            "password": "short",
        },
    )
    assert response.status_code == 422


@pytest.fixture
async def listing_staff() -> AsyncGenerator[list[str], None]:
    ids = ["AUTOTEST-LIST-1", "AUTOTEST-LIST-2", "AUTOTEST-LIST-3"]
    await _create_staff(ids[0], RoleEnum.STAFF, is_active=True)
    await _create_staff(ids[1], RoleEnum.STAFF, is_active=True)
    await _create_staff(ids[2], RoleEnum.STAFF, is_active=False)
    yield ids
    for staff_id in ids:
        await _delete_staff(staff_id)


async def test_admin_can_list_staff_filtered_by_role_and_active(
    client: AsyncClient, admin_actor: str, listing_staff: list[str]
) -> None:
    headers = await _login(client, admin_actor)
    response = await client.get(
        "/api/v1/admin/staff",
        headers=headers,
        params={"role": "STAFF", "is_active": "true", "limit": 200},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    returned_ids = {item["staff_id"] for item in body["items"]}
    assert listing_staff[0] in returned_ids
    assert listing_staff[1] in returned_ids
    assert listing_staff[2] not in returned_ids
    assert all(item["role"] == "STAFF" for item in body["items"])
    assert all(item["is_active"] is True for item in body["items"])
    assert body["total"] == len(body["items"])


async def test_admin_can_list_inactive_staff(
    client: AsyncClient, admin_actor: str, listing_staff: list[str]
) -> None:
    headers = await _login(client, admin_actor)
    response = await client.get(
        "/api/v1/admin/staff",
        headers=headers,
        params={"is_active": "false", "limit": 200},
    )
    assert response.status_code == 200, response.text
    returned_ids = {item["staff_id"] for item in response.json()["items"]}
    assert listing_staff[2] in returned_ids
    assert listing_staff[0] not in returned_ids


async def test_staff_list_respects_limit(
    client: AsyncClient, admin_actor: str, listing_staff: list[str]
) -> None:
    headers = await _login(client, admin_actor)
    response = await client.get("/api/v1/admin/staff", headers=headers, params={"limit": 1})
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 1


async def test_staff_list_offset_beyond_total_returns_empty(
    client: AsyncClient, admin_actor: str
) -> None:
    headers = await _login(client, admin_actor)
    response = await client.get(
        "/api/v1/admin/staff", headers=headers, params={"offset": 1_000_000}
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []


async def test_manager_cannot_list_staff(client: AsyncClient, manager_actor: str) -> None:
    headers = await _login(client, manager_actor)
    response = await client.get("/api/v1/admin/staff", headers=headers)
    assert response.status_code == 403


async def test_list_staff_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/staff")
    assert response.status_code == 401
