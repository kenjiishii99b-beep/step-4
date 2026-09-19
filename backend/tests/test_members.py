from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import Member, RoleEnum, Staff

PASSWORD = "members-battery-staple"

MANAGER_ID = "AUTOTEST-MEMBERS-MANAGER"
STAFF_ID = "AUTOTEST-MEMBERS-STAFF"


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
async def member_id() -> AsyncGenerator[str, None]:
    mid = "AUTOTEST-MEMBER-1"
    yield mid
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Member).where(Member.member_id == mid))
        await db.commit()


async def test_manager_can_create_member(
    client: AsyncClient, manager_headers: dict[str, str], member_id: str
) -> None:
    response = await client.put(
        f"/api/v1/members/{member_id}",
        headers=manager_headers,
        json={"member_name": "Taro Yamada", "phone_number": "090-1234-5678"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "member_id": member_id,
        "member_name": "Taro Yamada",
        "phone_number": "090-1234-5678",
        "address": None,
        "gender": None,
        "age": None,
        "point_balance": 0,
    }


async def test_staff_can_get_member(
    client: AsyncClient,
    manager_headers: dict[str, str],
    staff_headers: dict[str, str],
    member_id: str,
) -> None:
    await client.put(
        f"/api/v1/members/{member_id}",
        headers=manager_headers,
        json={"member_name": "Hanako Suzuki"},
    )
    response = await client.get(f"/api/v1/members/{member_id}", headers=staff_headers)
    assert response.status_code == 200, response.text
    assert response.json()["member_name"] == "Hanako Suzuki"


async def test_get_unknown_member_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/members/NO-SUCH-MEMBER", headers=staff_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "MEMBER_NOT_FOUND"


async def test_update_preserves_point_balance_when_omitted(
    client: AsyncClient, manager_headers: dict[str, str], member_id: str
) -> None:
    await client.put(
        f"/api/v1/members/{member_id}",
        headers=manager_headers,
        json={"member_name": "Points Person", "point_balance": 500},
    )
    response = await client.put(
        f"/api/v1/members/{member_id}",
        headers=manager_headers,
        json={"member_name": "Points Person Updated"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["member_name"] == "Points Person Updated"
    assert body["point_balance"] == 500


async def test_staff_cannot_update_member(
    client: AsyncClient, staff_headers: dict[str, str], member_id: str
) -> None:
    response = await client.put(
        f"/api/v1/members/{member_id}",
        headers=staff_headers,
        json={"member_name": "Should Fail"},
    )
    assert response.status_code == 403


async def test_get_member_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/members/whatever")
    assert response.status_code == 401


async def test_update_member_requires_authentication(client: AsyncClient) -> None:
    response = await client.put("/api/v1/members/whatever", json={"member_name": "Nope"})
    assert response.status_code == 401
