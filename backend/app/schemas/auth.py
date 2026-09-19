from pydantic import BaseModel, Field

from app.models.enums import RoleEnum


class LoginRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    staff_id: str
    staff_name: str
    role: RoleEnum


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff_id: str
    staff_name: str
    role: RoleEnum
