from pydantic import BaseModel, Field

from app.models.enums import RoleEnum


class StaffUpsertRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=32)
    staff_name: str = Field(min_length=1, max_length=64)
    role: RoleEnum
    is_active: bool = True
    # 新規作成時は必須。更新時は省略すると既存のパスワードを維持する。
    password: str | None = Field(default=None, min_length=8)


class StaffResponse(BaseModel):
    staff_id: str
    staff_name: str
    role: RoleEnum
    is_active: bool


class StaffListResponse(BaseModel):
    items: list[StaffResponse]
    total: int
