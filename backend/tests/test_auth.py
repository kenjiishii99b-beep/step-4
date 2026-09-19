from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.api.deps import require_roles
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import RoleEnum, Staff

PASSWORD = "correcthorse-battery-staple"


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
async def active_manager() -> AsyncGenerator[str, None]:
    staff_id = "AUTOTEST-MGR"
    await _create_staff(staff_id, RoleEnum.MANAGER)
    yield staff_id
    await _delete_staff(staff_id)


@pytest.fixture
async def inactive_staff() -> AsyncGenerator[str, None]:
    staff_id = "AUTOTEST-INACTIVE"
    await _create_staff(staff_id, RoleEnum.STAFF, is_active=False)
    yield staff_id
    await _delete_staff(staff_id)


@pytest.fixture
async def lockout_target() -> AsyncGenerator[str, None]:
    staff_id = "AUTOTEST-LOCKOUT"
    await _create_staff(staff_id, RoleEnum.STAFF)
    yield staff_id
    await _delete_staff(staff_id)


async def test_login_success(client: AsyncClient, active_manager: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": active_manager, "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["staff_id"] == active_manager
    assert body["role"] == "MANAGER"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_wrong_password_is_generic(client: AsyncClient, active_manager: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": active_manager, "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "IDまたはパスワードが正しくありません。"


async def test_login_unknown_staff_matches_wrong_password_message(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": "NO-SUCH-STAFF", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "IDまたはパスワードが正しくありません。"


async def test_login_inactive_staff_rejected(client: AsyncClient, inactive_staff: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": inactive_staff, "password": PASSWORD}
    )
    assert response.status_code == 401


async def test_refresh_issues_new_access_token(client: AsyncClient, active_manager: str) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"staff_id": active_manager, "password": PASSWORD}
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_refresh_rejects_access_token(client: AsyncClient, active_manager: str) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"staff_id": active_manager, "password": PASSWORD}
    )
    access_token = login.json()["access_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


async def test_refresh_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert response.status_code == 401


async def test_login_locks_out_after_max_failures(client: AsyncClient, lockout_target: str) -> None:
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login", json={"staff_id": lockout_target, "password": "wrong"}
        )

    response = await client.post(
        "/api/v1/auth/login", json={"staff_id": lockout_target, "password": PASSWORD}
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_require_roles_allows_matching_role() -> None:
    staff = Staff(staff_id="X", staff_name="X", password_hash="h", role=RoleEnum.MANAGER)
    checker = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])
    assert checker(current_user=staff) is staff


def test_require_roles_rejects_other_role() -> None:
    from fastapi import HTTPException

    staff = Staff(staff_id="X", staff_name="X", password_hash="h", role=RoleEnum.STAFF)
    checker = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])
    with pytest.raises(HTTPException) as exc_info:
        checker(current_user=staff)
    assert exc_info.value.status_code == 403
