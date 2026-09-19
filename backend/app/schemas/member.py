from pydantic import BaseModel, Field


class MemberUpsertRequest(BaseModel):
    member_name: str = Field(min_length=1, max_length=128)
    phone_number: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=16)
    age: int | None = Field(default=None, ge=0, le=150)
    # 新規登録時は省略すると0円。更新時は省略すると既存のポイント残高を維持する。
    point_balance: int | None = Field(default=None, ge=0)


class MemberResponse(BaseModel):
    member_id: str
    member_name: str
    phone_number: str | None
    address: str | None
    gender: str | None
    age: int | None
    point_balance: int
